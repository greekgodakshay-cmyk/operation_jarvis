# TOOLKIT INSTALLATION INVENTORY

**System:** HP Victus | Windows 11 Home | Operation JARVIS  
**Date:** November 6, 2026  
**Auditor:** Principal AI Systems Architect  

---

## 1. Cloned Repositories Inventory

All repositories were cloned to `C:\Users\Akshay aravind .rv\operation_jarvis\data\repo_eval\final_toolkit\`:

| Name | Source URL | Commit SHA | Version | On-Disk Path | Status |
|---|---|---|---|---|---|
| **tracelet** | `https://github.com/jnMetaCode/tracelet` | `eea4c10d03ca63582c64e34880219c5042eee5ce` | 0.3.2 | `...\final_toolkit\tracelet` | INSTALLED + CONNECTED |
| **skillet** | `https://github.com/jnMetaCode/skillet` | `b972e3dc28da0a0c94b6c4ec56a07ac491f966e8` | 0.1.2 | `...\final_toolkit\skillet` | INSTALLED + CONNECTED |
| **promptfoo** | `https://github.com/promptfoo/promptfoo` | `715e929298130cc32a6eab895f056ac32d0f15b4` | 0.125.1 | `...\final_toolkit\promptfoo` | INSTALLED + CONNECTED |
| **agentdojo** | `https://github.com/ethz-spylab/agentdojo` | `089ed468cf3ed0322acc66b0211f26d9d90dbf60` | 0.1.35 | `...\final_toolkit\agentdojo` | INSTALLED + CONNECTED |
| **engram** | `https://github.com/jnMetaCode/engram` | `b32c272648964ca8b692b0a70e09458197b5b3cb` | 0.3.1 | `...\final_toolkit\engram` | EVALUATED + PRESERVED SQLITE |
| **local-agent-toolkit** | `https://github.com/jnMetaCode/local-agent-toolkit` | `eb2779ebd05151c468f3ee0d094f40101cb58db0` | — | `...\final_toolkit\local-agent-toolkit` | EVALUATED + REFERENCE ONLY |
| **unslop** | `https://github.com/heydamir/unslop` | `a6f121eee5f29c2f74976b75456feae8b66afb3a` | — | `...\final_toolkit\unslop` | INSTALLED + CONNECTED |
| **localclaw** | `https://github.com/DB-Doo/localclaw` | `92b77c081a3da1ddcbaff87bb53b98bf9b02e5a4` | — | `...\final_toolkit\localclaw` | EVALUATED + ARCHITECTURE ADOPTED |

---

## 2. Installed Skills & Plugin Paths

| Skill Name | Package Source | Installation Location | Discoverable Antigravity | Discoverable Qwen |
|---|---|---|---|---|
| **unslop** | `heydamir/unslop` (CC BY 4.0) | `C:\Users\Akshay aravind .rv\.gemini\config\plugins\unslop\skills\unslop` | YES (`SkillRegistry` discovered) | YES (Shared plugins directory) |
| **changelog** | `jnMetaCode/skillet` (MIT) | `C:\Users\Akshay aravind .rv\.gemini\config\plugins\skillet_skills\skills\changelog` | YES (`SkillRegistry` discovered) | YES (`skillet_list` tool) |

---

## 3. MCP Server Registrations

File: `C:\Users\Akshay aravind .rv\.gemini\config\mcp_config.json`

| MCP Server | Command | Arguments | Transport | Status |
|---|---|---|---|---|
| **skillet** | `node` | `["C:\\Users\\Akshay aravind .rv\\operation_jarvis\\data\\repo_eval\\final_toolkit\\skillet\\bin\\skillet.js", "mcp"]` | stdio | INSTALLED + CONFIGURED |
| **playwright** | `npx` | `["-y", "@playwright/mcp@latest"]` | stdio | INSTALLED + CONNECTED |
| **chrome-devtools** | `npx` | `["-y", "@modelcontextprotocol/server-chrome-devtools@latest"]` | stdio | INSTALLED + CONNECTED |
| **local-memory** | `python` | `["LOCAL_AI_MEMORY/engine/mcp_server.py"]` | stdio | INSTALLED + CONNECTED |

---

## 4. Operation JARVIS & Qwen Adapter Modifications

| Modified File | Changes Made | Verification Status |
|---|---|---|
| `operation_jarvis/data/repo_eval/final_toolkit/skillet/src/install.js` | Added `isAbsolute()` check to prevent invalid Windows path joins. | VERIFIED PASS |
| `operation_jarvis/storage/tracelet_exporter.py` | New zero-dependency OTLP/HTTP JSON exporter emitting spans to `http://127.0.0.1:4318/v1/traces`. | VERIFIED PASS |
| `operation_jarvis/registry/capability_registry.py` | Added Tracelet export hook on tool completion; registered `skillet_search` and `skillet_list`. | VERIFIED PASS (22/22 pytest pass) |
| `LOCAL_AI_MEMORY/engine/qwen_chat.py` | Registered `skillet_search`, `skillet_list`, and `skillet_install` in Qwen's `ToolRegistry`. | VERIFIED PASS (Voice + CLI invocation) |

---

## 5. Configuration Backups

Saved in `C:\Users\Akshay aravind .rv\.ecosystem_backups\toolkit_integration_20261106\`:
- `mcp_config.json.bak`
- `config.yaml.bak`
- `capability_registry.py.bak`
- `qwen_chat.py.bak`
