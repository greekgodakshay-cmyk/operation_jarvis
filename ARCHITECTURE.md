# OPERATION JARVIS — SYSTEM ARCHITECTURE SPECIFICATION

**Document Version:** 1.0.0  
**Target Environment:** HP Victus 15-fa2382TX | Intel Core 5 210H | 24 GB DDR5 | NVIDIA RTX 4050 6GB VRAM | Windows 11  
**Project Directory:** `C:\Users\Akshay aravind .rv\operation_jarvis`  

---

## 1. ARCHITECTURAL OVERVIEW

Operation Jarvis transforms the local AI environment from an isolated chat endpoint into an autonomous, stateful, persistent, tool-using, and permission-controlled agent runtime.

The system decouples reasoning from execution, placing a strict policy enforcement, verification, and durability barrier between model decisions and system actions.

```
+---------------------------------------------------------------------------------------+
|                                    USER INTERFACES                                    |
|   +--------------------------+  +--------------------------+  +-------------------+   |
|   |   FastAPI REST API / UI  |  |     Unified CLI Tool     |  |   Jarvis Voice    |   |
|   |     (Port 8000)          |  |     (jarvis_cli.py)      |  |   (BrainRouter)   |   |
|   +--------------------------+  +--------------------------+  +-------------------+   |
+-------------------------------------------+-------------------------------------------+
                                            |
                                            v
+---------------------------------------------------------------------------------------+
|                            AGENT ORCHESTRATOR & LIFECYCLE                             |
|  +--------------------+   +---------------------+   +-------------------------------+  |
|  | Goal Interpretation|-->| Dynamic Planner     |-->| Task State Machine (SQLite)   |  |
|  +--------------------+   +---------------------+   +-------------------------------+  |
|                                     |                                                  |
|                                     v                                                  |
|  +--------------------+   +---------------------+   +-------------------------------+  |
|  | Bounded Retries    |<--| Execution Loop      |-->| Observation & Verification    |  |
|  +--------------------+   +---------------------+   +-------------------------------+  |
+-------------------------------------------+-------------------------------------------+
                                            |
                         +------------------+------------------+
                         |                                     |
                         v                                     v
+------------------------------------+    +---------------------------------------------+
|    QWEN 3.5 9B (OLLAMA ENGINE)     |    |        DEFENSE-IN-DEPTH POLICY ENGINE       |
|  - Endpoint: 127.0.0.1:11434       |    |  +---------------------------------------+  |
|  - Model: qwen3.5:9b (Q4_K_M)      |    |  | Level 1: SAFE (Inspection / Read)     |  |
|  - Context: 262k                   |    |  | Level 2: CONTROLLED (Jailed Scripts)  |  |
|  - GPU VRAM: ~4.3 GB (RTX 4050)    |    |  | Level 3: RESTRICTED (Human Approval)  |  |
|  - Thinking token extractor        |    |  +---------------------------------------+  |
|  - Structured JSON plan parser     |    |  - Canonical Path Jailing                   |  |
+------------------------------------+    |  - Command Blacklist & AST Validation       |  |
                                          |  - Credential Redaction Engine              |  |
                                          |  - Prompt Injection Boundary Delimiters    |  |
                                          +---------------------------------------------+
                                                               |
                                                               v
+---------------------------------------------------------------------------------------+
|                                  CAPABILITY REGISTRY                                  |
|  +------------------------+  +--------------------------+  +------------------------+ |
|  |     NATIVE TOOLS       |  |     MEMORY ADAPTER       |  |    EXTERNAL MCPs       | |
|  |  - read_file           |  |  - SQLite FTS5 Search    |  |  - Playwright MCP      | |
|  |  - write_file          |  |  - Category Budgeting    |  |  - Chrome DevTools     | |
|  |  - edit_file           |  |  - Verified Memory Store |  |  - Firecrawl           | |
|  |  - list_dir            |  |  - Versioned Updates     |  |  - Perplexity          | |
|  |  - run_command         |  +--------------------------+  +------------------------+ |
|  |  - verify_file_exists  |  +--------------------------+  +------------------------+ |
|  |  - verify_file_content |  |     DESKTOP ADAPTER      |  |     SKILL REGISTRY     | |
|  |  - verify_test_suite   |  |  - agent-desktop CLI     |  |  - 27 Agent Skills     | |
|  +------------------------+  |  - Windows Accessibility |  |  - Procedural Guidance | |
|                              +--------------------------+  +------------------------+ |
+---------------------------------------------------------------------------------------+
                                            |
                                            v
+---------------------------------------------------------------------------------------+
|                                    VERIFIED RESULT                                    |
|   +-------------------------------------------------------------------------------+   |
|   | 1. Real Artifact & Hash Verification (File presence, size, test passing code) |   |
|   | 2. Durable Task State Update in SQLite DB (Status: COMPLETED / FAILED)        |   |
|   | 3. Tamper-evident Audit Trail Entry (Rolling SHA-256 Digest in JSONL)         |   |
|   | 4. Verified Insight Ingestion into LOCAL_AI_MEMORY (when applicable)          |   |
|   +-------------------------------------------------------------------------------+   |
+---------------------------------------------------------------------------------------+
```

