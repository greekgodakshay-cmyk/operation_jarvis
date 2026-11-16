# OPERATION JARVIS — CAPABILITY AND TOOL REGISTRY

**Document Version:** 1.0.0  
**Registry Module:** `operation_jarvis/registry/capability_registry.py`  

---

## 1. OVERVIEW

Operation Jarvis implements a centralized capability registry that catalogs:
1. Native sandboxed file and command tools.
2. Verification assertions for physical artifacts and test suites.
3. Persistent memory adapters connecting to `LOCAL_AI_MEMORY`.
4. Windows desktop automation adapters via `agent-desktop` CLI.
5. External MCP servers discovered from `mcp_config.json`.
6. Procedural agent skills discovered from `agent-skills`.

Each capability publishes:
- **Unique Name**
- **Detailed Description**
- **Input JSON Schema** (compatible with OpenAI/Ollama function calling specifications)
- **Permission Level** (Level 1 Safe, Level 2 Controlled, Level 3 Restricted)
- **Execution Handler**
- **Timeout Budget**

---

## 2. REGISTERED TOOL SPECIFICATIONS

### 2.1 Native Filesystem Tools

#### `read_file`
- **Permission:** Level 1 — SAFE
- **Description:** Read lines from a file safely within workspace bounds.
- **Parameters:**
  ```json
  {
    "type": "object",
    "properties": {
      "path": {"type": "string", "description": "Absolute or relative file path"},
      "start_line": {"type": "integer", "default": 1},
      "end_line": {"type": "integer"}
    },
    "required": ["path"]
  }
  ```
- **Guarantees:** Path-jailed; returns line range, total line count, and content.

#### `list_dir`
- **Permission:** Level 1 — SAFE
- **Description:** List items inside a directory safely within workspace bounds.
- **Parameters:**
  ```json
  {
    "type": "object",
    "properties": {
      "path": {"type": "string", "description": "Directory path"},
      "recursive": {"type": "boolean", "default": false}
    },
    "required": ["path"]
  }
  ```
- **Guarantees:** Distinguishes files and directories with sizes.

#### `write_file`
- **Permission:** Level 2 — CONTROLLED
- **Description:** Write full contents to a file within workspace bounds.
- **Parameters:**
  ```json
  {
    "type": "object",
    "properties": {
      "path": {"type": "string", "description": "Target file path"},
      "content": {"type": "string", "description": "File text content"},
      "overwrite": {"type": "boolean", "default": false}
    },
    "required": ["path", "content"]
  }
  ```
- **Guarantees:** Path-jailed; refuses silent overwrite unless `overwrite=True`.

#### `edit_file`
- **Permission:** Level 2 — CONTROLLED
- **Description:** Replace target substring with replacement in an existing file.
- **Parameters:**
  ```json
  {
    "type": "object",
    "properties": {
      "path": {"type": "string", "description": "Target file path"},
      "target": {"type": "string", "description": "Exact text to replace"},
      "replacement": {"type": "string", "description": "New replacement text"}
    },
    "required": ["path", "target", "replacement"]
  }
  ```
- **Guarantees:** Atomic in-place replacement with count reporting.

#### `run_command`
- **Permission:** Level 2 — CONTROLLED / Level 3 — RESTRICTED
- **Description:** Run a controlled shell command or test script with defense-in-depth inspection.
- **Parameters:**
  ```json
  {
    "type": "object",
    "properties": {
      "command": {"type": "string", "description": "Command line string"},
      "working_dir": {"type": "string", "description": "Optional working directory"},
      "timeout": {"type": "number", "default": 60.0}
    },
    "required": ["command"]
  }
  ```
- **Guarantees:** Scanned by `command_validator`. Destructive commands (deletion, process kill) escalate to Level 3 approval.

---

### 2.2 Verification Assertions

#### `verify_file_exists`
- **Permission:** Level 1 — SAFE
- **Description:** Verify that a required file exists on disk and check its size.
- **Parameters:** `path` (string)
- **Guarantees:** Eliminates hallucinated file creations.

#### `verify_file_content`
- **Permission:** Level 1 — SAFE
- **Description:** Verify that a file contains an expected substring.
- **Parameters:** `path` (string), `expected_substring` (string)
- **Guarantees:** Confirms syntactic and semantic correctness of written code.

#### `verify_test_suite`
- **Permission:** Level 2 — CONTROLLED
- **Description:** Run an automated test suite command (e.g. `pytest`) and verify exit code 0.
- **Parameters:** `test_command` (string), `working_dir` (string)
- **Guarantees:** Bounded 120s timeout; captures stdout and stderr.

---

### 2.3 Memory Ecosystem Adapters

#### `memory_search`
- **Permission:** Level 1 — SAFE
- **Description:** Search persistent local memory and project knowledge using BM25 FTS5.
- **Parameters:** `query` (string), `category` (optional), `project` (optional), `limit` (int, default 5)
- **Guarantees:** Sub-millisecond full-text retrieval across all memory categories.

#### `memory_store`
- **Permission:** Level 2 — CONTROLLED
- **Description:** Store a verified factual memory record in the persistent local memory ecosystem.
- **Parameters:** `title` (string), `content` (string), `category` (optional), `project` (string), `importance` (string), `tags` (list)
- **Guarantees:** Automatically checks logical storage budgets; updates SQLite FTS5 index.

#### `memory_update`
- **Permission:** Level 2 — CONTROLLED
- **Description:** Update an existing memory record with version tracking and changelog.
- **Parameters:** `target_id_or_title` (string), `content` (string), `changelog` (string)
- **Guarantees:** Preserves previous versions; tracks rationale for revision.

#### `memory_status`
- **Permission:** Level 1 — SAFE
- **Description:** Check storage health and utilization budgets of the persistent memory ecosystem.
- **Parameters:** None
- **Guarantees:** Reports bytes used, remaining budget, and healthy flag across 6 categories.

---

### 2.4 Desktop Automation Adapters

#### `desktop_snapshot`
- **Permission:** Level 1 — SAFE
- **Description:** Capture accessibility tree of Windows applications with `@ref` identifiers.
- **Parameters:** `app_name` (optional string)
- **Guarantees:** Powered by native `agent-desktop` CLI.

#### `desktop_list_apps`
- **Permission:** Level 1 — SAFE
- **Description:** List running GUI applications on the Windows workstation.
- **Parameters:** None

---

## 3. PROCEDURAL SKILLS INTEGRATION (`registry/skill_adapter.py`)

Skills are procedural instruction sets (distinguished from executable tools).
The Skill Registry discovers and indexes:
- 27 `agent-skills` (e.g., `test-driven-development`, `debugging-and-error-recovery`, `security-and-hardening`, `agent-desktop`, `api-and-interface-design`).
- 5 `ponytail` skills (`ponytail`, `ponytail-audit`, `ponytail-debt`, `ponytail-gain`, `ponytail-review`).

When an objective is submitted, `skill_registry.find_relevant_skills(objective)` extracts relevant guidance and provides it to the planner so Qwen reasons according to proven engineering protocols.
