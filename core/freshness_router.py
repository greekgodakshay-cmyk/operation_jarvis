"""
Intelligent Source Router and Zero-Footprint Online Intelligence Gateway for Operation JARVIS.
Enforces the Zero-Footprint Knowledge Policy:
- Local reasoning via Qwen 3.5 9B (Ollama).
- Targeted online retrieval via official MediaWiki API, authorized Reddit research,
  primary technical documentation, GitHub releases, and live news RSS.
- Deterministic routing to the smallest relevant set of sources.
- No offline dumps, no persistent external vector databases, and no cloud LLMs.
"""
from datetime import datetime
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from config.settings import settings
from core.llm_client import llm_client
from core.types import TaskBudget
from registry.capability_registry import capability_registry
from registry.internet_gateway import internet_gateway
from registry.memory_adapter import memory_adapter

logger = logging.getLogger("jarvis.source_router")

# --- 1. ROUTING PATTERNS & CLASSIFIERS ---

TIME_PATTERNS = [
    r"\b(what time is it|current time|what is the time|tell me the time|today's date|current date|what day is it)\b"
]

WEATHER_PATTERNS = [
    r"\b(weather|temperature|forecast|rain|raining|rainfall|humidity|wind speed|precipitation|degrees outside|celsius outside)\b"
]

PERSONAL_MEMORY_PATTERNS = [
    r"\b(student internship portal|mr mysto|mysto|my project|my workouts|my training|my routine|my calendar|my tasks|btu|4th sem|cse exam)\b"
]

REDDIT_COMMUNITY_PATTERNS = [
    r"\b(reddit|subreddit|user experiences|community opinion|what do users say|what do developers think|community thoughts|real-world experience)\b",
    r"\b(which (linux distribution|distro|framework|library|tool) is better for\b)"
]

VERSION_PATTERNS = [
    r"\b(latest version of|newest version of|current version of|latest release of|release notes for|what version is|new release of)\b",
    r"\b(v\d+\.\d+|version \d+)\b"
]

PROGRAMMING_DOCS_PATTERNS = [
    r"\b(how does|how to use|how do i use|syntax for|api reference|docs for|documentation for)\b.*\b(asyncio|taskgroup|borrow checker|std::|unique_ptr|shared_ptr|goroutine|channel|pydantic|fastapi|python|rust|c\+\+|javascript|typescript|golang)\b",
    r"\b(asyncio|taskgroup|multiprocessing|threading|pydantic|fastapi|metaclass|decorator|pointer|memory leak|deadlock|borrow checker)\b",
    r"\b(programming|function in python|method in rust|class in c\+\+)\b"
]

NEWS_PATTERNS = [
    r"\b(news|headline|headlines|breaking news|happening today|current events|latest developments|latest ai developments|what's happening in)\b",
    r"\b(election|elections|prime minister|president|leadership changes|resignation|spacex|starship launch)\b"
]

DEEP_RESEARCH_PATTERNS = [
    r"\b(compare\s+[a-zA-Z0-9\+#\.]+\s+and\s+[a-zA-Z0-9\+#\.]+\s+for\b)",
    r"\b(deep research|in-depth comparison|comprehensive analysis of|architectural trade-offs between)\b"
]

FACTUAL_PATTERNS = [
    r"\b(what is|who is|who was|when was|how does|why is|explain the concept of|define)\s+([a-zA-Z0-9\s\-]+)",
    r"\b(photosynthesis|quantum computing|crispr|relativity|thermodynamics|french revolution|black hole|mitochondria|dna|turing machine)\b"
]

CONVERSATIONAL_PATTERNS = [
    r"^(hi|hello|hey|greetings|good morning|good evening|how are you|who are you|what can you do|thanks|thank you)\b",
    r"^(what is \d+\s*[\+\-\*\/]\s*\d+\??)$"
]

