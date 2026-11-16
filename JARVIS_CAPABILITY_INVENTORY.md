# Operation JARVIS: Runtime & Capability Inventory

**System:** Operation JARVIS Local Autonomous Agent Runtime  
**Root Path:** `C:\Users\Akshay aravind .rv\operation_jarvis`  
**Verification Date:** 2026-11-06  
**Primary Model Engine:** Ollama `qwen3.5:9b` (Q4_K_M) at `http://127.0.0.1:11434`

---

## 1. System Overview

Operation JARVIS is a persistent, tool-using, self-correcting, permission-controlled agent runtime built specifically for Windows 11. It provides autonomous multi-step objective execution, continuous verification, memory grounding, and defense-in-depth safety controls.

---

## 2. Core Execution Engine

Located in `operation_jarvis/core/`:

| Module | Class / Component | Responsibilities & Capabilities |
| :--- | :--- | :--- |
| **`dynamic_planner.py`** | `DynamicPlanner` | Decomposes high-level objectives into verifiable steps. Queries local memory (`memory_search`) and indexes matching skills (`find_relevant_skills`) to ground the plan. |
| **`orchestrator.py`** | `AgentOrchestrator` | Coordinates step-by-step execution loop, evaluates prerequisites, triggers verification gates, and manages task lifecycle states (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `WAITING_APPROVAL`). |
| **`self_correction.py`** | `SelfCorrectionEngine` | Diagnoses failed step executions, inspects tool error messages, and formulates alternate tool arguments or remediation steps (up to 3 retries per step). |
| **`verification.py`** | `VerificationEngine` | Validates post-execution truth. Verifies file existence, verifies exact content substrings, inspects subprocess return codes, and prevents silent failure hallucinations. |
| **`llm_client.py`** | `OllamaClient` | Strongly-typed client for local Ollama API with timeout management, fallback model support (`qwen-batman:latest`), JSON extraction, and telemetry. |
| **`types.py`** | Core Data Models | Pydantic v2 schemas for `TaskPlan`, `ExecutionStep`, `ToolCall`, `ToolResult`, `VerificationResult`, `ApprovalRequest`, and `PermissionLevel`. |

---

## 3. Defense-in-Depth Security Framework

Located in `operation_jarvis/security/`:

| Security Layer | Implementation | Protection Enforcement |
| :--- | :--- | :--- |
| **Path Jailing** | `path_jail.py` | Restricts file access strictly to allowed roots (`C:\Users\Akshay aravind .rv`, `operation_jarvis`, `LOCAL_AI_MEMORY`). Blocks directory traversal (`..`) and Windows protected directories (`C:\Windows`, `C:\Program Files`, `$Recycle.Bin`). |
| **Command Validation** | `command_validator.py` | Inspects PowerShell commands prior to execution. Classifies into Level 1, 2, or 3. Blocks destructive system tampering (`Format`, `Diskpart`, `Set-MpPreference`, Defender disabling, recursive wipe). |
| **Policy Engine** | `policy_engine.py` | Enforces 3-tier authorization model: Level 1 (Safe, auto-run), Level 2 (Controlled, logged), Level 3 (Restricted, requires user approval token). |
| **Secret Redaction** | `secret_redactor.py` | Sanitizes API tokens, SSH keys, Bearer tokens, GitHub personal access tokens (`ghp_`), and passwords from logs, traces, and LLM prompts. |
| **Prompt Injection Guard** | `injection_guard.py` | Wraps untrusted external outputs (web scrapes, emails, tool stdout) in defensive isolation boundaries (`<untrusted_external_content>`) to prevent prompt hijacking. |

---

## 4. Capability & Tool Registry

Located in `operation_jarvis/registry/`:

### 4.1 Native Tools (14 Capabilities)
- **Filesystem Tools:** `read_file` (Level 1), `list_dir` (Level 1), `write_file` (Level 2), `edit_file` (Level 2).
- **Command Tools:** `run_command` (Level 2).
- **Verification Tools:** `verify_file_exists` (Level 1), `verify_file_content` (Level 1), `verify_test_suite` (Level 2).
- **Memory Integration Tools:** `memory_search` (Level 1), `memory_store` (Level 2), `memory_update` (Level 2), `memory_status` (Level 1).
- **Desktop Automation Tools:** `desktop_snapshot` (Level 1), `desktop_list_apps` (Level 1).
- **Procedural Skill Discovery Tools:** `search_skills` (Level 1), `read_skill` (Level 1).

### 4.2 Dynamic Skill Adapter (`skill_adapter.py`)
- Dynamically scans `C:\Users\Akshay aravind .rv\.gemini\config\plugins` and builtin skills on startup.
- Discovers **107 procedural skills** without duplicating markdown files.
- Provides semantic keyword ranking (`find_relevant_skills`) for zero-overhead progressive disclosure.

---

## 5. Storage, Audit, and Persistence

- **Task Database:** SQLite database at `data/jarvis_tasks.db` storing complete task state, steps, tool calls, and verification records. Survives terminal restarts.
- **Audit Logger:** Append-only JSON Lines ledger at `logs/audit_trail.jsonl` recording every tool call, permission evaluation, approval request, and exit code.
- **Trace Logger:** Per-task execution traces stored in `logs/traces/<task_id>.json`.

---

## 6. User Interfaces

- **Qwen CLI Wrapper:** `qwen "objective"` routes through dual-path logic (`is_action_objective`). Action requests invoke the JARVIS orchestrator; conversational queries run fast-path Ollama generation.
- **Troubleshooting CLI:** `qwen-raw` provides direct unmediated Ollama prompt/response for diagnostics.
- **Voice Pipeline:** Kokoro-82M ONNX TTS pipeline running in `.venv_voice` with `bm_george` voice preset and SAPI5 fallback.
- **FastAPI Service:** Exposes REST endpoints (`/api/v1/tasks`, `/api/v1/voice/query`, `/api/v1/approve`) at `http://127.0.0.1:8000`.
