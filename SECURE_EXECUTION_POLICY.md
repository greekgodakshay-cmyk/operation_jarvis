# OPERATION JARVIS — SECURE EXECUTION POLICY

**Document Version:** 1.0.0  
**Status:** Active & Enforced  
**Classification:** Security Architecture & Enforcement Specification  
**Target Runtime:** Operation JARVIS Autonomous Orchestrator & Local Runtimes  
**Author:** Principal AI Systems Architect & Cybersecurity Engineer  

---

## 1. EXECUTIVE SUMMARY & DEFENSE-IN-DEPTH POSTURE

The **Secure Execution Policy** governs all physical computer actions, process invocations, file operations, network interactions, and state mutations within Operation JARVIS.

While the *Open Intelligence Policy* permits open, detailed, and uninhibited discussion, education, and safe simulation, this *Secure Execution Policy* enforces an unyielding, non-bypassable barrier between cognitive model decisions and physical system operations.

```
+--------------------------------------------------------------------------------------------------+
|                            DEFENSE-IN-DEPTH EXECUTION GATEWAY                                    |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|   1. CAPABILITY REGISTRY               2. POLICY & PERMISSION ENGINE     3. CANONICAL PATH JAIL  |
|   • Default-deny unknown tools         • Level 1: SAFE (Inspection)      • Resolves real symlinks|
|   • Strict JSON parameter schemas      • Level 2: CONTROLLED (Jailed)    • Allowed workspaces    |
|   • Strict timeout enforcement         • Level 3: RESTRICTED (Approval)  • System dirs forbidden |
|                                                                                                  |
|   4. COMMAND VALIDATOR (AST)           5. UNTRUSTED INJECTION GUARD      6. CRYPTOGRAPHIC AUDIT  |
|   • Regex & token blacklist            • Escapes system tokens           • Rolling SHA-256 hash  |
|   • Destructive command escalation     • <untrusted_external_content>    • Immutable JSONL trail |
|   • Outbound POST/exfil escalation     • Injection pattern warning       • Zero secret leakage   |
|                                                                                                  |
|   ============================================================================================   |
|   EMERGENCY STOP (KILLSWITCH): Immediate revocation of all approval tokens and process abort.     |
+--------------------------------------------------------------------------------------------------+
```

---

## 2. THREE-TIER PERMISSION CLASSIFICATION

Every tool in the `CapabilityRegistry` is assigned an immutable permission level:

### Level 1: SAFE (Automatic Execution Permitted)
- **Characteristics:** Strictly non-mutating, read-only inspection operations. Zero destructive capability; zero persistent side-effects.
- **Tools:**
  - `read_file`, `list_dir`, `verify_file_exists`, `verify_file_content`
  - `memory_search`, `memory_status`
  - `web_search`, `web_fetch`, `wikipedia_search`, `arxiv_search`, `cve_search`, `tech_news_search`
  - `research_search`, `research_status`, `research_emergency_stop`
  - `desktop` (read-only inspection: `list-apps`, `list-windows`, `snapshot`, `status`)
  - `browser_status`, `browser_list_pages`, `browser_snapshot`, `browser_read_gmail` (read-only)
- **Constraint:** Filesystem reads must still resolve within canonical workspace bounds (`PathJail`).

### Level 2: CONTROLLED (Bounded Autonomous Execution)
- **Characteristics:** Mutating operations strictly confined to approved workspace directories or verified safe scripts.
- **Tools:**
  - `write_file`, `edit_file` (sandboxed inside workspace roots)
  - `run_command` (approved safe prefixes: `python `, `uv run `, `pytest `, `npm test `, `git add `, `git commit `)
  - `memory_store`, `memory_update` (versioned updates with changelog)
  - `verify_test_suite` (automated test runner)
  - `research_trigger_cycle` (on-demand research indexing cycle)
- **Constraint:** Commands containing deletion or termination keywords (`del`, `rm`, `remove-item`, `kill`, `drop`) automatically escalate to Level 3.

### Level 3: RESTRICTED (Explicit Human Approval Required)
- **Characteristics:** Privileged, destructive, irreversible, or sensitive operations.
- **Operations Requiring Human Approval Gate:**
  1. Destructive file operations (`del /s /q`, `rmdir /s /q`, `rm -rf`, `erase`, `format`).
  2. Database deletion or drops (`drop database`, `drop table`).
  3. Operating system configuration changes (`netsh firewall`, `Set-MpPreference`, `DisableRealtimeMonitoring`, registry edits, service stops).
  4. External network communication and outbound data transfer (`curl -X POST`, `Invoke-RestMethod -Method Post`, `nmap`, `masscan`, `nc`, `ncat`, `ssh`, `scp`, `ftp`).
  5. System reboot, shutdown, or process termination (`shutdown`, `stop-process`).
- **Approval Workflow:**
  - The orchestrator suspends the task, generates an immutable `ApprovalRequest` (`appr-<uuid>`), sets state to `WAITING_FOR_APPROVAL`, and emits an audible/terminal alert.
  - The user must explicitly run `jarvis_cli approve <task_id> <request_id>` to authorize.

---

## 3. FILESYSTEM SANDBOXING & CANONICAL PATH JAIL

The `PathJail` engine enforces strict filesystem boundaries on all file-accessing tools:

### 3.1 Allowed Workspace Roots
Access is strictly confined to:
1. `C:\Users\Akshay aravind .rv\operation_jarvis` (Primary workspace)
2. `C:\Users\Akshay aravind .rv\LOCAL_AI_MEMORY` (Persistent memory ecosystem)
3. `C:\Users\Akshay aravind .rv` (User profile bounds)