def classify_source_route(query: str) -> Dict[str, Any]:
    """
    Deterministically determines the optimal retrieval route following Section 7 routing matrix.
    Returns: route, reason, requires_external, needs_reddit_approval
    """
    if not query or not query.strip():
        return {"route": "conversational", "target": "local_qwen", "requires_external": False, "needs_reddit_approval": False}

    q_lower = query.strip().lower()

    # 1. Operating System Clock / Time
    for p in TIME_PATTERNS:
        if re.search(p, q_lower):
            return {"route": "current_time", "target": "local_os_clock", "requires_external": False, "needs_reddit_approval": False}

    # 2. Weather
    for p in WEATHER_PATTERNS:
        if re.search(p, q_lower):
            return {"route": "weather", "target": "weather_service", "requires_external": True, "needs_reddit_approval": False}

    # 3. Personal Memory
    for p in PERSONAL_MEMORY_PATTERNS:
        if re.search(p, q_lower):
            return {"route": "personal_memory", "target": "sqlite_fts5_memory", "requires_external": False, "needs_reddit_approval": False}

    # 4. Deep Research Comparison
    for p in DEEP_RESEARCH_PATTERNS:
        if re.search(p, q_lower):
            return {"route": "deep_research", "target": "multi_source_research", "requires_external": True, "needs_reddit_approval": True}

    # 5. Community Experiences (Reddit) - REQUIRES EXPLICIT APPROVAL
    for p in REDDIT_COMMUNITY_PATTERNS:
        if re.search(p, q_lower):
            return {"route": "community_experiences", "target": "reddit_authorized_search", "requires_external": True, "needs_reddit_approval": True}

    # 6. Latest Software Version
    for p in VERSION_PATTERNS:
        if re.search(p, q_lower):
            return {"route": "latest_software_version", "target": "github_releases_and_docs", "requires_external": True, "needs_reddit_approval": False}

    # 7. Programming Question / Technical Documentation
    for p in PROGRAMMING_DOCS_PATTERNS:
        if re.search(p, q_lower):
            return {"route": "programming_question", "target": "official_documentation", "requires_external": True, "needs_reddit_approval": False}

    # 8. Current Events & Live News
    for p in NEWS_PATTERNS:
        if re.search(p, q_lower):
            return {"route": "current_events", "target": "live_news_retrieval", "requires_external": True, "needs_reddit_approval": False}

    # 9. Simple Conversational or Basic Math
    for p in CONVERSATIONAL_PATTERNS:
        if re.search(p, q_lower):
            return {"route": "conversational", "target": "local_qwen", "requires_external": False, "needs_reddit_approval": False}

    # 10. General Factual Questions (Science, Engineering, History, etc.) -> Wikipedia Online
    for p in FACTUAL_PATTERNS:
        if re.search(p, q_lower):
            return {"route": "general_factual", "target": "wikipedia_online", "requires_external": True, "needs_reddit_approval": False}

    # Default fallback: If query asks a question with question words, use Wikipedia online
    if any(q_lower.startswith(w) for w in ["what", "who", "when", "where", "why", "how", "explain", "describe", "tell me"]):
        return {"route": "general_factual", "target": "wikipedia_online", "requires_external": True, "needs_reddit_approval": False}

    # Otherwise default to local reasoning
    return {"route": "conversational", "target": "local_qwen", "requires_external": False, "needs_reddit_approval": False}


# Backward compatibility for existing tests/code
def classify_freshness(query: str) -> Tuple[bool, str]:
    routed = classify_source_route(query)
    is_fresh = routed["requires_external"]
    r_type = routed["route"]
    if r_type in ["current_events", "news"]:
        return True, "news"
    elif r_type == "weather":
        return True, "weather"
    elif r_type in ["general_factual", "wikipedia"]:
        return True, "wikipedia"
    elif r_type in ["latest_software_version", "programming_question"]:
        return True, "technical_docs"
    elif r_type == "community_experiences":
        return True, "reddit"
    elif is_fresh:
        return True, "general_web"
    return False, "none"


