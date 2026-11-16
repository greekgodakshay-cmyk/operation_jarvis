"""
Live Read-Only Internet Intelligence Gateway for Operation JARVIS.
Enforces strict read-only semantics (GET/HEAD only), SSRF & DNS rebinding defense,
outgoing query privacy sanitization, prompt injection neutralization,
and source freshness classification.
"""
import datetime
import html
import ipaddress
import json
import logging
import os
import re
import socket
import time
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
INTERNET_AUDIT_LOG = LOGS_DIR / "internet_retrieval.jsonl"

logger = logging.getLogger("jarvis.internet_gateway")

class InternetSecurityViolation(Exception):
    pass

class SSRFViolationError(InternetSecurityViolation):
    pass

class ReadOnlyViolationError(InternetSecurityViolation):
    pass


class HTMLContentExtractor(HTMLParser):
    """Safe, zero-dependency HTML parser for text and metadata extraction."""
    def __init__(self):
        super().__init__()
        self.title: str = ""
        self.meta_date: str = ""
        self.meta_description: str = ""
        self.text_chunks: List[str] = []
        self._in_title = False
        self._ignore_tag = False
        self._ignored_tags = {"script", "style", "noscript", "svg", "iframe", "header", "footer", "nav"}

    def handle_starttag(self, tag, attrs):
        lower_tag = tag.lower()
        if lower_tag in self._ignored_tags:
            self._ignore_tag = True
        elif lower_tag == "title":
            self._in_title = True
        elif lower_tag == "meta":
            attr_dict = {k.lower(): v for k, v in attrs if v is not None}
            name = attr_dict.get("name", "") or attr_dict.get("property", "")
            content = attr_dict.get("content", "")
            if name.lower() in ["article:published_time", "date", "pubdate", "publishdate", "og:updated_time"]:
                if not self.meta_date and content:
                    self.meta_date = content.strip()
            elif name.lower() in ["description", "og:description"]:
                if not self.meta_description and content:
                    self.meta_description = content.strip()

    def handle_endtag(self, tag):
        lower_tag = tag.lower()
        if lower_tag in self._ignored_tags:
            self._ignore_tag = False
        elif lower_tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._ignore_tag:
            return
        if self._in_title:
            self.title += data.strip() + " "
        else:
            cleaned = data.strip()
            if cleaned:
                self.text_chunks.append(cleaned)

    def get_clean_text(self, max_length: int = 15000) -> str:
        raw_text = " ".join(self.text_chunks)
        clean_text = re.sub(r"\s+", " ", raw_text).strip()
        return clean_text[:max_length]


