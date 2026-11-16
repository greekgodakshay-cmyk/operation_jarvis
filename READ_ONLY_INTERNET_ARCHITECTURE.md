# OPERATION JARVIS — LIVE READ-ONLY INTERNET INTELLIGENCE ARCHITECTURE

**Document Version:** 1.0.0  
**Status:** Active & Implemented  
**Classification:** Network Security & Intelligence Architecture  
**Target Runtime:** Operation JARVIS Live Internet Gateway (`registry/internet_gateway.py`)  
**Author:** Principal AI Systems Architect & Cybersecurity Engineer  

---

## 1. ARCHITECTURAL OVERVIEW & PURPOSE

To provide Operation JARVIS with real-time public world intelligence without expanding the workstation's attack surface or granting external write access, JARVIS implements a **Dedicated Live Read-Only Internet Intelligence Gateway** (`registry/internet_gateway.py`).

The gateway bridges local reasoning models (Qwen 3.5 9B / Qwen-Batman) and public knowledge sources while strictly enforcing:
1. **Zero Outbound Write Operations:** HTTP methods are mathematically and programmatically restricted to `GET` and `HEAD`.
2. **Strict Network Isolation & Anti-SSRF Defense:** Prevents Server-Side Request Forgery against localhost, internal private subnets, and cloud metadata endpoints with hop-by-hop redirect validation.
3. **Outgoing Privacy Protection:** Sanitizes personal identifiers, file paths, credentials, and tokens from queries before external transmission.
4. **Untrusted Content Wrapping & Prompt-Injection Defense:** Encloses external webpage text in strict boundary delimiters and escapes LLM control tokens.
5. **Data Provenance & Freshness Classification:** Structures all research findings with publisher, URL, publication date, retrieval timestamp, and temporal freshness tiers.
6. **Isolation from Personal Memory:** Internet research is indexed separately into `data/research_index.db`, preserving `LOCAL_AI_MEMORY` as a pure, unpolluted personal knowledge store.

```
+--------------------------------------------------------------------------------------------------+
|                            READ-ONLY INTERNET GATEWAY PIPELINE                                   |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|   1. AGENT QUERY (Qwen / Jarvis Orchestrator / Voice)                                            |
|      "Research latest developments in FlashAttention and transformer optimization"               |
|               |                                                                                  |
|               v                                                                                  |
|   2. PRIVACY SCRUBBER (sanitize_outgoing_query)                                                  |
|      • Strips C:\Users\... and /home/... paths                                                   |
|      • Strips personal names ("Akshay", "Batman") -> "user"                                      |
|      • Strips API keys (sk-..., ghp-...) and Bearer tokens                                       |
|               |                                                                                  |
|               v                                                                                  |
|   3. DESTINATION DNS & SSRF VALIDATOR (validate_destination_ip)                                  |
|      • Resolves DNS via socket.getaddrinfo()                                                     |
|      • Rejects loopback (127.0.0.0/8, ::1)                                                       |
|      • Rejects RFC1918 private subnets (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)             |
|      • Rejects cloud metadata (169.254.169.254)                                                  |
|      • Protocol scheme whitelist: strictly http:// and https://                                  |
|               |                                                                                  |
|               v                                                                                  |
|   4. STRICT READ-ONLY HTTP CLIENT (fetch_url)                                                    |
|      • Methods permitted: GET and HEAD ONLY                                                      |
|      • Rejects POST, PUT, PATCH, DELETE (ReadOnlyViolationError)                                 |
|      • Hop-by-hop redirect validation (re-resolves and validates IP at every hop)                |
|      • Response size capped at 5 MB; 15-second connect/read timeout                              |
|      • Content-type whitelist: text/html, application/json, text/plain, xml                      |
|               |                                                                                  |
|               v                                                                                  |
|   5. PARSING & PROMPT INJECTION DEFENSE (HTMLContentExtractor & sanitize_untrusted_content)     |
|      • Strips scripts, styles, iframes, tracking pixels                                          |
|      • Escapes <|im_start|>, <|im_end|>, ```system, [SYSTEM]                                     |
|      • Wraps in <untrusted_external_content source="..." warning="..."> boundary tags            |
|               |                                                                                  |
|               v                                                                                  |
|   6. TEMPORAL FRESHNESS & PROVENANCE CITATION                                                    |
|      • Extracts published_date (meta tags / API timestamps)                                      |
|      • Classifies freshness: Newly Published / Recently Updated / Older Background / Unknown     |
|      • Emits ISO 8601 retrieval_timestamp and original source URL                                |
|               |                                                                                  |
|               v                                                                                  |
|   7. LOCAL AUDIT LOG & STORAGE ROUTING                                                           |
|      • Written to logs/internet_retrieval.jsonl                                                  |
|      • If background indexed: stored in data/research_index.db (NEVER in LOCAL_AI_MEMORY)        |
+--------------------------------------------------------------------------------------------------+
```

---

## 2. STRICT READ-ONLY ENFORCEMENT SPECIFICATION

A prompt instruction stating "you are read-only" is fundamentally insufficient for computer security. The `InternetGateway` enforces read-only invariants at the code and network levels:

1. **Method Whitelist:**
   - Any HTTP request with method not in `{"GET", "HEAD"}` triggers an immediate `ReadOnlyViolationError` and is aborted prior to network socket creation.
2. **Rejection of Write Payloads:**
   - Outbound requests never carry body payloads, file attachments, form data, or mutations.
3. **Zero Session Re-use:**
   - The internet gateway uses clean, non-persistent HTTP sessions. It never carries cookies, session tokens, or credentials from the user's active Chrome browser profile or Gmail accounts.
4. **Credential Isolation:**
   - Authorization headers (`Bearer`, `Basic`, `ApiKey`) are strictly forbidden on external web requests.

---

## 3. ANTI-SSRF, DNS REBINDING & NETWORK ISOLATION

To prevent an attacker or a malicious prompt from tricking JARVIS into querying internal infrastructure, routers, or cloud services, `InternetGateway.validate_destination_ip()` enforces:

### 3.1 Prohibited Destination Addresses
Every destination hostname is resolved to all associated IPv4 and IPv6 addresses via `socket.getaddrinfo()`. A connection is aborted if any resolved IP falls into:
- **Loopback:** `127.0.0.0/8`, `::1`
- **Private RFC 1918:** `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`
- **Unique Local IPv6:** `fc00::/7`
- **Link-Local / APIPA:** `169.254.0.0/16`, `fe80::/10`
- **Cloud Metadata Endpoints:** `169.254.169.254`, `metadata.google.internal`, `instance-data`
- **Multicast & Reserved:** `224.0.0.0/4`, `240.0.0.0/4`, `0.0.0.0`

### 3.2 Hop-by-Hop Redirect Validation
Standard HTTP client libraries follow redirects automatically without re-validating the destination host. Attackers exploit this via open redirects on public sites pointing to `http://127.0.0.1:8000/`.
- JARVIS disables automatic redirects (`follow_redirects=False`).
- It manually executes up to 5 redirect hops. At **each hop**, the redirect URL is parsed, verified for `http`/`https` scheme, and subjected to the full `validate_destination_ip()` check. If a redirect attempts to enter an internal or private address, execution halts immediately with `SSRFViolationError`.

