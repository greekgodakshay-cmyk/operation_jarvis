# Google Antigravity: Capability & Plugin Inventory

**Environment:** Google Antigravity IDE & Agent Framework  
**CLI Version:** 1.5.1  
**Verification Date:** 2026-11-06  
**Primary Configuration Path:** `C:\Users\Akshay aravind .rv\.gemini\config`

---

## 1. Overview of Antigravity Architecture

Google Antigravity serves as the workstation's interactive development environment and autonomous coding agent. It features:
- A plugin architecture managed via `agy plugin` CLI.
- Extensible skill folders formatted as `SKILL.md` with YAML frontmatter.
- First-class subagent delegation (`subagent-driven-development`).
- Model Context Protocol (MCP) clients connecting to live browser, memory, and search backends.

---

## 2. Installed & Active Plugins

Verified via `agy plugin list`:

| Plugin Name | Version | Source | Components & Capabilities |
| :--- | :--- | :--- | :--- |
| **`agent-skills`** | `0.6.13` | Antigravity Native | **27 skills, 4 agents**: `code-reviewer`, `security-auditor`, `test-engineer`, `web-performance-auditor`. Covers TDD, API design, security hardening, CI/CD, debugging, performance. |
| **`superpowers`** | `7.0.2` | Antigravity Native | **15 skills**: `brainstorming`, `diagnosing-superpowers`, `dispatching-parallel-agents`, `executing-plans`, `finishing-a-development-branch`, `receiving-code-review`, `requesting-code-review`, `subagent-driven-development`, `systematic-debugging`, `test-driven-development`, `using-git-worktrees`, `using-superpowers`, `verification-before-completion`, `writing-plans`, `writing-skills`. |
| **`ui-ux-pro-max`** | `2.15.0` | Claude-Code / Universal | **13 skills & design intelligence**: 80 UI styles, 192 color palettes, 74 font pairings, 25 charts, 22 stack presets. Includes `design`, `design-system`, `landing-page`, `mobile-ui`, `responsive-design`. |
| **`understand-anything`** | `2.9.8` | Claude-Code / Universal | **9 skills, 10 agents, 1 lifecycle hook**: Automated codebase visualization, architectural explanation, diff analysis, and onboarding walkthroughs. |
| **`anthropic-skills`** | `1.0.0` | Antigravity Curated | **19 skills**: Office automation (`docx`, `pdf`, `pptx`, `xlsx`), visual design (`frontend-design`, `algorithmic-art`, `canvas-design`), testing (`webapp-testing`, `mcp-builder`). |
| **`ponytail`** | `5.3.2` | Antigravity Native | **6 core skills (12 total manifests)**: `ponytail`, `ponytail-audit`, `ponytail-debt`, `ponytail-gain`, `ponytail-help`, `ponytail-review`. Ultra-lean senior developer mode enforcing minimal diffs. |
| **`get-shit-done`** | `1.50.0` | Antigravity Universal | **2 native agents, 65 workflow commands**: Spec-driven multi-agent orchestration, roadmap tracking, milestone completion (`gsd-nyquist-auditor`, `gsd-security-auditor`). |
| **`andrej-karpathy-skills`**| `1.0.0` | Claude-Code / Universal | **1 skill**: `karpathy-guidelines` (LLM pitfall prevention, minimal changes, deterministic verification). |
| **`humanizer`** | `3.1.0` | Claude-Code / Universal | **1 skill**: `humanizer` (Anti-AI prose polishing, natural human rhythm in documentation and commit messages). |

---

## 3. Builtin Core Skills

Located in `C:\Users\Akshay aravind .rv\.gemini\antigravity-cli\builtin\skills`:
1. `agy-customizations`: Comprehensive guide for creating rules, skills, hooks, and MCP servers.
2. `antigravity_guide`: System reference, slash commands, keybindings, and Python SDK.
3. `automation`: Workflow execution and headless automation scripts.
4. `generative_ui`: Dynamic generative UI and component rendering.
5. `migrate-workflows`: Migration tooling across harness formats.
6. `permissioned-github`: Secure GitHub interactions with credential validation.
7. `plugin`: Plugin lifecycle management (install, enable, disable, remove).
8. `run-workflow`: Workflow pipeline runner.
9. `ui-plugin-navigation`: Interactive UI navigation controls.

---

## 4. Model Context Protocol (MCP) Integration

Configured in `C:\Users\Akshay aravind .rv\.gemini\config\mcp_config.json`:

| Server Name | Transport | Purpose & Exposed Tools |
| :--- | :--- | :--- |
| **`chrome-devtools`** | stdio (node) | Direct Chrome browser control: `navigate_page`, `click`, `take_screenshot`, `evaluate_script`, `list_console_messages`. |
| **`playwright`** | stdio (node) | Headless browser automation: `browser_navigate`, `browser_click`, `browser_type`, `browser_snapshot`. |
| **`local-memory`** | stdio (python) | Workspace memory index: `memory_search`, `memory_store`, `memory_update`, `memory_status`. |
| **`firecrawl`** | stdio (node) | Web scraping, crawling, and research: `firecrawl_scrape`, `firecrawl_search`, `firecrawl_crawl`. |
| **`perplexity`** | stdio (node) | Live web search and fact verification: `perplexity_search`, `perplexity_reason`. |
| **`hyperframes`** | stdio (node) | Visual animation and multi-media timeline orchestration. |

---

## 5. Token Budget & Context Management Strategy

- **Prompt Rules Limit:** Antigravity enforces a strict context budget (default ~20,000 tokens for system rules).
- **Enforcement:** Wholesale dumping of bloated repositories (such as the 1,068 skills in ECC) was deliberately rejected. Only high-value curated plugins are active.
- **Progressive Skill Loading:** Skills are loaded strictly on demand when trigger phrases or tools are invoked, maintaining prompt cleanliness and high inference speed.