def fetch_live_intelligence(
    query: str,
    route_type: Optional[str] = None,
    reddit_authorized: bool = False
) -> Dict[str, Any]:
    """
    Executes online retrieval strictly adhering to the Zero-Footprint Knowledge Policy.
    Uses direct API requests and permitted interfaces.
    """
    t0 = time.perf_counter()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    route_info = classify_source_route(query)
    effective_route = route_type or route_info["route"]

    results = []
    error = None
    reddit_prompt = None

    try:
        # Route 1: Local Clock / Time
        if effective_route in ["current_time", "time"]:
            time_now = datetime.now().strftime("%A, %B %d, %Y %I:%M:%S %p")
            banner = f"[LOCAL OS CLOCK: {time_now}]"
            return {
                "ok": True,
                "route": "current_time",
                "results_count": 1,
                "duration_seconds": round(time.perf_counter() - t0, 3),
                "attribution_banner": banner,
                "evidence": [{"title": "System Clock", "source": "Windows OS", "url": "local://clock", "date": now_str, "snippet": time_now}]
            }

        # Route 2: Weather Service
        elif effective_route == "weather":
            from core.weather_service import get_weather
            loc_match = re.search(r"\b(?:in|for|at|around)\s+([a-zA-Z\s.-]+?)(?:\s+(?:today|tomorrow|now|tonight|this week|right now|\?|\.|$)|$)", query, re.IGNORECASE)
            loc = loc_match.group(1).strip() if loc_match else None
            if loc and loc.lower() in ("the", "this", "my area", "here", "outside"):
                loc = None
            w_res = get_weather(location=loc)
            if w_res.get("ok"):
                cur = w_res.get("current", {})
                loc_disp = w_res.get("location_display", loc or "Bengaluru, Karnataka, India")
                banner = (
                    f"\n[LIVE WEATHER INTELLIGENCE - OPEN-METEO PROVIDER]\n"
                    f"Location: {loc_disp}\n"
                    f"Current: {cur.get('temperature_c')}°C, {cur.get('condition')}, Humidity: {cur.get('humidity_pct')}%, Wind: {cur.get('wind_speed_kmh')} km/h\n"
                    f"Retrieval Time: {w_res.get('retrieval_time')}\n"
                )
                return {
                    "ok": True,
                    "route": "weather",
                    "results_count": 1,
                    "duration_seconds": round(time.perf_counter() - t0, 3),
                    "attribution_banner": banner,
                    "weather_data": w_res,
                    "evidence": [{"title": f"Weather for {loc_disp}", "source": "Open-Meteo", "url": "https://open-meteo.com", "date": now_str, "snippet": banner}]
                }
            else:
                banner = f"[LIVE WEATHER NOTICE: Weather retrieval failed: {w_res.get('error')}. Do NOT fabricate weather values.]"
                return {"ok": False, "route": "weather", "results_count": 0, "duration_seconds": round(time.perf_counter() - t0, 3), "attribution_banner": banner, "error": w_res.get("error")}

        # Route 3: Personal Memory
        elif effective_route == "personal_memory":
            mem_hits = memory_adapter.search(query, limit=3)
            results = [{
                "title": m.get("title", "Personal Memory"),
                "source": "Local SQLite Memory",
                "url": f"local://memory/{m.get('id')}",
                "date": m.get("updated_at", now_str),
                "snippet": m.get("snippet", "")
            } for m in mem_hits]

        # Route 4: Wikipedia Online Knowledge (MediaWiki API)
        elif effective_route in ["general_factual", "wikipedia"]:
            wiki_res = internet_gateway.get_wikipedia_article(query)
            if wiki_res.get("ok"):
                results.append({
                    "title": wiki_res["title"],
                    "source": "Wikipedia (MediaWiki API)",
                    "url": wiki_res["url"],
                    "date": wiki_res.get("published_date") or now_str,
                    "snippet": wiki_res.get("extract", "")[:600]
                })
            else:
                # Fallback to search_wikipedia
                hits = internet_gateway.search_wikipedia(query, limit=3)
                for h in hits:
                    results.append({
                        "title": h["title"],
                        "source": "Wikipedia",
                        "url": h["url"],
                        "date": h.get("published_date") or now_str,
                        "snippet": h.get("extract") or h.get("snippet", "")
                    })

        # Route 5: Community Experiences (Reddit Authorization)
        elif effective_route == "community_experiences":
            if not reddit_authorized:
                # Do NOT search automatically! Return requirement for approval
                reddit_prompt = "I can answer using general knowledge and Wikipedia. Would you also like me to investigate Reddit discussions and real-world user experiences?"
                return {
                    "ok": True,
                    "route": "community_experiences",
                    "requires_approval": True,
                    "authorization_prompt": reddit_prompt,
                    "message": reddit_prompt,
                    "evidence": []
                }
            else:
                reddit_res = internet_gateway.search_reddit(query, authorized=True, limit=4)
                for d in reddit_res.get("discussions", []):
                    results.append({
                        "title": f"[Community Experience] {d['title']}",
                        "source": f"Reddit ({d.get('subreddit')})",
                        "url": d["url"],
                        "date": d.get("published_date") or now_str,
                        "snippet": f"Anecdotal user experience: {d.get('snippet')}"
                    })

        # Route 6: Software Version (GitHub Releases)
        elif effective_route == "latest_software_version":
            gh_res = internet_gateway.get_github_release_info(query)
            if gh_res.get("ok"):
                results.append({
                    "title": f"GitHub Release: {gh_res.get('repository')} {gh_res.get('tag_name')}",
                    "source": f"GitHub Releases ({gh_res.get('repository')})",
                    "url": gh_res.get("html_url"),
                    "date": gh_res.get("published_at") or now_str,
                    "snippet": f"Verified Release: Tag {gh_res.get('tag_name')} published on {gh_res.get('published_at')}. Summary: {gh_res.get('summary')}"
                })
            else:
                # Fallback to tech news or docs
                hits = internet_gateway.search_tech_news(query, max_results=3)
                results.extend([{
                    "title": h["title"], "source": h["publisher"], "url": h["url"], "date": h.get("published_date"), "snippet": h.get("snippet")
                } for h in hits])

        # Route 7: Programming Question / Technical Documentation
        elif effective_route == "programming_question":
            doc_hits = internet_gateway.search_technical_docs(query, limit=3)
            for h in doc_hits:
                results.append({
                    "title": h["title"],
                    "source": h.get("publisher", "Technical Documentation"),
                    "url": h["url"],
                    "date": h.get("published_date") or now_str,
                    "snippet": h.get("snippet")
                })

        # Route 8: Live News Retrieval
        elif effective_route in ["current_events", "news"]:
            news_hits = internet_gateway.search_news(query, max_results=4)
            for h in news_hits:
                results.append({
                    "title": h["title"],
                    "source": h.get("publisher", "News Feed"),
                    "url": h["url"],
                    "date": h.get("published_date") or now_str,
                    "snippet": h.get("snippet")
                })

        # Route 9: Deep Research Multi-Source Plan
        elif effective_route == "deep_research":
            # Multi-source: Technical docs + Wikipedia + Ask for Reddit
            wiki_hits = internet_gateway.search_wikipedia(query, limit=2)
            for h in wiki_hits:
                results.append({
                    "title": f"Foundational: {h['title']}",
                    "source": "Wikipedia",
                    "url": h["url"],
                    "date": h.get("published_date") or now_str,
                    "snippet": h.get("extract") or h.get("snippet")
                })
            doc_hits = internet_gateway.search_technical_docs(query, limit=2)
            for h in doc_hits:
                results.append({
                    "title": f"Technical Specification: {h['title']}",
                    "source": h.get("publisher"),
                    "url": h["url"],
                    "date": h.get("published_date") or now_str,
                    "snippet": h.get("snippet")
                })
            if reddit_authorized:
                r_hits = internet_gateway.search_reddit(query, authorized=True, limit=2)
                for d in r_hits.get("discussions", []):
                    results.append({
                        "title": f"Community Discussion: {d['title']}",
                        "source": f"Reddit ({d.get('subreddit')})",
                        "url": d["url"],
                        "date": d.get("published_date") or now_str,
                        "snippet": d.get("snippet")
                    })

        # Route 10: Simple conversational -> no external retrieval
        else:
            return {
                "ok": True,
                "route": "conversational",
                "results_count": 0,
                "duration_seconds": round(time.perf_counter() - t0, 3),
                "attribution_banner": "[CONVERSATIONAL: Answering directly from local Qwen without external retrieval.]",
                "evidence": []
            }

    except Exception as ex:
        error = str(ex)

    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    if error or not results:
        return {
            "ok": False,
            "query": query,
            "route_type": effective_route,
            "retrieved_at": now_str,
            "latency_ms": round(elapsed_ms, 2),
            "evidence": [],
            "attribution_banner": (
                f"[ONLINE RETRIEVAL NOTICE: Online retrieval for '{query}' via {effective_route} returned zero verified records or encountered: {error or 'No hits'}. "
                f"Honest reporting policy: Do NOT fabricate information, dates, or source links.]"
            )
        }

    # Format structured evidence items with source citations, URLs, and dates
    formatted_items = []
    for item in results[:5]:
        publisher = item.get("source") or effective_route
        url = item.get("url") or ""
        date_str = item.get("date") or now_str[:10]
        title = item.get("title", "Source")
        snippet = item.get("snippet") or title
        formatted_items.append({
            "title": title,
            "source": publisher,
            "url": url,
            "date": date_str,
            "snippet": snippet[:400]
        })

    attribution_text = "\n".join([
        f"- [{it['title']}] Publisher: {it['source']} | Date: {it['date']} | URL: {it['url']}\n  Content: {it['snippet']}"
        for it in formatted_items
    ])

    return {
        "ok": True,
        "query": query,
        "route_type": effective_route,
        "retrieved_at": now_str,
        "latency_ms": round(elapsed_ms, 2),
        "evidence": formatted_items,
        "attribution_banner": (
            f"[ONLINE RETRIEVAL INTEL: Retrieved {len(formatted_items)} verified sources at {now_str} via {effective_route}:\n"
            f"{attribution_text}\n"
            f"Ground your response strictly in these verified live findings with dated source attribution and links.]"
        )
    }


