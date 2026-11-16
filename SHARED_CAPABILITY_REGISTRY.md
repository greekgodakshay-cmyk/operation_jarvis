# Shared Capability & Skill Registry: Dual-Ecosystem Catalog

**Ecosystems:** Google Antigravity & Operation JARVIS  
**Total Canonical Skills:** 107  
**Total Native/MCP Capabilities:** 20  
**Verification Date:** 2026-11-06  
**Storage Architecture:** Canonical files under `.gemini/config/plugins` with dynamic cross-environment indexing.

---

## 1. Procedural Skills Catalog (Categorized by Domain)

### 1.1 Development, Testing & TDD
| Skill Name | Canonical Origin | Summary & Trigger |
| :--- | :--- | :--- |
| `test-driven-development` | `agent-skills` & `superpowers` | Red-green-refactor loop. Write failing test first, verify failure, implement minimal code, pass test. |
| `subagent-driven-development`| `superpowers` | Spawns isolated fresh-context subagents for independent tasks with review gates. |
| `incremental-implementation` | `agent-skills` | Delivers changes in thin, verifiable slices behind feature flags without breaking main branch. |
| `karpathy-guidelines` | `andrej-karpathy-skills` | Minimizes common LLM coding pitfalls: surgical edits, zero unrequested refactoring, deterministic verification. |
| `webapp-testing` | `anthropic-skills` | End-to-end webapp verification via Playwright/DevTools automation scripts. |

### 1.2 Code Review & Quality Assurance
| Skill Name | Canonical Origin | Summary & Trigger |
| :--- | :--- | :--- |
| `code-review-and-quality` | `agent-skills` | Multi-axis review: correctness, readability, architecture, security, performance. |
| `requesting-code-review` | `superpowers` | Verifies task requirements and creates review checklists before merging changes. |
| `receiving-code-review` | `superpowers` | Verifies review feedback technically before blind implementation. |
| `ponytail-review` | `ponytail` | Checks logic correctness, load endurance, safety, and deletes bloated lines. |
| `ponytail-audit` | `ponytail` | Repo-wide audit identifying bugs, security holes, untested code paths, and bloat. |

### 1.3 Architecture, Planning & Meta-Prompting
| Skill Name | Canonical Origin | Summary & Trigger |
| :--- | :--- | :--- |
| `writing-plans` | `superpowers` | Produces structured, bite-sized implementation plans with exact file paths and test commands. |
| `planning-and-task-breakdown`| `agent-skills` | Decomposes complex specifications into dependency-ordered work units. |
| `brainstorming` | `superpowers` | Structured divergence/convergence before creative or exploratory tasks. |
| `spec-driven-development` | `agent-skills` | Establishes formal PRD requirements and capability maps before implementation. |
| `doubt-driven-development` | `agent-skills` | Subjects every non-trivial decision to fresh-context adversarial review. |
| `documentation-and-adrs` | `agent-skills` | Records Architecture Decision Records (ADRs) with rationale and trade-offs. |
| `api-and-interface-design` | `agent-skills` | Establishes stable typed interfaces and module boundaries. |

### 1.4 Systematic Debugging & Error Recovery
| Skill Name | Canonical Origin | Summary & Trigger |
| :--- | :--- | :--- |
| `systematic-debugging` | `superpowers` | 4-phase root cause analysis: investigate, hypothesize, minimal reproduction, fix & verify. |
| `debugging-and-error-recovery`| `agent-skills` | Systematic diagnosis of test failures, build errors, and regressions. |
| `diagnosing-superpowers` | `superpowers` | Analyzes agent execution transcripts to detect repeated loops or missed skills. |

### 1.5 UI/UX, Design Systems & Frontend Engineering
| Skill Name | Canonical Origin | Summary & Trigger |
| :--- | :--- | :--- |
| `design` | `ui-ux-pro-max` | Comprehensive UI design: 80 styles, 192 color palettes, font pairings, visual hierarchy. |
| `design-system` | `ui-ux-pro-max` | Token architecture, component specifications, and responsive layout rules. |
| `frontend-ui-engineering` | `agent-skills` | Production-grade, WCAG-accessible, responsive component implementations. |
| `frontend-design` | `anthropic-skills` | Modern CSS, Tailwind, and interactive UI component creation. |
| `canvas-design` | `anthropic-skills` | HTML5 canvas graphics, dynamic visualizations, and chart rendering. |