---

## 4. PUBLIC DISCOVERY & SEARCH CAPABILITIES

The gateway provides five specialized public intelligence channels:

| Tool Name | Upstream Provider / Protocol | Data Types Retrieved | Typical Use Cases |
|---|---|---|---|
| `wikipedia_search` | Official Wikipedia REST API (`en.wikipedia.org/w/api.php`) | Clean encyclopedia articles, summaries, page URLs, revision timestamps | Background technical context, historical programs, foundational CS concepts |
| `arxiv_search` | Official arXiv Export API (`export.arxiv.org/api/query`) | Peer-reviewed preprints, abstracts, publication dates, authors, PDF links | Deep learning breakthroughs, transformer architectures, agent research |
| `cve_search` | CIRCL CVE API / NIST NVD Search | Vulnerability IDs (CVE), CVSS scores, affected software, advisory links | Cybersecurity vulnerability research, patch analysis, zero-day advisories |
| `tech_news_search` | HackerNews Algolia API (`hn.algolia.com/api/v1/search`) | Breaking tech stories, developer releases, discussion URLs, scores | "What's happening in AI today?", framework updates, major tech news |
| `web_search` | Unified Discovery Synthesizer | Multi-source aggregated citation bundle | Broad multi-domain technical research queries |
| `web_fetch` | Strict Read-Only HTTP GET Engine | Sanitized webpage text, metadata titles, published dates | In-depth analysis of specific public documentation pages or articles |

---

## 5. TEMPORAL FRESHNESS CLASSIFICATION ENGINE

To prevent presenting outdated facts as breaking news, every retrieved document is tagged with a deterministic freshness tier:

```python
def classify_freshness(date_str: Optional[str]) -> str:
    if not date_str:
        return "Unknown Publication Date"
    # Parses ISO timestamp and calculates delta from current UTC time
    delta = now_utc - published_utc
    if delta.days <= 7:
        return "Newly Published (Recent)"
    elif delta.days <= 30:
        return "Recently Updated"
    else:
        return "Older Background Information"
```

- When reliable sources disagree on emerging events, JARVIS presents the disagreement neutrally and attributes both positions rather than adopting an unsubstantiated consensus.

---

## 6. INTEGRATION WITH CAPABILITY REGISTRY & QWEN

The internet gateway is registered in `registry/capability_registry.py` under `PermissionLevel.LEVEL_1_SAFE`. Because it is strictly read-only, non-mutating, bounded in memory, and immune to SSRF, autonomous planners and Qwen coworker agents can freely invoke it during technical reasoning tasks without requiring disruptive human approval popups.
