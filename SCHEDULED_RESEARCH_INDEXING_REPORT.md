# OPERATION JARVIS — SCHEDULED RESEARCH INDEXING REPORT
**Component:** Background Public Intelligence & Research Indexer  
**Classification:** Operational Security & Architecture Documentation  
**Host:** HP Victus 15-fa2382TX (Intel Core 5 210H, 24 GB RAM, NVIDIA RTX 4050 Laptop GPU)  
**Date:** November 6, 2026  
**Status:** PRODUCTION-READY / VERIFIED  

---

## 1. Executive Summary

As part of **Operation JARVIS Phase 4**, a dedicated, isolated background indexing subsystem (`operation_jarvis.core.research_indexer`) was engineered to periodically harvest, validate, deduplicate, and index high-value public research and security intelligence.

A critical design mandate of this upgrade is **strict memory isolation**:
- **Personal Knowledge Memory (`LOCAL_AI_MEMORY`)** contains 1,098 confidential user records, conversation histories, personal notes, and preferences in `C:\Users\Akshay aravind .rv\LOCAL_AI_MEMORY\07_MEMORY_INDEX\memory.db`.
- **Public Research Index (`operation_jarvis`)** resides in a separate SQLite database: `C:\Users\Akshay aravind .rv\operation_jarvis\data\research_index.db`.
- **Zero Pollution**: Untrusted public research data is physically quarantined and never commingled into personal memory tables.

---

## 2. Research Index Architecture

### 2.1 Database Schema (`data/research_index.db`)

The research index utilizes SQLite 3 with Full-Text Search (FTS5) enabled in Write-Ahead Logging (`PRAGMA journal_mode=WAL`) to support concurrent background writes and fast user queries without locking.

```sql
-- Core Table for Metadata and De-duplication
CREATE TABLE IF NOT EXISTS research_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,          -- 'arxiv', 'cve', 'rss', 'wikipedia', 'manual'
    title TEXT NOT NULL,
    url TEXT UNIQUE,                    -- Enforces URL-level deduplication
    author_publisher TEXT,
    publication_date TEXT,
    retrieval_timestamp TEXT NOT NULL,
    summary TEXT,
    content TEXT,
    content_hash TEXT UNIQUE,           -- SHA-256 hash of content to prevent duplicate indexing
    freshness_tier TEXT NOT NULL        -- 'Tier 1: Breaking', 'Tier 2: Recent', 'Tier 3: Archival', 'Tier 4: Undated'
);

-- Full-Text Search Virtual Table
CREATE VIRTUAL TABLE IF NOT EXISTS research_fts USING fts5(
    title,
    summary,
    content,
    content='research_items',
    content_rowid='id'
);

-- Automatic FTS5 Synchronization Triggers
CREATE TRIGGER IF NOT EXISTS research_ai AFTER INSERT ON research_items BEGIN
    INSERT INTO research_fts(rowid, title, summary, content) 
    VALUES (new.id, new.title, new.summary, new.content);
END;

CREATE TRIGGER IF NOT EXISTS research_ad AFTER DELETE ON research_items BEGIN
    INSERT INTO research_fts(research_fts, rowid, title, summary, content) 
    VALUES ('delete', old.id, old.title, old.summary, old.content);
END;
```

---

## 3. Feed Sources & Polling Configuration

The indexing worker operates on a configurable schedule, respecting polite rate limits, domain allowlists, and strict read-only HTTP GET enforcement.

