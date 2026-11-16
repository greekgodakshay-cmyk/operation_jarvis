"""
Hierarchical Task Decomposition Planner for Operation Jarvis.
Decomposes complex objectives into structured sub-objectives, assigns specialist agents,
detects parallel execution opportunities, and enforces fail-closed semantics.
"""
import json
import logging
from typing import Any, Dict, List, Optional
from core.types import TaskPlan, SubObjective, ExecutionStep, StepStatus, AgentRole, PlanGenerationError
from core.llm_client import llm_client
from core.temporal import get_temporal_context_prompt
from registry.capability_registry import capability_registry
from registry.memory_adapter import memory_adapter
from registry.skill_adapter import skill_registry

logger = logging.getLogger("jarvis.hierarchical_planner")

HIERARCHICAL_PLANNER_PROMPT = """You are the Principal Multi-Agent Planning Engine for Operation Jarvis.
Decompose the objective into independent sub-objectives, assign specialist agents, and generate concrete execution steps.

Agent Specializations:
- orchestrator: High-level coordination, synthesis, verification.
- code_agent: File reading, code writing, syntax verification, multi-file patching.
- workspace_agent: File structure discovery, directory listing, workspace inventory.
- tester_agent: Debugging, executing test suites, verifying test outputs.
- documenter_agent: Generating READMEs, docstrings, architectural documentation.
- git_agent: Git status, branch/remote inspection, staging, committing, pushing to GitHub.
- browser_agent: Browser automation, webpage text inspection, Gmail review.
- system_agent: Desktop automation, processes, system diagnostics, shell commands.
- research_agent: Deep research, live news search, arxiv, CVEs, Wikipedia, weather.
- memory_agent: Retrieving and storing persistent local memories and preferences.

Rules:
1. Select real registered tools from the available capabilities.
2. Mark 'is_parallel_eligible': true for steps with no shared state or sequential dependency.
3. Every step must have a concrete, verifiable outcome.
4. Output strictly valid JSON matching this schema:
{
  "reasoning": "High-level architectural rationale",
  "sub_objectives": [
    {
      "id": "sub_1",
      "title": "Clear objective title",
      "assigned_agent": "orchestrator|code_agent|browser_agent|system_agent|research_agent",
      "dependencies": []
    }
  ],
  "steps": [
    {
      "step_number": 1,
      "sub_objective_id": "sub_1",
      "description": "Specific action to perform",
      "assigned_agent": "code_agent",
      "tool_name": "read_file",
      "tool_arguments": {"path": "example.py"},
      "is_parallel_eligible": false,
      "dependencies": []
    }
  ]
}
Output ONLY valid JSON. No conversational filler or markdown fences.
"""

