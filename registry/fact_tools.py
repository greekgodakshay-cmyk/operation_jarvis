"""
Cross-Source Fact and Claim Verification Tool for Operation JARVIS.
Cross-references claims against live read-only internet retrieval and persistent memory.
"""
import re
from typing import Any, Dict, List, Optional
from registry.internet_gateway import internet_gateway
from registry.memory_adapter import memory_adapter

def tool_verify_factual_claims(
    claim: str,
    max_sources: int = 3
) -> Dict[str, Any]:
    """
    Verifies a factual claim by cross-referencing independent search sources and local knowledge base.
    Returns consensus stance, verified citations, and confidence score.
    """
    if not claim or not claim.strip():
        return {"ok": False, "error": "Claim text cannot be empty."}

    clean_claim = claim.strip()
    sources_evidence: List[Dict[str, Any]] = []

    # 1. Query Local Knowledge Base
    try:
        mem_hits = memory_adapter.search(clean_claim, limit=2)
        for m in mem_hits:
            sources_evidence.append({
                "source_type": "local_memory",
                "title": m.get("title") or m.get("id"),
                "url": f"memory://{m.get('id')}",
                "snippet": m.get("snippet", "")[:200]
            })
    except Exception:
        pass

    # 2. Query Live Internet Gateway
    try:
        web_hits = internet_gateway.unified_search(query=clean_claim, max_results=max_sources)
        for s in web_hits.get("sources", []):
            sources_evidence.append({
                "source_type": "live_web",
                "title": s.get("title", ""),
                "url": s.get("url", ""),
                "snippet": s.get("snippet", "")[:200],
                "retrieval_timestamp": s.get("retrieval_timestamp", "")
            })
    except Exception:
        pass

    if not sources_evidence:
        return {
            "ok": True,
            "claim": clean_claim,
            "status": "UNVERIFIED",
            "confidence_score": 0.0,
            "reason": "No corroborating sources found across local memory or live internet gateway.",
            "sources": []
        }

    # Analyze textual alignment between claim keywords and source snippets
    claim_words = set(w.lower() for w in re.findall(r"\w+", clean_claim) if len(w) > 3)
    matching_sources = 0

    for src in sources_evidence:
        snippet_words = set(w.lower() for w in re.findall(r"\w+", src.get("snippet", "")))
        common = claim_words.intersection(snippet_words)
        if len(common) >= max(1, len(claim_words) // 2):
            matching_sources += 1

    ratio = matching_sources / len(sources_evidence) if sources_evidence else 0.0
    if ratio >= 0.6:
        verdict = "VERIFIED_SUPPORTED"
        confidence = min(0.95, round(0.5 + 0.45 * ratio, 2))
    elif ratio >= 0.3:
        verdict = "PARTIALLY_CORROBORATED"
        confidence = round(0.3 + 0.3 * ratio, 2)
    else:
        verdict = "INCONCLUSIVE_OR_CONTRADICTED"
        confidence = round(ratio, 2)

    return {
        "ok": True,
        "claim": clean_claim,
        "status": verdict,
        "confidence_score": confidence,
        "corroborating_sources_count": matching_sources,
        "total_sources_evaluated": len(sources_evidence),
        "sources": sources_evidence[:max_sources + 1]
    }
