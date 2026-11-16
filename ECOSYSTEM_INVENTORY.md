# OPERATION JARVIS — WORKSTATION ECOSYSTEM INVENTORY

**Document Version:** 1.0.0  
**Audit Date:** 2026-11-06  
**Auditor:** Operation Jarvis Systems Architect  
**Preservation Status:** 100% Intact — Zero Existing Configurations Modified or Overwritten  

---

## 1. INVENTORY SUMMARY

This document catalogs every discovered integration, model, protocol, MCP server, plugin, procedural skill, and voice component present on the Windows 11 workstation (`HP Victus 15-fa2382TX`).

---

## 2. LOCAL LARGE LANGUAGE MODELS (LLMs)

### 2.1 Primary Reasoning Model
- **Name:** `qwen3.5:9b`
- **Family:** Qwen 3.5 (Alibaba Cloud)
- **Parameters:** 9.0 Billion
- **Format / Quantization:** GGUF / `Q4_K_M`
- **Context Window:** 262,144 tokens (active slot: 8,192 tokens)
- **Capabilities:** Completion, Vision, Structured Tools, Native Thinking (`<think>`)
- **Server:** Ollama v0.40.13
- **Local Endpoint:** `http://127.0.0.1:11434`
- **Model Digest:** `5852b52876b93f88a1d3b8f6a9888e3f6f904a38dff024a18f28831f6cbc1048`
- **Installation Path:** `C:\Users\Akshay aravind .rv\.ollama\models`
- **Operational Status:** **ONLINE & ACTIVE** (Inference verified on RTX 4050 GPU, ~4.3 GB VRAM)

### 2.2 Secondary / Custom Model
- **Name:** `qwen-batman:latest`
- **Parent Model:** `qwen3.5:9b`
- **Parameters:** 9.0 Billion (`Q4_K_M`)
- **Digest:** `1cc48f681ece8428928b6183048e6c97cc308ed68b9c67f2c7e8246091fd4605`
- **Purpose:** Conversational partner personality for Batman dynamic
- **Operational Status:** **ONLINE & AVAILABLE** in Ollama catalog

---

## 3. PERSISTENT MEMORY INFRASTRUCTURE

- **Root Directory:** `C:\Users\Akshay aravind .rv\LOCAL_AI_MEMORY`
- **Total Budget:** 33.5 GB (35,972,768,240 bytes)
- **Primary Database:** `C:\Users\Akshay aravind .rv\LOCAL_AI_MEMORY\07_MEMORY_INDEX\memory.db`
- **Storage Sub-Systems:**
  1. `01_PERSONAL_PREFERENCES` (500 MB budget, 7 records active)
  2. `02_PROJECT_KNOWLEDGE` (5,120 MB budget, 6 records active)
  3. `03_CONVERSATION_ARCHIVES` (3,072 MB budget, 1,078 records active)
  4. `04_TECHNICAL_DOCUMENTATION` (10,240 MB budget, 3 records active)
  5. `05_RESEARCH_LIBRARY` (10,240 MB budget, 1 record active)
  6. `06_TEMPORARY_CACHE` (5,120 MB budget)
  7. `07_MEMORY_INDEX` (SQLite FTS5 + BM25 full text search virtual table)
  8. `08_BACKUPS` (Automated zip snapshots)
- **Engine Package:** `LOCAL_AI_MEMORY\engine` (`db.py`, `indexer.py`, `retriever.py`, `writer.py`, `monitor.py`, `importer.py`, `backup.py`, `categorizer.py`)
- **CLI Wrapper:** `memory_cli.py` (executed via `uv run python memory_cli.py`)
- **Operational Status:** **ONLINE & VERIFIED** (70.79 MB used, 0.21% budget utilization, healthy status)

---

## 4. MODEL CONTEXT PROTOCOL (MCP) SERVERS

Configuration Location: `C:\Users\Akshay aravind .rv\.gemini\config\mcp_config.json`

| Server Name | Transport Protocol | Startup Command | Arguments / Endpoint | Operational Status |
| :--- | :--- | :--- | :--- | :--- |
| **`local-memory`** | JSON-RPC 2.0 stdio | `uv.exe` | `run python ...\memory_mcp_server.py` | **OPERATIONAL** (Verified via stdio test) |
| **`playwright`** | JSON-RPC 2.0 stdio | `npx.cmd` | `-y @playwright/mcp@latest` | **OPERATIONAL** (CLI help and flags validated) |
| **`chrome-devtools`** | JSON-RPC 2.0 stdio | `npx.cmd` | `-y chrome-devtools-mcp@latest` | **OPERATIONAL** (Puppeteer/DevTools backend ready) |
| **`firecrawl`** | JSON-RPC 2.0 stdio | `npx.cmd` | `-y firecrawl-mcp` | **CONFIGURED** (Requires API key for paid crawls) |
| **`hyperframes`** | HTTP / SSE | Remote SSE | `https://mcp.heygen.com/mcp/hyperframes/` | **CONFIGURED** (Remote HeyGen endpoint) |
| **`perplexity`** | JSON-RPC 2.0 stdio | `npx.cmd` | `-y @perplexity-ai/mcp-server` | **CONFIGURED** (Requires `PERPLEXITY_API_KEY`) |

