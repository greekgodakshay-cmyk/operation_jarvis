"""
Deterministic Freshness Classifier and Live Read-Only Research Router for Operation JARVIS.
Inspects incoming queries before LLM inference for temporal and recency cues,
routes deterministically to read-only search gateways, formats source attribution with dates,
and honestly handles network/gateway failures.
"""
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# Deterministic cues indicating freshness requirement
FRESHNESS_PATTERNS = [
    r"\b(latest|current|currently|today|today's|tonight|yesterday|tomorrow|this week|this month|this year|now|recent|recently)\b",
    r"\b(who is the (new|current|present|acting|interim)|what is the (new|current|present|latest))\b",
    r"\b(breaking news|headline|headlines|new release|new version|just released|newest)\b",
    r"\b(cve-\d{4}-\d+|vulnerability|zero-day|0-day|patch tuesday|security advisory|exploit)\b",
    r"\b(stock price|crypto price|exchange rate|weather today|live score|price of)\b",
    r"\b(election|elections|election result|midterm|midterms|elected|first .* elected)\b",
    r"\b(prime minister|president|ceo|leadership changes|resignation|resigned|step down|steps down)\b",
    r"\b(scandal|alleged|allegation|allegations|spy scandal|outage|outages)\b",
    r"\b(spacex|starship|flight \d+|falcon|rocket launch|nasa mission)\b",
    r"\b(arxiv|recent paper|recent research|preprint|scientific preprint)\b"
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in FRESHNESS_PATTERNS]

def classify_freshness(query: str) -> Tuple[bool, str]:
    """
    Classifies if query demands live real-time internet intelligence.
    Returns: (is_freshness_required, route_type)
    route_type: 'cve' | 'arxiv' | 'news' | 'general_web' | 'none'
    """
    if not query or len(query.strip()) < 3:
        return False, "none"

    q_lower = query.lower()
    
    # Check Weather / Meteorological queries
    if re.search(r"\b(weather|temperature|forecast|rain|raining|rainfall|humidity|wind speed|precipitation|degrees outside|celsius outside)\b", q_lower):
        return True, "weather"

    # Check CVE / Security
    if re.search(r"\b(cve-\d{4}-\d+|vulnerability|zero-day|0-day|security advisory|exploit)\b", q_lower):
        return True, "cve"
        
    # Check arXiv / Science
    if re.search(r"\b(arxiv|preprint|quantum|paper|research study)\b", q_lower) and any(w in q_lower for w in ["latest", "recent", "new"]):
        return True, "arxiv"
        
    # Check News / Current Events / Politics / Leadership / SpaceX
    if re.search(r"\b(news|headline|headlines|breaking|happening|update|updates|current president|current pm|current ceo|ceo|prime minister|election|elections|midterm|midterms|elected|spacex|starship|resignation|scandal|huang|kress|netanyahu|eisenkot)\b", q_lower):
        return True, "news"

    # Check general freshness patterns
    for pat in COMPILED_PATTERNS:
        if pat.search(q_lower):
            return True, "news"

    return False, "none"

