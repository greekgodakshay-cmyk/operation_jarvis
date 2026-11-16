# OPERATION JARVIS — OPERATIONAL TROUBLESHOOTING GUIDE

**Document Version:** 1.0.0  
**Target Environment:** Windows 11 | Ollama | FastAPI Port 8000  

---

## 1. COMMON ISSUES & RESOLUTIONS

### 1.1 Ollama Service Offline / Port 11434 Inaccessible

**Symptom:**
```
LLMClientError: Chat failed after 3 attempts: Unable to connect to http://127.0.0.1:11434
```

**Root Cause:**
The Ollama server process is not running. On Windows, if Ollama GUI is not running in the system tray or session 0, the server must be started as a service.

**Resolution:**
1. Start Ollama in a separate terminal:
   ```powershell
   ollama serve
   ```
2. Or run the Jarvis startup script which handles Ollama automatically:
   ```powershell
   .\scripts\start_jarvis.ps1
   ```
3. Verify connection:
   ```powershell
   Test-NetConnection -ComputerName 127.0.0.1 -Port 11434
   ```

---

### 1.2 Task Paused in `WAITING_FOR_APPROVAL`

**Symptom:**
```
Task Status: WAITING_FOR_APPROVAL
[⚠️ ACTION REQUIRED] Restricted operation 'Stop-Process' requires human confirmation.
```

**Root Cause:**
A step in the execution plan triggered a **Level 3 Restricted Policy Gate** (e.g., file deletion, system modification, destructive shell command). The policy engine safely intercepted the call to protect workstation integrity.

**Resolution:**
1. Inspect the pending approval details:
   ```powershell
   python cli/jarvis_cli.py status <task_id>
   ```
2. Grant approval if safe:
   ```powershell
   python cli/jarvis_cli.py approve <task_id> <request_id>
   ```
3. Or deny the action to abort the dangerous step:
   ```powershell
   python cli/jarvis_cli.py approve <task_id> <request_id> --deny
   ```

---

### 1.3 Sandbox Boundary & Path Jail Violation

**Symptom:**
```
PathJailViolation: Sandbox Boundary Violation: Path 'C:\Windows\System32\...' is outside allowed workspaces.
```

**Root Cause:**
The model or tool attempted to read, create, or modify a file outside the authorized workspace roots (`operation_jarvis`, `LOCAL_AI_MEMORY`, user home directory) or inside a protected Windows directory (`C:\Windows`, `C:\Program Files`).

**Resolution:**
- Direct the agent to write artifacts strictly within project directories, e.g.:
  `C:\Users\Akshay aravind .rv\operation_jarvis\data\` or `LOCAL_AI_MEMORY\`.
- The agent self-correction engine will automatically attempt to list and use the local directory on the next retry.

---

### 1.4 Port 8000 Conflict (FastAPI Server)

**Symptom:**
```
[Errno 10048] error while attempting to bind on address ('127.0.0.1', 8000): only one usage of each socket address is normally permitted
```

**Root Cause:**
A previous instance of Uvicorn or another local dev server is currently occupying port 8000.

**Resolution:**
1. Run the shutdown script:
   ```powershell
   .\scripts\stop_jarvis.ps1
   ```
2. Or forcefully terminate conflicting python processes on port 8000:
   ```powershell
   Get-Process -Name "*python*" | Where-Object { $_.CommandLine -like "*api.app:app*" } | Stop-Process -Force
   ```

---

### 1.5 GPU VRAM Contention / Out-of-Memory

**Symptom:**
Inference slows down significantly (< 1 token/sec) or Ollama fails back to CPU runner.

**Root Cause:**
The laptop GPU has 6,141 MiB (6.0 GB) of dedicated VRAM. Loading multiple LLMs simultaneously (e.g. running another Ollama model or a local diffusion model) will exceed 6 GB VRAM and force system RAM paging.

**Resolution:**
1. Check GPU memory:
   ```powershell
   nvidia-smi
   ```
2. Unload inactive Ollama models:
   ```powershell
   ollama stop <other_model>
   ```
3. Operation Jarvis is strictly pinned to `qwen3.5:9b` (`Q4_K_M`) which consumes ~4.3 GB VRAM, safely leaving 1.8 GB free.

---

### 1.6 MCP Server Unreachable / Node Execution Failures

**Symptom:**
MCP tools report timeouts or missing npm packages.

**Resolution:**
1. Verify Node and npx versions:
   ```powershell
   node -v; npx -v
   ```
2. Test Playwright MCP directly:
   ```powershell
   npx -y @playwright/mcp@latest --help
   ```
3. Test Chrome DevTools MCP directly:
   ```powershell
   npx -y chrome-devtools-mcp@latest --help
   ```
