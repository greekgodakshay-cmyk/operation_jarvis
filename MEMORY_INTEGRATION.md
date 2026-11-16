# OPERATION JARVIS — PERSISTENT MEMORY INTEGRATION

**Document Version:** 1.0.0  
**Root Path:** `C:\Users\Akshay aravind .rv\LOCAL_AI_MEMORY`  
**Database:** `C:\Users\Akshay aravind .rv\LOCAL_AI_MEMORY\07_MEMORY_INDEX\memory.db`  
**Total Allocated Budget:** 33.5 GB  

---

## 1. INTEGRATION OBJECTIVE & PRESERVATION MANDATE

The user's persistent memory ecosystem (`LOCAL_AI_MEMORY`) represents a permanent, highly structured repository containing personal preferences, project architecture, conversation archives, and technical documentation.

**Mandate:** Operation Jarvis does NOT create a competing or redundant memory store. Instead, it provides a native Python adapter (`registry/memory_adapter.py`) that binds directly to the existing memory engine components:
- `engine.db.MemoryDB`
- `engine.indexer.MemoryIndexer`
- `engine.retriever.MemoryRetriever`
- `engine.writer.MemoryWriter`
- `engine.monitor.StorageMonitor`

---

## 2. MEMORY ECOSYSTEM ARCHITECTURE & BUDGETS

The storage budget is logically partitioned into 6 distinct categories, defined in `STORAGE_CONFIG.json`:

| Category Directory | Budget (MB) | Purpose |
| :--- | :--- | :--- |
| `01_PERSONAL_PREFERENCES` | 500 MB | Long-term user preferences, career profile, communication tone |
| `02_PROJECT_KNOWLEDGE` | 5,120 MB (5 GB) | Architecture, tech stacks, source code refs, active decisions |
| `03_CONVERSATION_ARCHIVES` | 3,072 MB (3 GB) | Historical dialogues, ChatGPT imports, Qwen session archives |
| `04_TECHNICAL_DOCUMENTATION` | 10,240 MB (10 GB) | Reference manuals, framework specs, SQLite FTS5 guides |
| `05_RESEARCH_LIBRARY` | 10,240 MB (10 GB) | Academic papers, local LLM benchmarks, research analysis |
| `06_TEMPORARY_CACHE` | 5,120 MB (5 GB) | Search indexes, rebuildable embeddings, scratch cache |
| **Total Allocated** | **34,304 MB (~33.5 GB)** | **Monitored with 80% proactive threshold alert** |

---

## 3. CORE INTEGRATION WORKFLOWS

### 3.1 Retrieval Before Planning
Before generating an execution plan, the Dynamic Planner calls:
```python
relevant_memories = memory_adapter.search(query=objective, limit=3)
```
This queries the SQLite `memories_fts` FTS5 virtual table using Okapi BM25 ranking, retrieving relevant project architecture and technical conventions. These are injected into Qwen's prompt, ensuring plans adhere to known workstation realities.

### 3.2 Factual Knowledge Ingestion
When an agent task produces verified factual outcomes (e.g. system benchmarks or architecture specs), it stores the record via:
```python
memory_adapter.store(
    title=title,
    content=content,
    category="02_PROJECT_KNOWLEDGE",
    project="operation-jarvis",
    importance="normal",
    source="operation_jarvis"
)
```
- Automatically redacts secrets using regex patterns (`sk-`, `ghp_`, `AKIA`, etc.).
- Verifies that the target category does not exceed its storage budget.
- Updates the SQLite FTS5 full-text index immediately.

### 3.3 Non-Destructive Versioned Updates
The adapter adheres strictly to rule #4 ("Never automatically overwrite valuable existing information"):
- Overwrite requires an explicit `target_id_or_title` and mandatory `changelog` string explaining the revision.
- Previous versions and timestamps are tracked in the database metadata table.

### 3.4 Verification Through Retrieval
When a step involves storing or updating memory, `core/verification.py` runs a subsequent `memory_adapter.search(...)` to confirm that the record was indexed and is discoverable via full-text search before marking the step as verified.

---

## 4. CROSS-INTERFACE COMPATIBILITY

Both Google Antigravity and Qwen local can access this shared memory:
1. **Google Antigravity:** Connects via MCP Server (`local-memory` in `mcp_config.json` -> `mcp_server/memory_mcp_server.py`).
2. **Operation Jarvis Runtime:** Imports `LocalMemoryAdapter` directly with zero process overhead.
3. **PowerShell CLI:** Executable via `uv run python memory_cli.py <command>`.
4. **Voice Workstation:** Accessible via `BrainRouter` and Jarvis FastAPI bridge.
