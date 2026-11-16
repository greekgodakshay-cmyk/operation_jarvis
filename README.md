# OPERATION JARVIS — LOCAL AGENTIC AI RUNTIME

**Workstation:** HP Victus 15-fa2382TX | Intel Core 5 210H | 24 GB DDR5 | NVIDIA RTX 4050 Laptop GPU (6GB VRAM)  
**Operating System:** Microsoft Windows 11 (x64)  
**Primary Reasoning Engine:** Qwen 3.5 9B (`Q4_K_M`) via Ollama (`http://127.0.0.1:11434`)  
**Project Directory:** `C:\Users\Akshay aravind .rv\operation_jarvis`  

---

## 1. PROJECT SUMMARY

Operation Jarvis transforms the local AI environment from an isolated chat endpoint into an autonomous, stateful, persistent, tool-using, self-correcting, and permission-controlled AI system.

Unlike simple wrapper scripts or theoretical demonstrations, Operation Jarvis is a genuine, production-grade agent runtime with:
1. **Decoupled Architecture:** Clean separation between LLM reasoning, dynamic planning, task state, policy enforcement, tool execution, and artifact verification.
2. **Persistent Task Database:** SQLite-backed durable task lifecycle (`PENDING` -> `PLANNING` -> `RUNNING` -> `WAITING_FOR_APPROVAL` -> `RECOVERING` -> `COMPLETED` / `FAILED` / `CANCELLED`).
3. **Defense-in-Depth Policy Engine:** Three-level permission hierarchy (Level 1 Safe, Level 2 Controlled, Level 3 Restricted) with path jailing, shell command sanitization, credential redaction, and prompt injection defense.
4. **Physical Verification Engine:** Requires evidence (file presence, size, substring matching, exit codes, FTS5 index lookups) before declaring completion.
5. **Ecosystem Preservation:** 100% preserves existing `LOCAL_AI_MEMORY` (33.5 GB budget), 27 agent skills, MCP configurations (`playwright`, `chrome-devtools`, `firecrawl`), and the Kokoro-82M ONNX voice workstation.

---

## 2. QUICKSTART COMMANDS

### 2.1 Starting the Agent Runtime
To start Ollama (if offline) and launch the FastAPI server on port 8000:
```powershell
# In PowerShell:
.\scripts\start_jarvis.ps1

# Or in Command Prompt:
scripts\start_jarvis.bat
```
- **API URL:** `http://127.0.0.1:8000`
- **Interactive Swagger Docs:** `http://127.0.0.1:8000/docs`
- **Health Endpoint:** `http://127.0.0.1:8000/api/v1/health`

### 2.2 Stopping the Agent Runtime
```powershell
# In PowerShell:
.\scripts\stop_jarvis.ps1

# Or in Command Prompt:
scripts\stop_jarvis.bat
```

---

## 3. UNIFIED CLI USAGE (`cli/jarvis_cli.py`)

Execute commands using the project's virtual environment:

```powershell
$py = "C:\Users\Akshay aravind .rv\operation_jarvis\.venv\Scripts\python.exe"
```

### 3.1 Check System Health & Capabilities
```powershell
& $py cli/jarvis_cli.py health
```

### 3.2 Submit an Objective
```powershell
& $py cli/jarvis_cli.py submit "Analyze current storage utilization and create a status report in data/status.txt"
```

### 3.3 Inspect Task Status & Verification Evidence
```powershell
& $py cli/jarvis_cli.py status <task_id>
```

### 3.4 List Recent Tasks
```powershell
& $py cli/jarvis_cli.py list
```

### 3.5 Resume an Interrupted Task
```powershell
& $py cli/jarvis_cli.py resume <task_id>
```

### 3.6 Approve or Deny a Level 3 Restricted Action
When a task enters `WAITING_FOR_APPROVAL`:
```powershell
# Grant approval and resume:
& $py cli/jarvis_cli.py approve <task_id> <request_id>

# Deny action:
& $py cli/jarvis_cli.py approve <task_id> <request_id> --deny
```

### 3.7 Inspect Execution Trace & Rolling Audit Trail
```powershell
& $py cli/jarvis_cli.py trace <task_id>
```

---