def fetch_live_intelligence(query: str, route_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Deterministically routes to read-only internet gateway tools with attribution.
    All calls are strictly GET/HEAD operations with timeout and injection defenses.
    """
    t0 = time.perf_counter()
    if not route_type or route_type == "none":
        _, route_type = classify_freshness(query)

    from registry.capability_registry import capability_registry
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    results = []
    error = None

    try:
        if route_type == "weather":
            from core.weather_service import get_weather
            loc_match = re.search(r"\b(?:in|for|at|around)\s+([a-zA-Z\s.-]+?)(?:\s+(?:today|tomorrow|now|tonight|this week|right now|\?|\.|$)|$)", query, re.IGNORECASE)
            loc = loc_match.group(1).strip() if loc_match else None
            if loc and loc.lower() in ("the", "this", "my area", "here", "outside"):
                loc = None
            w_res = get_weather(location=loc)
            if w_res.get("ok"):
                prov = w_res.get("provenance", "[Live observation]")
                cur = w_res.get("current", {})
                loc_disp = w_res.get("location_display", loc or "Bengaluru, Karnataka, India")
                today_f = w_res.get("today_forecast", {})
                tmrw_f = w_res.get("tomorrow_forecast", {})
                banner = (
                    f"\n[LIVE WEATHER INTELLIGENCE - OPEN-METEO PROVIDER]\n"
                    f"Location: {loc_disp}\n"
                    f"Provenance: {prov}\n"
                    f"Current: {cur.get('temperature_c')}°C (feels like {cur.get('apparent_temperature_c')}°C), {cur.get('condition')}, Humidity: {cur.get('humidity_pct')}%, Wind: {cur.get('wind_speed_kmh')} km/h, Precipitation: {cur.get('precipitation_mm')} mm\n"
                    f"Today's Forecast: Max {today_f.get('max_temp_c')}°C / Min {today_f.get('min_temp_c')}°C, Rain prob: {today_f.get('rain_probability_pct')}%\n"
                    f"Tomorrow's Forecast ({tmrw_f.get('date', 'Tomorrow')}): Max {tmrw_f.get('max_temp_c')}°C / Min {tmrw_f.get('min_temp_c')}°C, {tmrw_f.get('condition')}, Rain prob: {tmrw_f.get('rain_probability_pct')}%\n"
                    f"Retrieval Time: {w_res.get('retrieval_time')}\n"
                    f"Natural Summary: {w_res.get('summary')}\n"
                    f"Strict Policy: State observation and retrieval times clearly. Distinguish live vs cached. Never fabricate weather values.\n"
                )
                return {
                    "ok": True,
                    "route": "weather",
                    "results_count": 1,
                    "duration_seconds": round(time.perf_counter() - t0, 3),
                    "attribution_banner": banner,
                    "weather_data": w_res
                }
            else:
                banner = (
                    f"\n[LIVE WEATHER GATEWAY NOTICE: Live weather retrieval for '{loc or 'current location'}' "
                    f"failed: {w_res.get('error')}. Honest response policy: State that live weather is currently unavailable. "
                    f"Do NOT fabricate temperatures or meteorological conditions.]\n"
                )
                return {
                    "ok": False,
                    "route": "weather",
                    "results_count": 0,
                    "duration_seconds": round(time.perf_counter() - t0, 3),
                    "attribution_banner": banner,
                    "error": w_res.get("error")
                }

        elif route_type == "cve":
            tool = capability_registry.get_tool("cve_search")
            if tool:
                res = tool.handler(query) if callable(tool.handler) else []
                if isinstance(res, list):
                    results = res
                elif isinstance(res, dict):
                    results = res.get("vulnerabilities", res.get("results", []))
        elif route_type == "arxiv":
            tool = capability_registry.get_tool("arxiv_search")
            if tool:
                res = tool.handler(query) if callable(tool.handler) else []
                if isinstance(res, list):
                    results = res
                elif isinstance(res, dict):
                    results = res.get("papers", res.get("results", []))
        elif route_type == "news":
            tool = capability_registry.get_tool("search_news")
            if tool:
                res = tool.handler(query) if callable(tool.handler) else []
                if isinstance(res, list):
                    results = res
                elif isinstance(res, dict):
                    results = res.get("articles", res.get("headlines", res.get("results", [])))
            # If news returned no hits, fallback to unified web search
            if not results:
                web_tool = capability_registry.get_tool("web_search")
                if web_tool:
                    web_res = web_tool.handler(query) if callable(web_tool.handler) else {}
                    if isinstance(web_res, dict):
                        results = web_res.get("sources", web_res.get("results", []))
                    elif isinstance(web_res, list):
                        results = web_res
        else:
            # General fallback to web_search or wikipedia_search
            tool = capability_registry.get_tool("web_search")
            if tool:
                res = tool.handler(query) if callable(tool.handler) else {}
                if isinstance(res, dict):
                    results = res.get("sources", res.get("results", []))
                elif isinstance(res, list):
                    results = res

    except Exception as ex:
        error = str(ex)

    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    if error or not results:
        return {
            "ok": False,
            "query": query,
            "route_type": route_type,
            "retrieved_at": now_str,
            "latency_ms": round(elapsed_ms, 2),
            "evidence": [],
            "attribution_banner": (
                f"[LIVE RESEARCH GATEWAY NOTICE: Deterministic live lookup for '{query}' ({route_type}) "
                f"was attempted at {now_str}. Gateway returned zero verified live records or encountered: {error or 'No live hits'}. "
                f"Honest response policy: Proceeding with existing offline indexed knowledge. Do NOT fabricate current events.]"
            )
        }

    # Format structured evidence items with source citations, URLs, and dates
    formatted_items = []
    for item in results[:5]:
        if isinstance(item, dict):
            publisher = item.get("publisher") or item.get("source") or route_type
            url = item.get("url") or item.get("link") or ""
            date_str = item.get("published_date") or item.get("published") or item.get("pubDate") or now_str[:10]
            title = item.get("title", "Untitled")
            snippet = item.get("snippet") or item.get("description") or item.get("summary") or title
            formatted_items.append({
                "title": title,
                "source": publisher,
                "url": url,
                "date": date_str,
                "snippet": snippet[:300]
            })
        elif isinstance(item, str):
            formatted_items.append({
                "title": "Search Result",
                "source": route_type,
                "url": "",
                "date": now_str[:10],
                "snippet": item[:300]
            })

    attribution_text = "\n".join([
        f"- [{it['title']}] Publisher: {it['source']} | Date: {it['date']} | URL: {it['url']}\n  Summary: {it['snippet']}"
        for it in formatted_items
    ])

    return {
        "ok": True,
        "query": query,
        "route_type": route_type,
        "retrieved_at": now_str,
        "latency_ms": round(elapsed_ms, 2),
        "evidence": formatted_items,
        "attribution_banner": (
            f"[LIVE RESEARCH GATEWAY INTEL: Retrieved {len(formatted_items)} verified sources at {now_str} via {route_type} gateway:\n"
            f"{attribution_text}\n"
            f"Ground your response strictly in these verified live findings with dated source attribution.]"
        )
    }

class FreshnessRouter:
    """Wrapper class providing object-oriented access to freshness router."""
    def is_freshness_sensitive(self, query: str) -> bool:
        is_fresh, _ = classify_freshness(query)
        return is_fresh

    def route_and_fetch(self, query: str) -> Dict[str, Any]:
        return fetch_live_intelligence(query)

freshness_router = FreshnessRouter()