### 1.6 Security, Hardening & Compliance
| Skill Name | Canonical Origin | Summary & Trigger |
| :--- | :--- | :--- |
| `security-and-hardening` | `agent-skills` | OWASP Top 10 mitigation, input sanitization, session security, credential defense. |
| `constraint-driven-development`| `agent-skills` | Prevents agents from silently lowering quality thresholds or suppressing lint checks. |
| `permissioned-github` | `builtin` | GitHub operations with strict permission and secret token validation. |

### 1.7 Optimization, Performance & Code Simplification
| Skill Name | Canonical Origin | Summary & Trigger |
| :--- | :--- | :--- |
| `performance-optimization` | `agent-skills` | Profiling, query optimization, Core Web Vitals, and caching layers. |
| `code-simplification` | `agent-skills` | Refactors hard-to-read code for clarity without altering behavior. |
| `ponytail` | `ponytail` | Lazy senior developer mode: produces the smallest possible diff that solves the task. |
| `ponytail-debt` | `ponytail` | Tracks deferred technical debt and shortcut comments. |

### 1.8 Prose, Documents & Anti-AI Polishing
| Skill Name | Canonical Origin | Summary & Trigger |
| :--- | :--- | :--- |
| `humanizer` | `humanizer` | Removes formulaic AI prose patterns, restoring natural human cadence. |
| `docx` / `pdf` / `pptx` / `xlsx`| `anthropic-skills` | Generates and parses standard Microsoft Office and PDF document formats. |

### 1.9 Codebase Understanding & Git Operations
| Skill Name | Canonical Origin | Summary & Trigger |
| :--- | :--- | :--- |
| `understand` / `understand-chat`| `understand-anything` | Deep codebase mapping, knowledge graph generation, and architecture explanation. |
| `using-git-worktrees` | `superpowers` | Isolated workspace branching using native Git worktrees. |
| `git-workflow-and-versioning`| `agent-skills` | Clean atomic commits, semantic version bumps, and PR creation. |
| `verification-before-completion`| `superpowers` | Mandates running verification commands and confirming green output before completion. |

---

## 2. Shared Workstation Capabilities & Tools

| Capability Name | Tool Type | Permission | Antigravity Access | JARVIS Access |
| :--- | :--- | :--- | :--- | :--- |
| `read_file` | Native Filesystem | Level 1 Safe | Native Tool (`read_file`) | Capability Registry (`read_file`) |
| `write_file` | Native Filesystem | Level 2 Controlled | Native Tool (`write_file`) | Capability Registry (`write_file`) |
| `edit_file` | Native Filesystem | Level 2 Controlled | Native Tool (`edit_file`) | Capability Registry (`edit_file`) |
| `run_command` | Shell Execution | Level 2 Controlled | Native Tool (`run_command`) | Capability Registry (`run_command`) |
| `verify_file_exists` | Truth Assertion | Level 1 Safe | Script / Test | Capability Registry (`verify_file_exists`) |
| `verify_file_content`| Truth Assertion | Level 1 Safe | Script / Test | Capability Registry (`verify_file_content`) |
| `verify_test_suite` | Truth Assertion | Level 2 Controlled | Terminal Runner | Capability Registry (`verify_test_suite`) |
| `memory_search` | BM25 FTS5 Memory | Level 1 Safe | MCP (`local-memory`) | Capability Registry (`memory_search`) |
| `memory_store` | BM25 FTS5 Memory | Level 2 Controlled | MCP (`local-memory`) | Capability Registry (`memory_store`) |
| `search_skills` | Procedural Discovery| Level 1 Safe | Slash / Auto-Skill | Capability Registry (`search_skills`) |
| `read_skill` | Procedural Instruction| Level 1 Safe | Skill File Read | Capability Registry (`read_skill`) |
| `navigate_page` | Chrome DevTools | Level 1 Safe | MCP (`chrome-devtools`)| MCP Adapter (`navigate_page`) |
| `browser_navigate` | Playwright Browser | Level 1 Safe | MCP (`playwright`) | MCP Adapter (`browser_navigate`) |
| `desktop_snapshot` | Windows Desktop GUI | Level 1 Safe | Skill (`agent-desktop`) | Capability Registry (`desktop_snapshot`) |

---

## 3. Dynamic Lookup Architecture

Neither environment requires hardcoded skill paths:
- **Antigravity:** Loads plugins dynamically from `C:\Users\Akshay aravind .rv\.gemini\config\plugins` using `plugin.json` manifests.
- **JARVIS:** `SkillRegistry` crawls the same `.gemini\config\plugins` directory on startup and parses YAML frontmatter in real time.
- If a user installs or updates a skill in Antigravity via `agy plugin install`, JARVIS immediately accesses the update without modifying its own codebase.
