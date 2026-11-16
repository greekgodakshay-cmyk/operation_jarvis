# Operation JARVIS — Operations & Command Manual

**System:** Operation JARVIS & Antigravity Dual-Ecosystem Workstation  
**Hardware:** HP Victus 15-fa2382TX | Intel Core 5 210H | 24GB RAM | RTX 4050 6GB VRAM  
**Operating System:** Windows 11 Home 64-bit

---

## 1. Quick Command Reference

All launch commands are integrated into your PowerShell profile (`$PROFILE`) and `.local\bin` path:

```powershell
# 1. Launch Qwen Batman Coworker (Interactive text session)
qwen

# 2. Launch Qwen with Kokoro Voice enabled (Speaks responses automatically)
qwen /voice

# 3. Single-turn query with spoken response
qwen /voice "What are today's top technology headlines?"

# 4. Direct Ollama model access without memory layer
qwen-raw

# 5. Launch Antigravity 2.0 Principal Orchestrator CLI / TUI
agy

# 6. Launch Antigravity with JARVIS voice synthesis
agy /voice
```

---

## 2. Interactive REPL Slash Commands

When inside an interactive `qwen` terminal session (`Batman >`), the following slash commands are available:

### 2.1 Orchestrator & Multi-Agent Collaboration
- **/antigravity `<task>`:** Dispatches a complex architecture, multi-turn plan, code review, or deep verification task to Antigravity 2.0 Principal Orchestrator. Executes synchronous roundtrip with cryptographic task and handoff tracking.
  ```text
  Batman > /antigravity Review the DaVinci Resolve EDL generation pipeline and verify timeline bounds
  ```
- **/agents:** Displays all registered agents in the ecosystem, their runtime tiers, statuses, and capabilities (`antigravity`, `qwen-batman`, `continue-ide`, `security-auditor`, `research`, `test-engineer`).
- **/tools:** Lists all 55 discoverable workstation tools across native file ops, desktop automation, internet gateway, skillet packages, and memory adapters.

### 2.2 Task Management & Autonomous Execution
- **/tasks:** Lists recent persistent tasks stored in SQLite database.
- **/task `<task_id>`:** Displays detailed task inspection: objective, step execution history, verifications, final outcome, and errors.
- **/task `<objective>`** or **/execute `<objective>`:** Launches autonomous multi-step execution loop where Qwen or JARVIS plans, selects tools, checks observations, and synthesizes results.
- **/resume `<task_id>`:** Resumes an interrupted, paused, or blocked task.

### 2.3 Security & Human Approval Gate
- **/approve `<task_id> [approval_request_id]`:** Explicitly approves a Level 3 restricted action (e.g., sending emails, canceling calendar events, executing high-consequence system commands).
- **/trace `<task_id>`:** Displays the immutable cryptographic SHA-256 audit trail for all operations executed under that task.

### 2.4 Voice & Speech Control
- **/voice on:** Enables Kokoro ONNX spoken output for all subsequent responses.
- **/voice off:** Disables spoken output (silent text-only mode).
- **/voice status:** Displays the current voice engine, active voice (`bm_george`), and audio availability.

### 2.5 Persistent Memory Management
- **/memory search `<query>`:** Search SQLite FTS5 database for past architectural choices, workstation facts, or context.
- **/memory store `<title> | <content> | [project]`:** Direct storage of a verified memory record.
- **/memory update `<id> | <updated content>`:** Update an existing memory with version tracking.
- **/memory count:** Displays total verified records in SQLite FTS5 index.
- **/store `<title> | <content>`:** Shorthand for memory storage.
- **/update `<id> | <content>`:** Shorthand for memory update.

### 2.6 Desktop & Workstation Health
- **/desktop `<subcommand>`:** Executes Vercel Agent Desktop CLI commands (e.g., `/desktop snapshot --app notepad -i --compact`, `/desktop list-windows`).
- **/status:** Displays real-time hardware telemetry: CPU, GPU VRAM allocation, RAM utilization, Ollama daemon status, memory database record count, and agent health.
- **/help:** Displays the in-terminal command cheat sheet.

---

## 3. Tool Calling Syntax for Autonomous Coworkers

Qwen and autonomous subagents invoke tools using the structured JSON tool call block:

```text
[TOOL_CALL: {"tool": "<tool_name>", "args": {<arguments>}}]
```

### Common Tool Examples:
1. **Live News Search:**
   `[TOOL_CALL: {"tool": "search_news", "args": {"query": "AI research", "region": "IN", "max_results": 3}}]`
2. **Read-Only Web Fetch:**
   `[TOOL_CALL: {"tool": "web_fetch", "args": {"url": "https://en.wikipedia.org/wiki/Artificial_intelligence"}}]`
3. **Antigravity Bridge:**
   `[TOOL_CALL: {"tool": "antigravity_bridge", "args": {"title": "Code Review", "description": "Review orchestrator.py for race conditions"}}]`
4. **Desktop Automation:**
   `[TOOL_CALL: {"tool": "desktop", "args": {"subcommand": "snapshot --compact -i"}}]`
5. **Memory Search:**
   `[TOOL_CALL: {"tool": "memory_search", "args": {"query": "Victus hardware profile"}}]`
6. **File Operations:**
   `[TOOL_CALL: {"tool": "read_file", "args": {"path": "C:\\Users\\Akshay aravind .rv\\package.json", "start_line": 1, "end_line": 50}}]`

---

## 4. Maintenance & Troubleshooting

### 4.1 Ollama Offline
- **Symptom:** Terminal outputs `Error communicating with local Ollama service`.
- **Automatic Recovery:** The `qwen` launcher and `qwen_chat.py` automatically start Ollama in the background via `wscript.exe` with zero console flashing and wait up to 15 seconds for socket readiness.
- **Manual Command:** In a separate PowerShell terminal, run `ollama serve`.

### 4.2 Desktop Automation Permissions (`agent-desktop`)
- **Symptom:** `agent-desktop` reports `PERM_DENIED: private file DACL grants an untrusted principal`.
- **Resolution:** Run the following command to strip sandbox ACEs:
  ```powershell
  icacls "C:\Users\Akshay aravind .rv\.agent-desktop" /remove "CodexSandboxUsers" /t
  ```

### 4.3 Database Backup & Integrity
- All memories, tasks, and audit logs are safely stored in:
  - `C:\Users\Akshay aravind .rv\LOCAL_AI_MEMORY\07_MEMORY_INDEX\memory.db`
  - `C:\Users\Akshay aravind .rv\operation_jarvis\data\document_index.db`
  - `C:\Users\Akshay aravind .rv\operation_jarvis\data\tasks.db`
- WAL mode is permanently enabled. Never delete or drop tables from `memory.db`.
- Backups are stored in `LOCAL_AI_MEMORY\07_MEMORY_INDEX\backups\`.