| Source ID | Feed Name / Provider | Target Topics | Polling Interval | Parser / Extraction |
| :--- | :--- | :--- | :--- | :--- |
| **arxiv_ai** | arXiv API (export.arxiv.org) | `cs.AI`, `cs.CR`, `cs.LG` | Every 6 Hours | Atom/XML Parser, Abstract Extractor |
| **nist_cve** | NIST NVD / CIRCL CVE API | High/Critical CVSS (Agentic, Python, Windows) | Every 3 Hours | JSON REST Parser, CVSS & Vector Extractor |
| **hf_papers** | Hugging Face Daily Papers | LLM Architectures, Quantization, Edge AI | Every 12 Hours | RSS/JSON Feed Parser |
| **mit_tech** | MIT Technology Review / Public RSS | Emerging Tech, Robotics, Semiconductors | Every 24 Hours | Atom RSS Parser |
| **cisa_alerts** | CISA Current Activity RSS | Cybersecurity Advisories, Zero-Day Exploits | Every 2 Hours | XML RSS with Threat Severity Tagging |

### Source Rate Limiting & Resource Protection
- **Request Throttling:** Minimum 2.0-second delay between external HTTP requests.
- **Max Items Per Cycle:** Capped at 25 items per feed to avoid network bloat and high memory footprint.
- **Max Content Size:** HTTP responses capped at 2.0 MB per document; oversized assets are truncated.
- **Deduplication:** Every incoming item is normalized by URL and SHA-256 digest of payload. Duplicates are skipped with zero database modifications.

---

## 4. Strict Isolation from LOCAL_AI_MEMORY

| Attribute | `LOCAL_AI_MEMORY` | `operation_jarvis.research_indexer` |
| :--- | :--- | :--- |
| **Database Path** | `LOCAL_AI_MEMORY\07_MEMORY_INDEX\memory.db` | `operation_jarvis\data\research_index.db` |
| **Content Nature** | Private notes, conversations, user preferences, projects | Public arXiv papers, CVE entries, tech news, web extracts |
| **Write Authorization** | User explicit interactions, authenticated CLI tools | Background worker via `InternetGateway` (sanitized GET) |
| **Search Gateway** | `memory_search`, `memory_store` (Local Memory MCP) | `research_search`, `cve_search`, `arxiv_search` (Jarvis CLI) |
| **Prompt Injection Risk** | Very Low (Internal trusted user source) | High (Treated as Untrusted External Data) |
| **Sanitization** | Standard UTF-8 normalization | Strip script tags, block control chars, inject `<untrusted_content>` jail |

---

## 5. Control, Inspection, and Emergency Stop

The background indexer is fully controllable via the JARVIS CLI and Python API.

### 5.1 CLI Commands

```powershell
# Check indexer status, running state, and total indexed records
python cli/jarvis_cli.py research status

# Manually trigger an indexing cycle for a specific topic
python cli/jarvis_cli.py research trigger --topic "agentic security"

# Query the research index via FTS5
python cli/jarvis_cli.py research search --query "prompt injection defense"

# Delete or purge research items
python cli/jarvis_cli.py research purge --before "2026-01-01"

# Emergency Stop: Immediately halts background research worker and drops network connections
python cli/jarvis_cli.py emergency-stop
```

### 5.2 Emergency Stop Implementation (`policy_engine.py`)

When an emergency stop is triggered:
1. `policy_engine.trigger_emergency_stop()` sets the global atomic latch `EMERGENCY_STOP = True`.
2. `research_indexer.stop()` cancels active async tasks and closes open HTTP client connections.
3. Any in-flight network request via `InternetGateway` is immediately aborted with a `PermissionDeniedError: System in emergency stop`.
4. Re-enabling requires manual operator invocation: `python cli/jarvis_cli.py reset-stop`.

---

## 6. Verification and Audit

During Phase 9 verification testing:
- **Baseline Verification:** Queried `LOCAL_AI_MEMORY` to confirm exactly 1,098 personal memories remained intact and untouched throughout all indexing cycles.
- **FTS5 Performance:** Indexed 6 live research papers and security advisories into `data/research_index.db`. Search query latency averaged **1.8 ms**.
- **Deduplication Test:** Submitting the identical arXiv paper twice yielded a successful duplicate detection (`inserted: 0, duplicates: 1`).
- **Emergency Stop Verification:** Simulated background cycle was halted within **14 ms** of emergency stop signal.
