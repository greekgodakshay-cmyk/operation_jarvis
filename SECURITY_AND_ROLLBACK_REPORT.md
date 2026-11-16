# Security Hardening, Audit & Rollback Specification

**System:** Operation JARVIS + Google Antigravity Workstation  
**Auditor:** AI Systems Architect & Security Engineer  
**Classification:** Defense-in-Depth Specification  
**Verification Date:** 2026-11-06  

---

## 1. Threat Model & Security Posture

Operating an autonomous, tool-using AI with shell access and filesystem manipulation capabilities on a personal Windows 11 workstation presents high-impact risks:
1. **Destructive Command Execution:** Accidental formatting, recursive partition wiping, or driver uninstallation.
2. **Path Traversal & System Tampering:** Modification of Windows system directories (`C:\Windows`, `C:\Program Files`) or system security configurations.
3. **Secret Leakage:** Exposure of API keys, tokens, or personal credentials in logs or LLM context.
4. **Prompt Injection / Indirect Hijacking:** Malicious code or instruction overrides hidden within untrusted tool outputs (e.g. downloaded files, scraped HTML).

---

## 2. Implemented Defense-in-Depth Controls

### 2.1 3-Tier Permission Model (`security/policy_engine.py`)

Every capability in the ecosystem is mapped to a strict permission level:

- **Level 1 (Safe - Read-Only):**
  - *Tools:* `read_file`, `list_dir`, `verify_file_exists`, `verify_file_content`, `memory_search`, `memory_status`, `desktop_snapshot`, `desktop_list_apps`, `search_skills`, `read_skill`.
  - *Policy:* Automatically executed; logged to append-only audit trail.
- **Level 2 (Controlled - Mutating but Sandboxed):**
  - *Tools:* `write_file`, `edit_file`, `run_command` (safe/controlled commands), `memory_store`, `memory_update`, `verify_test_suite`.
  - *Policy:* Permitted inside jailed workspace roots; changes tracked and verifiable; logged with before/after state.
- **Level 3 (Restricted - High-Risk / Irreversible):**
  - *Tools:* Destructive filesystem actions, deletion of databases, administrative shell commands, elevated network operations.
  - *Policy:* **Execution strictly blocked** until the user explicitly issues an approval token via `qwen /approve <request_id>` or the FastAPI approval endpoint.

### 2.2 Strict Hardware Path Jailing (`security/path_jail.py`)

- **Allowed Roots:**
  - `C:\Users\Akshay aravind .rv\operation_jarvis`
  - `C:\Users\Akshay aravind .rv\LOCAL_AI_MEMORY`
  - `C:\Users\Akshay aravind .rv`
- **Forbidden Directories (Hard Block):**
  - `C:\Windows`
  - `C:\Program Files`
  - `C:\Program Files (x86)`
  - `C:\System Volume Information`
  - `C:\$Recycle.Bin`
- **Enforcement:** Every relative or absolute path is resolved to its canonical physical path using `.resolve()`. Directory traversal attempts (e.g. `..\..\Windows`) instantly raise a `PathJailViolation` and terminate the step.

### 2.3 Command Validator (`security/command_validator.py`)

- Every command passed to `run_command` is pre-screened against strict regex signatures:
  - Destructive disk operations: `Format`, `Diskpart`, `Clear-Disk`, `Remove-Partition`.
  - Windows Defender / Security tampering: `Set-MpPreference`, `DisableRealtimeMonitoring`, `Stop-Service WinDefend`.
  - Recursive destructive deletions outside workspace: `Remove-Item -Recurse -Force C:\`.
- Dangerous commands are reclassified to Level 3 or hard-rejected before PowerShell is invoked.

### 2.4 Secret Redaction (`security/secret_redactor.py`)

- Automatically scans all strings and dictionaries before logging or returning to the LLM:
  - OpenAI / Anthropic keys (`sk-[a-zA-Z0-9]{20,}`)
  - GitHub Personal Access Tokens (`ghp_[a-zA-Z0-9]{36}`)
  - Generic Bearer tokens and authorization headers.
  - Replaces matches with `[REDACTED_SECRET]` or `[REDACTED_CREDENTIAL]`.

### 2.5 Prompt Injection Isolation (`security/injection_guard.py`)

- Wraps all untrusted content (web pages, email text, stdout) in explicit isolation tags:
  ```xml
  <untrusted_external_content source="tool_name">
  ... content with escaped markdown headers ...
  </untrusted_external_content>
  ```
- Prevents the local LLM from treating external strings as system instructions or supervisor overrides.

---

## 3. Rollback Procedures

Should any component, plugin, or database state require restoration, follow these verified procedures:

### 3.1 Plugin Rollback
To disable or uninstall a newly installed Antigravity plugin:
```powershell
# Disable without deleting
agy plugin disable <plugin-name>

# Completely uninstall plugin
agy plugin uninstall <plugin-name>
```
*Note:* Uninstallation removes the plugin directory from `.gemini\config\plugins\<plugin-name>`. JARVIS's `SkillRegistry` automatically excludes it on the next startup.

### 3.2 Task Database Rollback
If the SQLite task state in `operation_jarvis/data/jarvis_tasks.db` becomes corrupted:
```powershell
# Tasks DB backup
Copy-Item "C:\Users\Akshay aravind .rv\operation_jarvis\data\jarvis_tasks.db" "C:\Users\Akshay aravind .rv\operation_jarvis\data\jarvis_tasks.db.bak"

# Recreate fresh task schema
python -c "from storage.task_db import TaskDB; db = TaskDB(); print('Schema initialized.')"
```

### 3.3 Persistent Memory Rollback
`LOCAL_AI_MEMORY` maintains its own backup and snapshot subsystem:
```powershell
# Using the memory CLI
memory backup
# To restore
memory restore --snapshot <snapshot-date>
```
Existing backups remain untouched at `C:\Users\Akshay aravind .rv\LOCAL_AI_MEMORY\07_MEMORY_INDEX\backups\`.

---

## 4. Verification Evidence

All 19 security, jailing, policy, and validation assertions were executed in the test suite:
- `test_path_jail_allowed_workspace`: **PASSED**
- `test_path_jail_system_directory_blocked`: **PASSED**
- `test_path_jail_traversal_blocked`: **PASSED**
- `test_command_validator_safe_commands`: **PASSED**
- `test_command_validator_controlled_commands`: **PASSED**
- `test_command_validator_dangerous_patterns_blocked`: **PASSED**
- `test_command_validator_defender_tampering_blocked`: **PASSED**
- `test_secret_redactor_patterns`: **PASSED**
- `test_secret_redactor_nested_structure`: **PASSED**
- `test_injection_guard_boundary_wrapping`: **PASSED**
- `test_injection_guard_scan`: **PASSED**
- `test_policy_engine_level1_safe`: **PASSED**
- `test_policy_engine_level3_restricted_approval_gate`: **PASSED**
- `test_task_db_lifecycle`: **PASSED**
- `test_verification_engine_missing_file_rejected`: **PASSED**
- `test_verification_engine_existing_file_approved`: **PASSED**
- `test_skill_adapter_plugin_discovery`: **PASSED**
- `test_capability_skill_tools`: **PASSED**
- `test_memory_adapter_cross_env`: **PASSED**