## 4. FASTAPI REST API SPECIFICATION

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/tasks` | Submit an objective (synchronous or background execution) |
| `GET` | `/api/v1/tasks` | List recent tasks with optional status filtering |
| `GET` | `/api/v1/tasks/{id}` | Retrieve complete task details, plan, and verifications |
| `POST` | `/api/v1/tasks/{id}/resume` | Resume interrupted task or proceed with approval token |
| `POST` | `/api/v1/tasks/{id}/cancel` | Safely cancel a running task |
| `POST` | `/api/v1/tasks/{id}/approve` | Resolve pending Level 3 approval request |
| `GET` | `/api/v1/tasks/{id}/traces` | Stream immutable execution traces with SHA-256 rolling hashes |
| `GET` | `/api/v1/health` | Comprehensive health check (LLM, GPU, Memory, System) |
| `GET` | `/api/v1/tools` | Enumerate all registered capabilities and permission levels |
| `POST` | `/api/v1/chat` | Direct conversation with Qwen 3.5 augmented with memory retrieval |
| `POST` | `/api/v1/voice/query` | Native voice endpoint compatible with `brain_router.py` |
| `GET` | `/api/weather` | Authoritative live weather observations & forecasts via Open-Meteo |
| `GET` | `/api/v1/weather` | Versioned live weather endpoint with geocoding & caching |

---

## 5. LIVE WEATHER INTELLIGENCE (PART A)

Operation JARVIS integrates Open-Meteo's geocoding and forecast services into the shared runtime:
- **No API Key Required**: Fully functional, free-tier meteorological telemetry.
- **Geocoding & Location Resolution**: Resolves explicit city names (e.g. "Tokyo", "London", "Bengaluru") with coordinates and local timezone. Defaults to user's workstation profile (`Bengaluru, Karnataka, India`, timezone `Asia/Kolkata`).
- **Meteorological Observations**: Real-time temperature (°C), feels-like apparent temperature (°C), WMO weather condition descriptions, relative humidity (%), wind speed (km/h), precipitation (mm), and rain probability (%).
- **Multi-Day Forecasting**: Structured today and tomorrow forecast breakdowns.
- **Strict Evidence & Caching**: 10-minute in-memory caching with explicit provenance indicators (`[Live observation]` vs `[Cached observation from HH:MM]`). Never fabricates weather data on network failure.

---

## 6. MODULAR MULTI-AGENT ORCHESTRATION (PART B)

The orchestrator coordinates 11 specialized agent execution roles backed by the local Qwen model:
- `orchestrator`: High-level workflow planning, task decomposition, and final synthesis.
- `researcher`: Live news retrieval, arXiv preprints, CVE vulnerability lookups, and weather intelligence.
- `coder`: Multi-file patching, repository mapping, syntax verification, and bug fixing.
- `workspace`: Directory structure discovery, file searches, and workspace inventory.
- `tester`: Automated test suite execution, failure diagnosis, and outcome assertions.
- `documenter`: Architectural documentation, README generation, ADR records, and API specs.
- `git`: Git repository inspection, staging, committing, and GitHub remote synchronization.
- `system_ops`: Desktop automation, host diagnostics, and PowerShell execution.
- `memory`: Local persistent memory retrieval (SQLite FTS5, 1,102 memories) and ChatGPT archive search.
- `reviewer`: Independent post-execution verification audits and artifact checks.

---

## 7. GIT & GITHUB SYNCHRONIZATION

- **Local Repository**: Standalone Git repository anchored at `C:\Users\Akshay aravind .rv\operation_jarvis` on branch `main`.
- **Remote Synchronization**: Synchronized with public GitHub repository [`greekgodakshay-cmyk/operation_jarvis`](https://github.com/greekgodakshay-cmyk/operation_jarvis).
- **Authentication**: Authenticated via Windows Credential Manager (`git:https://github.com`) without exposing tokens in logs or code.
- **Zero-Leak Security**: Strict `.gitignore` excludes all local databases (`*.db`), ChatGPT archives, personal memory, virtual environments (`.venv/`), and environment files (`.env`).

---

## 8. DOCUMENTATION DIRECTORY

For in-depth architectural and operational specifications, consult:
- [`ARCHITECTURE.md`](ARCHITECTURE.md): Comprehensive system design and lifecycle state machine.
- [`SECURITY_MODEL.md`](SECURITY_MODEL.md): Defense-in-depth policy rules, path jail, and injection guards.
- [`TOOL_REGISTRY.md`](TOOL_REGISTRY.md): Catalog of native tools, assertions, MCPs, and skills.
- [`MEMORY_INTEGRATION.md`](MEMORY_INTEGRATION.md): Integration details with `LOCAL_AI_MEMORY` (33.5 GB).
- [`RESOURCE_BENCHMARK.md`](RESOURCE_BENCHMARK.md): Hardware utilization profiles (CPU, RAM, RTX 4050 VRAM).
- [`ECOSYSTEM_INVENTORY.md`](ECOSYSTEM_INVENTORY.md): Catalog of all pre-existing workstation components.
- [`INTEGRATION_COMPATIBILITY_REPORT.md`](INTEGRATION_COMPATIBILITY_REPORT.md): Compatibility analysis and authorization tiers.
- [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md): Remediation runbooks for common operational scenarios.
- [`TEST_REPORT.md`](TEST_REPORT.md): Results from the 12-point automated evaluation suite.