### 3.2 Explicitly Forbidden System Directories
Attempts to read, write, or traverse into the following directories trigger an immediate `PathJailViolation` error:
- `C:\Windows`
- `C:\Program Files`
- `C:\Program Files (x86)`
- `C:\System Volume Information`
- `C:\$Recycle.Bin`

### 3.3 Traversal & Symlink Defense
- Every path argument is resolved using `Path(target).resolve()` to expand relative components (`..`), canonicalize drive letters, and follow symlinks before boundary validation.
- Direct path-string comparisons are performed against normalized lowercase representations.

---

## 4. COMMAND & SCRIPT EXECUTION RESTRICTIONS

The `CommandValidator` parses and classifies all command strings passed to `run_command` or shell adapters:

1. **Dangerous Pattern Interception:**
   - Any command matching system-destructive patterns (`format`, `diskpart`, Defender disabling, firewall disabling, piping web requests to interpreters `curl ... | iex`) is rejected outright.
2. **Network Scoping & Security Scanning:**
   - Security scanning tools (`nmap`, `masscan`) and raw network sockets (`nc`, `socat`) require Level 3 explicit human authorization and verified target scope.
   - Outbound write methods (`curl -X POST`, `Invoke-RestMethod -Method Post`) are restricted from autonomous execution.
3. **Execution Timeouts:**
   - Default command timeout: 60 seconds.
   - Non-terminating daemon commands must be spawned via supervised background tasks (`subprocess.Popen` with tracked PID) and must never hang synchronous pipelines.

---

## 5. LIVE READ-ONLY INTERNET BOUNDARIES

The `InternetGateway` operates under strict network isolation rules:

1. **HTTP Method Whitelist:** Strictly `GET` and `HEAD` only. Any `POST`, `PUT`, `PATCH`, `DELETE` request raises an immediate `ReadOnlyViolationError`.
2. **SSRF & DNS Rebinding Shield:**
   - Disallows `127.0.0.1`, `localhost`, `0.0.0.0`, `::1`.
   - Disallows private RFC1918 subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `fc00::/7`).
   - Disallows link-local / APIPA (`169.254.0.0/16`) and cloud metadata (`169.254.169.254`).
   - Validates destination IP address before connection and validates redirects at every single hop.
3. **Outgoing Query Sanitization:**
   - Automatically redacts user file paths, personal names, email addresses, and API keys before external transmission.
4. **Data Isolation:**
   - Internet read access conveys **zero** execution privileges on internal networks or the local machine.
   - External web content is strictly separated from `LOCAL_AI_MEMORY` and indexed only into `data/research_index.db`.

---

## 6. CREDENTIAL PROTECTION & SECRET REDACTION

The `SecretRedactor` automatically sanitizes data entering or leaving the system:
- High-entropy tokens, Bearer tokens, API keys (`sk-...`, `ghp_...`), private keys (`BEGIN PRIVATE KEY`), and passwords are masked with `[SECRET_REDACTED]` in audit logs, task traces, and LLM prompts.
- Personal memory files and credentials are never passed as arguments to web retrieval tools.

---

## 7. UNTRUSTED CONTENT & PROMPT INJECTION DEFENSE

The `InjectionGuard` protects the cognitive planning engine from indirect prompt injection:
1. All tool outputs, retrieved webpages, emails, and external documents are enclosed within strict boundary tags:
   ```xml
   <untrusted_external_content source="https://..." warning="possible_prompt_injection_detected">
   ...
   </untrusted_external_content>
   ```
2. LLM control tokens such as `<|im_start|>`, `<|im_end|>`, ````system`, and `[SYSTEM]` are neutralized to `[ESCAPED_TOKEN]` before entering the prompt.
3. External web instructions are explicitly classified as untrusted data and can **never** authorize tool execution or override system directives.

---

## 8. TAMPER-EVIDENT CRYPTOGRAPHIC AUDIT LOGGING

Every event in the agent lifecycle is recorded to `logs/audit_trail.jsonl`:
- **Record Fields:** `timestamp`, `task_id`, `event_type`, `details`, `prev_hash`, `hash`.
- **Rolling SHA-256 Digest:** Each entry computes `hash = SHA256(prev_hash + JSON(entry))`. Any manual tampering, line deletion, or retrofitting invalidates the cryptographic chain.
- **Trace Export:** Real-time OTLP tool call spans are emitted to Tracelet (`http://127.0.0.1:4318`) for visual latency and execution tracing.

---

## 9. EMERGENCY STOP (KILLSWITCH) PROTOCOL

Operation JARVIS implements an instantaneous emergency stop mechanism:
1. **Triggering:**
   - Via CLI: `python cli/jarvis_cli.py emergency-stop --reason "..."`
   - Via Python: `orchestrator.emergency_stop()` / `policy_engine.trigger_emergency_stop()`
   - Via Research Indexer: `research_indexer.emergency_stop()`
2. **Immediate Actions:**
   - Sets internal policy state to `EMERGENCY_STOP_ACTIVATED`.
   - Immediately purges and revokes all active approval tokens.
   - Any pending or incoming tool call is rejected with `PolicyViolationError("EMERGENCY STOP ACTIVE")`.
   - All active running tasks in SQLite state are transitioned to `CANCELLED`.
   - Background research indexing worker threads are signaled and terminated.
3. **Recovery:** Requires explicit human intervention via `python cli/jarvis_cli.py reset-stop`.