---

## 5. DESKTOP & ACCESSIBILITY AUTOMATION

- **Tool Name:** `agent-desktop` (Vercel Agent Desktop CLI)
- **Binary:** `agent-desktop-win32-x64.exe` (accessible via PATH as `agent-desktop`)
- **Platform Interface:** Native Windows UI Automation (UIA) Accessibility Tree
- **Capabilities:**
  - `snapshot`: Headless accessibility DOM capture with `@ref` IDs
  - `find`: Fast role/name/text selector queries
  - `screenshot`: Window PNG capture
  - `click`, `set-value`, `clear`, `focus`, `toggle`, `press`
  - `list-apps`, `list-windows`, `focus-window`, `launch`, `close-app`
- **Operational Status:** **ONLINE & VERIFIED** (UIA Tree snapshotting tested successfully)

---

## 6. VOICE INTEGRATION SUBSYSTEM

- **Root Location:** `C:\Users\Akshay aravind .rv\LOCAL_AI_MEMORY\engine\voice`
- **Dedicated Virtualenv:** `C:\Users\Akshay aravind .rv\LOCAL_AI_MEMORY\.venv_voice`
- **Components:**
  - **TTS Engine (`tts_engine.py`):** Kokoro-82M ONNX INT8 with British RP preset (`bm_george`), speed 1.0, 124 WPM; automatic fallback to SAPI5 (`Microsoft David Desktop`).
  - **STT Engine (`stt_engine.py`):** Faster-Whisper local speech recognition.
  - **Brain Router (`brain_router.py`):** Dual-routing logic for Qwen Local and Antigravity Cloud.
  - **UI Shells:** `desktop_voice_ui.py` (Tkinter GUI), `antigravity_voice.py`, `voice_cli.py`.
- **Operational Status:** **CONFIGURED & PRESERVED** (No modifications made; bridged via Jarvis API).

---

## 7. PROCEDURAL SKILLS REPOSITORY

- **Agent Skills Location:** `C:\Users\Akshay aravind .rv\.gemini\config\plugins\agent-skills\skills` (27 skills)
  - `agent-desktop`, `api-and-interface-design`, `browser-testing-with-devtools`, `ci-cd-and-automation`, `code-review-and-quality`, `code-simplification`, `constraint-driven-development`, `context-engineering`, `debugging-and-error-recovery`, `deprecation-and-migration`, `documentation-and-adrs`, `doubt-driven-development`, `frontend-ui-engineering`, `git-workflow-and-versioning`, `idea-refine`, `incremental-implementation`, `interview-me`, `observability-and-instrumentation`, `performance-optimization`, `persistent-memory`, `planning-and-task-breakdown`, `security-and-hardening`, `shipping-and-launch`, `source-driven-development`, `spec-driven-development`, `test-driven-development`, `using-agent-skills`.
- **Ponytail Skills Location:** `C:\Users\Akshay aravind .rv\.gemini\config\plugins\ponytail\skills` (5 skills)
  - `ponytail`, `ponytail-audit`, `ponytail-debt`, `ponytail-gain`, `ponytail-help`, `ponytail-review`.
- **Antigravity Customizations:** `C:\Users\Akshay aravind .rv\.gemini\antigravity-cli\builtin\skills\antigravity_guide`.
- **Operational Status:** **DISCOVERED & INDEXED** in Operation Jarvis `SkillRegistry`.

---

## 8. EXISTING WRAPPERS AND SHELL INTEGRATIONS

- `C:\Users\Akshay aravind .rv\.local\bin\qwen.ps1` / `qwen.cmd`: Invokes `uv run` on `LOCAL_AI_MEMORY\engine\qwen_chat.py`.
- `C:\Users\Akshay aravind .rv\.local\bin\qwen-raw.ps1` / `qwen-raw.cmd`: Invokes raw `ollama run qwen3.5:9b`.
- `C:\Users\Akshay aravind .rv\.gemini\bin\agy.exe`: Antigravity 2.0 CLI.
- **Operational Status:** **ALL 100% PRESERVED & FUNCTIONAL**.