class IntelligentSourceRouter:
    """
    Coordinator between intelligent source routing, online zero-footprint retrieval,
    and local Qwen 3.5 9B reasoning.
    """
    def route(self, query: str) -> Dict[str, Any]:
        return classify_source_route(query)

    def is_freshness_sensitive(self, query: str) -> bool:
        routed = classify_source_route(query)
        return routed.get("requires_external", False)

    def route_and_fetch(self, query: str, reddit_authorized: bool = False) -> Dict[str, Any]:
        return fetch_live_intelligence(query, reddit_authorized=reddit_authorized)

    def answer_query(self, query: str, reddit_authorized: bool = False) -> Dict[str, Any]:
        """
        Processes a user question end-to-end:
        1. Classifies route using smallest relevant source set.
        2. Retrieves information online when needed.
        3. Prompts for Reddit authorization if community experience requested without prior approval.
        4. Synthesizes a natural, fact-grounded answer using local Qwen.
        5. Preserves source citations and URLs.
        """
        route_meta = self.route(query)

        # Check Reddit permission requirement
        if route_meta.get("needs_reddit_approval") and not reddit_authorized:
            return {
                "reply": "I can answer using general knowledge and Wikipedia. Would you also like me to investigate Reddit discussions and real-world user experiences?",
                "requires_approval": True,
                "route": route_meta["route"],
                "sources": []
            }

        # Fetch intelligence
        retrieval = self.route_and_fetch(query, reddit_authorized=reddit_authorized)

        # Build prompt for local Qwen
        evidence_text = ""
        source_links = []
        if retrieval.get("evidence"):
            evidence_lines = []
            for ev in retrieval["evidence"]:
                evidence_lines.append(f"• Source: {ev['title']} ({ev['source']}) | Date: {ev['date']} | Link: {ev['url']}\n  Details: {ev['snippet']}")
                if ev.get("url") and not ev["url"].startswith("local://"):
                    source_links.append({"title": ev["title"], "url": ev["url"]})
            evidence_text = "\n".join(evidence_lines)

        sys_prompt = (
            "You are JARVIS, an autonomous local AI system running locally via Qwen 3.5 on an RTX 4050 GPU.\n"
            "Directives:\n"
            "1. Answer the user's question clearly, naturally, and factually based on verified evidence.\n"
            "2. If external sources were retrieved, cite them and provide their original URLs.\n"
            "3. If Reddit discussions were retrieved, clearly distinguish community opinions and user experiences from verified scientific truth.\n"
            "4. If external information could not be found or was unavailable, clearly communicate that limitation. Never fabricate sources or facts."
        )

        user_content = f"Question: {query}"
        if evidence_text:
            user_content += f"\n\nRetrieved External Knowledge:\n{evidence_text}"

        try:
            res = llm_client.chat(
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_content}
                ],
                num_predict=768,
                temperature=0.2,
                think=False,
                task_budget=TaskBudget.SHORT_ANSWER
            )
            reply = res.get("content", "").strip()
        except Exception as e:
            reply = f"Local reasoning model temporarily unavailable: {e}"

        return {
            "reply": reply,
            "route": route_meta["route"],
            "sources": source_links,
            "retrieval_ok": retrieval.get("ok", True)
        }

freshness_router = IntelligentSourceRouter()
source_router = freshness_router
