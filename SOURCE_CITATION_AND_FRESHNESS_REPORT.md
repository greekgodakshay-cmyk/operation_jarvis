# OPERATION JARVIS — SOURCE CITATION & FRESHNESS REPORT

**Document Version:** 1.0.0  
**Status:** Active & Implemented  
**Author:** Principal AI Systems Architect, Senior Agentic AI Engineer & Cybersecurity Engineer  
**Scope:** Public Research Provenance, Freshness Classification, Disagreement Handling, and Hallucination Prevention  
**Date:** 2026-11-06  

---

## 1. EXECUTIVE SUMMARY & PROVENANCE MANDATE

Operation JARVIS mandates that every externally researched answer must provide verifiable data provenance. Grounding research in verifiable sources transforms an AI assistant from a black-box text generator into a trusted, auditable research copilot.

The **Live Read-Only Internet Intelligence Gateway** (`registry/internet_gateway.py`) and **Research Indexer** (`core/research_indexer.py`) enforce structured citation standards and temporal freshness categorization across all public retrievals.

```
+--------------------------------------------------------------------------------------------------+
|                            SOURCE CITATION & FRESHNESS TAXONOMY                                  |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|   1. CITATION DATA MODEL                                                                         |
|      Every externally researched claim includes:                                                 |
|      • Source Title (Cleaned from HTML <title> or API title)                                     |
|      • Canonical URL (Verified destination address)                                              |
|      • Publisher / Domain (e.g. Wikipedia, arXiv.org, NIST NVD, HackerNews)                      |
|      • Publication Date (ISO 8601 from article:published_time, date meta tag, or API)            |
|      • Retrieval Timestamp (ISO 8601 UTC at exact moment of ingestion)                           |
|      • Freshness Category (Deterministic 4-tier classification)                                  |
|      • Key Findings / Snippet (Sanitized body extract)                                           |
|                                                                                                  |
|   ============================================================================================   |
|                                                                                                  |
|   2. FOUR-TIER TEMPORAL FRESHNESS CLASSIFICATION                                                |
|                                                                                                  |
|   [TIER 1: NEWLY PUBLISHED (RECENT)]                                                             |
|   • Published within the last 7 days (delta <= 7 days)                                           |
|   • Represents active breaking news, zero-day advisories, latest releases.                       |
|                                                                                                  |
|   [TIER 2: RECENTLY UPDATED]                                                                     |
|   • Published within the last 30 days (7 < delta <= 30 days)                                     |
|   • Represents current month documentation revisions, patch notes, recent preprints.             |
|                                                                                                  |
|   [TIER 3: OLDER BACKGROUND INFORMATION]                                                         |
|   • Published over 30 days ago (delta > 30 days)                                                 |
|   • Foundational papers, historical records, established documentation.                          |
|   • STRICT RULE: Never describe Tier 3 information as breaking news.                             |
|                                                                                                  |
|   [TIER 4: UNKNOWN PUBLICATION DATE]                                                             |
|   • Missing or unparseable publication date metadata.                                            |
|   • Treated with epistemological caution; verified via content corroboration.                    |
+--------------------------------------------------------------------------------------------------+
```

---

## 2. CITATION METADATA DATA MODEL

In Operation JARVIS, external citations conform to the following schema emitted by `InternetGateway.unified_search()`:

```json
{
  "title": "FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness",
  "url": "https://arxiv.org/abs/2205.14135",
  "publisher": "arXiv.org",
  "published_date": "2022-05-27T17:59:00Z",
  "retrieval_timestamp": "2026-11-06T06:50:42.774250+00:00",
  "freshness_category": "Older Background Information",
  "snippet": "We introduce FlashAttention, an IO-aware exact attention algorithm that uses tiling to reduce the number of memory reads/writes between GPU high bandwidth memory (HBM) and GPU on-chip SRAM..."
}
```

---

## 3. EPISTEMOLOGICAL RULES & DISAGREEMENT HANDLING

### 3.1 Prohibition on Stale-as-Breaking Fallacy
A frequent failure mode of LLMs is describing years-old articles as "breaking announcements" because they appear in search results. JARVIS combats this by:
1. Comparing the extracted `published_date` against the current workstation time (`2026-11-06`).
2. If `delta > 30 days`, the system explicitly classifies the source as *"Older Background Information"* or provides historical context (*"Originally published in May 2022..."*).

### 3.2 Source Disagreement Protocol
When multiple reputable sources offer conflicting facts or differing benchmarks:
- **Rule:** The AI must **not** arbitrarily select one source or fabricate a fake consensus.
- **Protocol:** Explain the discrepancy objectively:
  - Identify Source A's claim, methodology, and date.
  - Identify Source B's claim, methodology, and date.
  - Highlight the underlying technical difference (e.g., differing test hardware, distinct metric definitions, or evolving measurements over time).

### 3.3 Retrieval Failure Handling
If public retrieval fails due to network outage, DNS failure, or anti-SSRF blocks:
- **Rule:** The AI must **never** hallucinate a plausible answer.
- **Protocol:** Truthfully report:
  - Exact target URL or query that failed.
  - Technical error code (e.g. `404 Not Found`, `SSRFViolationError`, `ReadTimeout`).
  - Fallback: State what was already established in local memory and suggest alternate verified sources.

---

## 4. INTEGRATION EVIDENCE ACROSS INTERNET CHANNELS

In Phase 9 empirical testing, citation extraction and freshness classification were verified across four distinct source types:

1. **Wikipedia Articles (Test 17):**
   - Title: `Alan Turing`
   - URL: `https://en.wikipedia.org/wiki/Alan_Turing`
   - Publisher: `Wikipedia` | Retrieval Timestamp: Captured in UTC ISO 8601.
2. **HackerNews Tech Stories (Test 18):**
   - Live developer news stories correctly categorized by created timestamp into `Newly Published` or `Recently Updated`.
3. **arXiv Scientific Preprints (Test 19):**
   - XML feed parsing extracted exact publication dates, author abstracts, and canonical arXiv URLs.
4. **NVD / CIRCL CVE Advisories:**
   - Security advisories categorized with CVSS severity scores and advisory publication timestamps.