class InternetGateway:
    """
    Dedicated read-only internet gateway for JARVIS.
    """
    ALLOWED_SCHEMES = {"http", "https"}
    ALLOWED_METHODS = {"GET", "HEAD"}
    MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 5 MB max
    DEFAULT_TIMEOUT = 15.0  # seconds
    MAX_REDIRECT_HOPS = 5

    ALLOWED_CONTENT_TYPES = [
        "text/html", "text/plain", "text/markdown", "application/json",
        "text/xml", "application/xml", "application/rss+xml", "application/atom+xml"
    ]

    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 (JARVIS-Intelligence/1.0; Read-Only)"

    # Prompt injection indicators
    INJECTION_INDICATORS = [
        re.compile(r"ignore\s+(previous|all)\s+instructions", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+(an?\s+unrestricted|in\s+developer\s+mode)", re.IGNORECASE),
        re.compile(r"system\s*:\s*you\s+must", re.IGNORECASE),
        re.compile(r"<\|im_start\|>", re.IGNORECASE),
        re.compile(r"<\|im_end\|>", re.IGNORECASE),
        re.compile(r"bypass\s+all\s+(security|policy|restrictions)", re.IGNORECASE)
    ]

    def __init__(self):
        self.audit_log_path = INTERNET_AUDIT_LOG

    def log_retrieval(self, event_data: Dict[str, Any]):
        try:
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event_data) + "\n")
        except Exception as e:
            logger.warning(f"Failed to write internet retrieval audit log: {e}")

    # --- 1. PRIVACY PROTECTION & QUERY SANITIZATION ---
    def sanitize_outgoing_query(self, query: str) -> str:
        """
        Strips personal identifiers, file paths, credentials, and tokens from query
        before external transmission.
        """
        if not isinstance(query, str):
            query = str(query)

        sanitized = query
        # Strip Windows and Unix absolute file paths
        sanitized = re.sub(r"[a-zA-Z]:\\[^\s\"']+", "[LOCAL_PATH]", sanitized)
        sanitized = re.sub(r"/(?:Users|home|etc|var|usr)/[^\s\"']+", "[LOCAL_PATH]", sanitized)

        # Strip user names / personal identifiers
        sanitized = re.sub(r"\b(Akshay|aravind|\.rv|Batman)\b", "user", sanitized, flags=re.IGNORECASE)

        # Strip email addresses
        sanitized = re.sub(r"[\w\.-]+@[\w\.-]+\.\w+", "[EMAIL_REDACTED]", sanitized)

        # Strip typical API keys and secrets
        sanitized = re.sub(r"\b(?:sk|ghp|gho|pat|api)[-_][a-zA-Z0-9_\-]{14,}\b", "[SECRET_REDACTED]", sanitized)
        sanitized = re.sub(r"\bBearer\s+[a-zA-Z0-9_\-\.]{16,}\b", "[AUTH_REDACTED]", sanitized)

        return sanitized.strip()

    # --- 2. SSRF & NETWORK ISOLATION DEFENSE ---
    def validate_destination_ip(self, host: str, port: Optional[int] = None) -> List[str]:
        """
        Resolves hostname and verifies that none of the returned IP addresses
        belong to localhost, private RFC1918 networks, link-local, or cloud metadata endpoints.
        """
        cleaned_host = host.strip().lower()
        if not cleaned_host:
            raise SSRFViolationError("Empty hostname is invalid.")

        # Disallow explicit localhost names
        if cleaned_host in ["localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal", "instance-data"]:
            raise SSRFViolationError(f"Direct connection to '{cleaned_host}' is forbidden by SSRF defense policy.")

        try:
            # Resolve DNS
            addr_info = socket.getaddrinfo(cleaned_host, port or 443, socket.AF_UNSPEC, socket.SOCK_STREAM)
        except socket.gaierror as e:
            raise SSRFViolationError(f"DNS resolution failed for '{cleaned_host}': {e}")

        verified_ips = []
        for family, socktype, proto, canonname, sockaddr in addr_info:
            ip_str = sockaddr[0]
            try:
                ip_obj = ipaddress.ip_address(ip_str)
            except ValueError:
                raise SSRFViolationError(f"Invalid resolved IP '{ip_str}' for host '{cleaned_host}'.")

            # Check loopback
            if ip_obj.is_loopback:
                raise SSRFViolationError(f"SSRF Violation: Host '{cleaned_host}' resolved to loopback IP '{ip_str}'.")

            # Check private networks (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, fc00::/7)
            if ip_obj.is_private:
                raise SSRFViolationError(f"SSRF Violation: Host '{cleaned_host}' resolved to private RFC1918 IP '{ip_str}'.")

            # Check link-local / APIPA (169.254.0.0/16, fe80::/10)
            if ip_obj.is_link_local:
                raise SSRFViolationError(f"SSRF Violation: Host '{cleaned_host}' resolved to link-local IP '{ip_str}'.")

            # Check reserved / multicast / unspecified
            if ip_obj.is_multicast or ip_obj.is_reserved or ip_obj.is_unspecified:
                raise SSRFViolationError(f"SSRF Violation: Host '{cleaned_host}' resolved to reserved/multicast IP '{ip_str}'.")

            # Check cloud metadata endpoint (169.254.169.254)
            if ip_str == "169.254.169.254":
                raise SSRFViolationError(f"SSRF Violation: Attempt to access cloud metadata endpoint 169.254.169.254.")

            verified_ips.append(ip_str)

        if not verified_ips:
            raise SSRFViolationError(f"No valid public IP addresses resolved for host '{cleaned_host}'.")

        return verified_ips

    # --- 3. STRICT READ-ONLY HTTP GET / HEAD RETRIEVAL WITH HOP-BY-HOP REDIRECT VERIFICATION ---
    def fetch_url(self, url: str, method: str = "GET", timeout: float = DEFAULT_TIMEOUT) -> Dict[str, Any]:
        """
        Executes a strictly read-only HTTP request with SSRF validation at every hop,
        size limits, and content-type verification.
        """
        upper_method = method.upper().strip()
        if upper_method not in self.ALLOWED_METHODS:
            raise ReadOnlyViolationError(
                f"Method '{upper_method}' is forbidden. Internet Gateway permits ONLY read-only GET and HEAD."
            )

        parsed = urllib.parse.urlparse(url)
        if parsed.scheme.lower() not in self.ALLOWED_SCHEMES:
            raise SSRFViolationError(f"Forbidden URL scheme '{parsed.scheme}'. Only http and https are permitted.")

        current_url = url
        start_time = time.time()
        retrieval_timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Hop-by-hop redirect loop
        for hop in range(self.MAX_REDIRECT_HOPS + 1):
            curr_parsed = urllib.parse.urlparse(current_url)
            if curr_parsed.scheme.lower() not in self.ALLOWED_SCHEMES:
                raise SSRFViolationError(f"Redirected to forbidden scheme '{curr_parsed.scheme}'.")

            # Validate destination host before connection
            self.validate_destination_ip(curr_parsed.hostname, curr_parsed.port)

            headers = {
                "User-Agent": self.USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/json,application/xml,text/plain;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Cache-Control": "no-cache"
            }

            try:
                with httpx.Client(timeout=timeout, follow_redirects=False) as client:
                    resp = client.request(upper_method, current_url, headers=headers)

                    # Check for redirect
                    if resp.status_code in [301, 302, 303, 307, 308]:
                        loc = resp.headers.get("Location")
                        if not loc:
                            break
                        # Resolve relative redirect
                        current_url = urllib.parse.urljoin(current_url, loc)
                        continue

                    # Verified final response
                    content_type = resp.headers.get("Content-Type", "").lower()
                    is_allowed_ct = any(ct in content_type for ct in self.ALLOWED_CONTENT_TYPES)

                    # Size check
                    raw_content = resp.content
                    if len(raw_content) > self.MAX_RESPONSE_BYTES:
                        raw_content = raw_content[:self.MAX_RESPONSE_BYTES]

                    duration_ms = round((time.time() - start_time) * 1000.0, 2)

                    # Parse HTML / text
                    text_content = ""
                    title = ""
                    published_date = ""
                    meta_desc = ""

                    try:
                        decoded_text = raw_content.decode("utf-8", errors="replace")
                    except Exception:
                        decoded_text = str(raw_content)

                    if "text/html" in content_type or "xml" in content_type:
                        parser = HTMLContentExtractor()
                        try:
                            parser.feed(decoded_text)
                            text_content = parser.get_clean_text()
                            title = parser.title.strip()
                            published_date = parser.meta_date.strip()
                            meta_desc = parser.meta_description.strip()
                        except Exception:
                            text_content = decoded_text[:15000]
                    else:
                        text_content = decoded_text[:15000]

                    # Freshness classification
                    freshness = self.classify_freshness(published_date)

                    # Untrusted content wrapping & prompt injection neutralization
                    sanitized_body = self.sanitize_untrusted_content(text_content, current_url)

                    audit_entry = {
                        "timestamp": retrieval_timestamp,
                        "url": current_url,
                        "method": upper_method,
                        "status_code": resp.status_code,
                        "content_type": content_type,
                        "bytes": len(raw_content),
                        "duration_ms": duration_ms,
                        "title": title[:100]
                    }
                    self.log_retrieval(audit_entry)

                    return {
                        "ok": resp.status_code >= 200 and resp.status_code < 300,
                        "status_code": resp.status_code,
                        "url": current_url,
                        "title": title or curr_parsed.hostname,
                        "publisher": curr_parsed.hostname,
                        "published_date": published_date or None,
                        "retrieval_timestamp": retrieval_timestamp,
                        "freshness_category": freshness,
                        "meta_description": meta_desc,
                        "content": sanitized_body,
                        "raw_text": decoded_text,
                        "raw_bytes_length": len(raw_content),
                        "duration_ms": duration_ms
                    }

            except Exception as e:
                duration_ms = round((time.time() - start_time) * 1000.0, 2)
                audit_entry = {
                    "timestamp": retrieval_timestamp,
                    "url": current_url,
                    "method": upper_method,
                    "error": str(e),
                    "duration_ms": duration_ms
                }
                self.log_retrieval(audit_entry)
                raise e

        raise SSRFViolationError("Exceeded maximum redirect hops.")

    # --- 4. FRESHNESS CLASSIFICATION ---
    def classify_freshness(self, date_str: Optional[str]) -> str:
        """
        Classifies freshness based on publication date:
        - Newly Published (within last 7 days)
        - Recently Updated (within last 30 days)
        - Older Background Information (> 30 days)
        - Unknown Publication Date (no parseable date)
        """
        if not date_str:
            return "Unknown Publication Date"

        # Attempt ISO date parsing
        try:
            # Clean common ISO variations
            cleaned = date_str.replace("Z", "+00:00")
            dt = datetime.datetime.fromisoformat(cleaned)
            now = datetime.datetime.now(datetime.timezone.utc)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)

            delta = now - dt
            days = delta.days

            if days < 0:
                return "Newly Published (Recent)"
            elif days <= 7:
                return "Newly Published (Recent)"
            elif days <= 30:
                return "Recently Updated"
            else:
                return "Older Background Information"
        except Exception:
            # Check for year in string
            year_match = re.search(r"\b(20\d\d)\b", date_str)
            if year_match:
                year = int(year_match.group(1))
                curr_year = datetime.datetime.now().year
                if year == curr_year:
                    return "Recently Updated"
                elif year < curr_year:
                    return "Older Background Information"
            return "Unknown Publication Date"

    # --- 5. UNTRUSTED CONTENT SANITIZATION & PROMPT INJECTION DEFENSE ---
    def sanitize_untrusted_content(self, text: str, source_url: str) -> str:
        """
        Neutralizes prompt injection sequences and wraps content in explicit untrusted tags.
        """
        if not isinstance(text, str):
            text = str(text)

        suspicious = any(pattern.search(text) for pattern in self.INJECTION_INDICATORS)
        warning_attr = ' warning="possible_prompt_injection_detected"' if suspicious else ''

        # Neutralize markdown system fakes and special tokens
        safe = text.replace("<|im_start|>", "[ESCAPED_TOKEN]")
        safe = safe.replace("<|im_end|>", "[ESCAPED_TOKEN]")
        safe = safe.replace("```system", "```escaped_system")
        safe = safe.replace("```assistant", "```escaped_assistant")
        safe = safe.replace("[SYSTEM]", "[ESCAPED_SYSTEM]")

        return (
            f'<untrusted_external_content source="{source_url}"{warning_attr}>\n'
            f'{safe}\n'
            f'</untrusted_external_content>'
        )

    # --- 6. TARGETED PUBLIC INTELLIGENCE RETRIEVAL SOURCES ---

    def search_wikipedia(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Queries official Wikipedia REST API for clean encyclopedia knowledge.
        """
        clean_q = self.sanitize_outgoing_query(query)
        if not clean_q:
            return []

        search_url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": clean_q,
            "utf8": 1,
            "format": "json"
        }
        full_url = f"{search_url}?{urllib.parse.urlencode(params)}"
        ret = self.fetch_url(full_url)
        if not ret.get("ok"):
            return []

        results = []
        try:
            # Extract json from raw content or text
            raw = ret["content"]
            # Content is wrapped in <untrusted_external_content>
            json_str = re.sub(r"</?untrusted_external_content[^>]*>", "", raw).strip()
            data = json.loads(json_str)
            items = data.get("query", {}).get("search", [])[:limit]
            
            for item in items:
                page_id = item.get("pageid")
                title = item.get("title", "")
                snippet = html.unescape(re.sub(r"<[^>]+>", "", item.get("snippet", "")))
                page_url = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
                results.append({
                    "title": title,
                    "url": page_url,
                    "publisher": "Wikipedia",
                    "published_date": item.get("timestamp"),
                    "retrieval_timestamp": ret["retrieval_timestamp"],
                    "freshness_category": self.classify_freshness(item.get("timestamp")),
                    "snippet": snippet
                })
        except Exception as e:
            logger.warning(f"Error parsing Wikipedia response: {e}")

        return results

    def search_arxiv(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Queries arXiv official API for computer science and AI research papers.
        """
        clean_q = self.sanitize_outgoing_query(query)
        if not clean_q:
            return []

        arxiv_url = "https://export.arxiv.org/api/query"
        params = {
            "search_query": f"all:{clean_q}",
            "start": 0,
            "max_results": max_results
        }
        full_url = f"{arxiv_url}?{urllib.parse.urlencode(params)}"
        ret = self.fetch_url(full_url)
        if not ret.get("ok"):
            return []

        results = []
        try:
            raw = ret.get("raw_text", ret["content"])
            xml_str = re.sub(r"</?untrusted_external_content[^>]*>", "", raw).strip()
            # Parse entries using regex to avoid external xml lib requirements
            entries = re.findall(r"<entry>(.*?)</entry>", xml_str, re.DOTALL)
            for entry in entries[:max_results]:
                title_m = re.search(r"<title>(.*?)</title>", entry, re.DOTALL)
                summary_m = re.search(r"<summary>(.*?)</summary>", entry, re.DOTALL)
                published_m = re.search(r"<published>(.*?)</published>", entry)
                id_m = re.search(r"<id>(.*?)</id>", entry)

                title = re.sub(r"\s+", " ", title_m.group(1)).strip() if title_m else "Untitled Paper"
                summary = re.sub(r"\s+", " ", summary_m.group(1)).strip() if summary_m else ""
                pub_date = published_m.group(1).strip() if published_m else ""
                paper_url = id_m.group(1).strip() if id_m else "https://arxiv.org"

                results.append({
                    "title": title,
                    "url": paper_url,
                    "publisher": "arXiv.org",
                    "published_date": pub_date,
                    "retrieval_timestamp": ret["retrieval_timestamp"],
                    "freshness_category": self.classify_freshness(pub_date),
                    "snippet": summary[:300] + "..." if len(summary) > 300 else summary
                })
        except Exception as e:
            logger.warning(f"Error parsing arXiv response: {e}")

        return results

    def search_tech_news(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Queries HackerNews Algolia API for breaking technology announcements and discussions.
        """
        clean_q = self.sanitize_outgoing_query(query)
        if not clean_q:
            return []

        hn_url = "https://hn.algolia.com/api/v1/search"
        params = {
            "query": clean_q,
            "tags": "story",
            "hitsPerPage": max_results
        }
        full_url = f"{hn_url}?{urllib.parse.urlencode(params)}"
        ret = self.fetch_url(full_url)
        if not ret.get("ok"):
            return []

        results = []
        try:
            raw = ret["content"]
            json_str = re.sub(r"</?untrusted_external_content[^>]*>", "", raw).strip()
            data = json.loads(json_str)
            for hit in data.get("hits", [])[:max_results]:
                title = hit.get("title", "")
                url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
                created_at = hit.get("created_at")
                points = hit.get("points", 0)
                num_comments = hit.get("num_comments", 0)

                results.append({
                    "title": title,
                    "url": url,
                    "publisher": urllib.parse.urlparse(url).hostname or "HackerNews",
                    "published_date": created_at,
                    "retrieval_timestamp": ret["retrieval_timestamp"],
                    "freshness_category": self.classify_freshness(created_at),
                    "snippet": f"Score: {points} points, {num_comments} comments. Discussion on {urllib.parse.urlparse(url).hostname}."
                })
        except Exception as e:
            logger.warning(f"Error parsing HN response: {e}")

        return results

    def search_cve(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Queries CIRCL CVE API / public vulnerability databases for security advisories.
        """
        clean_q = self.sanitize_outgoing_query(query)
        if not clean_q:
            return []

        cve_url = f"https://cve.circl.lu/api/search/{urllib.parse.quote(clean_q)}"
        try:
            ret = self.fetch_url(cve_url)
            if not ret.get("ok"):
                return []
            raw = ret["content"]
            json_str = re.sub(r"</?untrusted_external_content[^>]*>", "", raw).strip()
            data = json.loads(json_str)
            results = []
            cve_items = data.get("data", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
            for item in cve_items[:max_results]:
                cve_id = item.get("id") or item.get("cve", "CVE")
                summary = item.get("summary") or item.get("description", "")
                pub_date = item.get("Published") or item.get("modified")
                cvss = item.get("cvss") or item.get("cvss3", "N/A")
                results.append({
                    "title": f"{cve_id} (CVSS: {cvss})",
                    "url": f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                    "publisher": "NIST NVD / CIRCL CVE",
                    "published_date": pub_date,
                    "retrieval_timestamp": ret["retrieval_timestamp"],
                    "freshness_category": self.classify_freshness(pub_date),
                    "snippet": summary[:250] + "..." if len(summary) > 250 else summary
                })
            return results
        except Exception as e:
            logger.warning(f"CVE lookup failed: {e}")
            return []

    def search_news(self, query: str = "", region: str = "IN", max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieves real-time live news headlines with source URLs and timestamps.
        Uses verified Google News RSS feed (zero API keys required, strictly read-only).
        """
        import xml.etree.ElementTree as ET

        clean_q = self.sanitize_outgoing_query(query) if query else ""
        region_clean = region.upper().strip() if region else "IN"

        if clean_q:
            news_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(clean_q)}&hl=en-{region_clean}&gl={region_clean}&ceid={region_clean}:en"
        else:
            news_url = f"https://news.google.com/rss?hl=en-{region_clean}&gl={region_clean}&ceid={region_clean}:en"

        try:
            ret = self.fetch_url(news_url)
            if not ret.get("ok"):
                return []

            raw = ret.get("raw_text") or ret.get("content", "")
            # Remove wrapper tags if present
            xml_str = re.sub(r"</?untrusted_external_content[^>]*>", "", raw).strip()

            root = ET.fromstring(xml_str)
            items = root.findall(".//item")[:max_results]
            results = []

            for item in items:
                title_elem = item.find("title")
                link_elem = item.find("link")
                pub_elem = item.find("pubDate")
                source_elem = item.find("source")

                title = title_elem.text.strip() if title_elem is not None and title_elem.text else "Untitled Headline"
                link = link_elem.text.strip() if link_elem is not None and link_elem.text else news_url
                pub_date = pub_elem.text.strip() if pub_elem is not None and pub_elem.text else ""
                publisher = source_elem.text.strip() if source_elem is not None and source_elem.text else ""

                if not publisher and " - " in title:
                    parts = title.rsplit(" - ", 1)
                    if len(parts) == 2:
                        publisher = parts[1].strip()

                results.append({
                    "title": title,
                    "url": link,
                    "publisher": publisher or "Google News",
                    "published_date": pub_date,
                    "retrieval_timestamp": ret.get("retrieval_timestamp", datetime.datetime.now(datetime.timezone.utc).isoformat()),
                    "freshness_category": self.classify_freshness(pub_date),
                    "snippet": title
                })

            return results
        except Exception as e:
            logger.warning(f"Error parsing News RSS response: {e}")
            return []

    def unified_search(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """
        Unified multi-source discovery across Live News, Wikipedia, Tech News, arXiv, and CVEs.
        Returns synthesized citation bundle.
        """
        sanitized_query = self.sanitize_outgoing_query(query)
        results = {
            "query": sanitized_query,
            "retrieved_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "sources": []
        }

        # Check if query indicates news or current events
        lower_q = sanitized_query.lower()
        is_news_query = any(k in lower_q for k in [
            "news", "headline", "today", "breaking", "current", "latest", "update", "india", "world", "war", "election", "market"
        ])

        if is_news_query:
            news_hits = self.search_news(sanitized_query, max_results=3)
            results["sources"].extend(news_hits)

        # Query Wikipedia
        wiki_hits = self.search_wikipedia(sanitized_query, limit=2)
        results["sources"].extend(wiki_hits)

        # Query Tech News
        tech_hits = self.search_tech_news(sanitized_query, max_results=3)
        results["sources"].extend(tech_hits)

        # If query looks like AI, research, paper, or model -> query arXiv
        if any(k in sanitized_query.lower() for k in ["ai", "model", "qwen", "transformer", "agent", "llm", "deep learning", "neural"]):
            arxiv_hits = self.search_arxiv(sanitized_query, max_results=2)
            results["sources"].extend(arxiv_hits)

        # If query looks like vulnerability, exploit, cve, security -> query CVE
        if any(k in sanitized_query.lower() for k in ["cve", "vulnerability", "exploit", "patch", "zero-day", "advisory"]):
            cve_hits = self.search_cve(sanitized_query, max_results=2)
            results["sources"].extend(cve_hits)

        # If still no sources found and not searched news yet, fallback to news
        if not results["sources"] and not is_news_query:
            fallback_news = self.search_news(sanitized_query, max_results=3)
            results["sources"].extend(fallback_news)

        # Deduplicate and bound
        seen_urls = set()
        unique_sources = []
        for s in results["sources"]:
            if s["url"] not in seen_urls:
                seen_urls.add(s["url"])
                unique_sources.append(s)

        results["sources"] = unique_sources[:max_results]
        results["count"] = len(results["sources"])
        return results

internet_gateway = InternetGateway()