class HierarchicalPlanner:
    def __init__(self):
        self.llm = llm_client

    def create_hierarchical_plan(self, objective: str) -> TaskPlan:
        # 1. Retrieve relevant memories
        relevant_memories = []
        try:
            raw_memories = memory_adapter.search(query=objective, limit=3)
            for m in raw_memories:
                relevant_memories.append({
                    "id": m.get("id"),
                    "title": m.get("title"),
                    "category": m.get("category"),
                    "snippet": m.get("snippet")
                })
        except Exception:
            pass

        # 2. Retrieve relevant skills
        relevant_skills = skill_registry.find_relevant_skills(objective, max_count=2)
        skills_text = "\n".join([f"- Skill '{s.name}': {s.description}" for s in relevant_skills])

        # 3. Available tools summary
        tools_summary = "\n".join([
            f"- {t['name']} (Level {t['permission_level']}): {t['description']}"
            for t in capability_registry.list_tools()[:25]
        ])

        temporal_prompt = get_temporal_context_prompt()

        user_prompt = f"""{temporal_prompt}

OBJECTIVE:
{objective}

RELEVANT MEMORIES:
{json.dumps(relevant_memories, indent=2) if relevant_memories else "None"}

RELEVANT PROCEDURAL SKILLS:
{skills_text if skills_text else "Standard operating procedures"}

CORE CAPABILITIES:
{tools_summary}

Generate the hierarchical execution plan with assigned agent roles and dependencies in valid JSON:"""

        messages = [
            {"role": "system", "content": HIERARCHICAL_PLANNER_PROMPT},
            {"role": "user", "content": user_prompt}
        ]

        last_error = None
        for attempt in (1, 2):
            try:
                res = self.llm.chat(messages, format_json=True, temperature=0.1, num_predict=768)
                content = res.get("content", "")
                parsed = self.llm.extract_json(content)

                def _normalize_role(val: str) -> AgentRole:
                    v = (val or "").lower().replace("_agent", "").replace("-agent", "").strip()
                    role_map = {
                        "code": AgentRole.CODER, "coder": AgentRole.CODER,
                        "system": AgentRole.SYSTEM_OPS, "system_ops": AgentRole.SYSTEM_OPS, "sysops": AgentRole.SYSTEM_OPS,
                        "research": AgentRole.RESEARCHER, "researcher": AgentRole.RESEARCHER,
                        "browser": AgentRole.BROWSER, "review": AgentRole.REVIEWER, "reviewer": AgentRole.REVIEWER,
                        "memory": AgentRole.MEMORY, "workspace": AgentRole.WORKSPACE, "file": AgentRole.WORKSPACE,
                        "test": AgentRole.TESTER, "tester": AgentRole.TESTER, "testing": AgentRole.TESTER,
                        "doc": AgentRole.DOCUMENTER, "documenter": AgentRole.DOCUMENTER, "docs": AgentRole.DOCUMENTER,
                        "git": AgentRole.GIT, "repo": AgentRole.GIT
                    }
                    return role_map.get(v, AgentRole.ORCHESTRATOR)

                def _normalize_deps(deps_list: Any) -> List[int]:
                    out = []
                    if isinstance(deps_list, list):
                        for d in deps_list:
                            if isinstance(d, int):
                                out.append(d)
                            elif isinstance(d, str):
                                s = d.lower().replace("step_", "").replace("step", "").strip()
                                if s.isdigit():
                                    out.append(int(s))
                    return out

                # Parse sub-objectives
                sub_objectives = []
                for so in parsed.get("sub_objectives", []):
                    role = _normalize_role(so.get("assigned_agent", "orchestrator"))
                    sub_objectives.append(SubObjective(
                        id=so.get("id", f"sub_{len(sub_objectives)+1}"),
                        title=so.get("title", "Sub-objective"),
                        assigned_agent=role,
                        dependencies=so.get("dependencies", []),
                        status=StepStatus.PENDING
                    ))

                # Parse steps
                steps = []
                for item in parsed.get("steps", []):
                    role = _normalize_role(item.get("assigned_agent", "orchestrator"))
                    t_name = item.get("tool_name")
                    # Pre-validate tool existence if tool_name is provided
                    if t_name and not capability_registry.get_tool(t_name):
                        logger.warning(f"Planner planned unregistered tool '{t_name}'. Setting to None for safe verification failure.")
                        t_name = None

                    clean_deps = _normalize_deps(item.get("dependencies", []))
                    steps.append(ExecutionStep(
                        step_number=int(item.get("step_number", len(steps) + 1)),
                        description=item.get("description", "Execute action"),
                        tool_name=t_name,
                        tool_arguments=item.get("tool_arguments", {}),
                        status=StepStatus.PENDING,
                        assigned_agent=role,
                        is_parallel_eligible=bool(item.get("is_parallel_eligible", False)),
                        dependencies=clean_deps
                    ))

                if not steps:
                    raise ValueError("Planner returned 0 steps.")

                # Compute parallel groups
                parallel_groups = self._compute_parallel_groups(steps)

                return TaskPlan(
                    objective=objective,
                    reasoning=parsed.get("reasoning", "Hierarchical plan generated."),
                    steps=steps,
                    sub_objectives=sub_objectives,
                    parallel_groups=parallel_groups,
                    relevant_memories=relevant_memories
                )

            except Exception as e:
                last_error = e
                logger.warning(f"Hierarchical planner attempt {attempt} failed: {e}")
                if attempt == 1:
                    messages.append({"role": "assistant", "content": res.get("content", "") if 'res' in locals() else ""})
                    messages.append({
                        "role": "user",
                        "content": "ERROR: The output was not valid JSON conforming to schema. Output strictly valid JSON matching the schema."
                    })

        # Fail-closed: Never substitute a 1-step dummy fallback plan
        raise PlanGenerationError(f"Hierarchical plan generation failed after 2 attempts: {last_error}")

    def _compute_parallel_groups(self, steps: List[ExecutionStep]) -> List[List[int]]:
        """Groups independent steps into parallel execution batches."""
        groups = []
        current_group = []
        for s in steps:
            if s.is_parallel_eligible and not s.dependencies:
                current_group.append(s.step_number)
            else:
                if current_group:
                    groups.append(current_group)
                    current_group = []
                groups.append([s.step_number])
        if current_group:
            groups.append(current_group)
        return groups if groups else [[s.step_number] for s in steps]

hierarchical_planner = HierarchicalPlanner()