---

## 2. COMPONENT DECOMPOSITION

### 2.1 Agent Orchestrator (`core/orchestrator.py`)
- Coordinates the complete autonomous lifecycle without human polling.
- Enforces strict execution state transitions:
  `PENDING` -> `PLANNING` -> `RUNNING` -> `WAITING_FOR_APPROVAL` -> `RECOVERING` -> `COMPLETED` / `FAILED` / `CANCELLED`.
- Supports graceful task interruption and durable resumption.

### 2.2 LLM Reasoning Client (`core/llm_client.py`)
- Interfaces with Ollama at `http://127.0.0.1:11434`.
- Uses `qwen3.5:9b` as the primary reasoning engine.
- Filters `<think>...</think>` internal cognitive chains while preserving structured output extraction.
- Automatic backoff and retry on model load or timeout.

### 2.3 Dynamic Planner (`core/dynamic_planner.py`)
- Retrieves contextual memories from `LOCAL_AI_MEMORY` using BM25 FTS5 before formulating a plan.
- Matches user objectives against 27 installed skills to inject procedural best practices.
- Emits schema-validated multi-step JSON execution plans.

### 2.4 Evidence-Based Verifier (`core/verification.py`)
- Eliminates hallucinations by requiring verifiable physical evidence:
  - Files created must exist on disk and have non-zero size.
  - Edits must be verified by reading back the modified contents.
  - Tests must return zero exit codes.
  - Memory updates must be verified via subsequent FTS5 database lookups.
- Prevents false completion claims.

### 2.5 Defense-in-Depth Security Engine (`security/`)
- Enforces a 3-tier permission hierarchy:
  - **Level 1 (Safe):** Read-only inspection, search, directory listings.
  - **Level 2 (Controlled):** File writing, editing within authorized workspaces, running unit tests.
  - **Level 3 (Restricted):** Deletions, service termination, system modifications — strictly gated behind user approval tokens.
- **Path Jailing:** Prevents directory traversal out of permitted project roots; strictly denies access to Windows system directories.
- **Command Validator:** Scans shell commands for destructive patterns (disk formatting, firewall modifications, defender tampering).
- **Prompt Injection Guard:** Neutralizes untrusted external text with boundary delimiters and escaped tokens.
- **Secret Redactor:** Automatically masks API keys, JWTs, and passwords in all logs and outputs.

### 2.6 Persistent Task Database (`storage/task_db.py`)
- Uses SQLite with WAL mode (`data/jarvis_tasks.db`).
- Tracks task objectives, plans, step results, approvals, and completion outcomes.
- Enables offline task resumption without repeating destructive operations.

### 2.7 Audit & Tracing Engine (`storage/audit_logger.py`)
- Records structured JSONL logs for every event.
- Incorporates rolling SHA-256 hashes (`prev_hash` -> `hash`) to ensure tamper-evident records.
- Creates per-task trace files in `logs/traces/{task_id}.jsonl`.

---

## 3. INTEGRATION CONTRACTS

### 3.1 Memory Integration Contract
- Connects directly to `LOCAL_AI_MEMORY` at `C:\Users\Akshay aravind .rv\LOCAL_AI_MEMORY`.
- Uses native `engine.db.MemoryDB`, `engine.retriever.MemoryRetriever`, and `engine.writer.MemoryWriter`.
- Preserves all 6 storage categories, logical budgets (33.5 GB), and secret redactor configurations.

### 3.2 Voice Integration Contract
- Exposes `POST /api/v1/voice/query` and `POST /api/v1/chat`.
- Enables `LOCAL_AI_MEMORY\engine\voice\brain_router.py` to route voice requests directly to the autonomous agent runtime.
- Respects the Kokoro-82M ONNX British RP voice preset (`bm_george`) and SAPI5 fallback.

### 3.3 Google Antigravity & MCP Contract
- Reuses existing configuration in `C:\Users\Akshay aravind .rv\.gemini\config\mcp_config.json`.
- Discovers Playwright, Chrome DevTools, Firecrawl, Perplexity, and Local Memory servers.
- Exposes unified capabilities through `registry/capability_registry.py`.
