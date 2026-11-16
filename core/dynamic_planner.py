"""
Dynamic Planning Engine for Operation Jarvis.
Produces multi-step verifiable execution plans with relevant memory, skill grounding,
authoritative host temporal awareness, and fail-closed retry semantics.
"""
import json
import logging
from typing import Any, Dict, List, Optional
from config.settings import settings
from core.types import TaskPlan, ExecutionStep, StepStatus, PlanGenerationError
from core.llm_client import llm_client, LLMClientError
from core.temporal import get_temporal_context_prompt
from registry.capability_registry import capability_registry
from registry.memory_adapter import memory_adapter
from registry.skill_adapter import skill_registry

logger = logging.getLogger("jarvis.planner")

PLANNER_SYSTEM_PROMPT = """You are the Senior Planning Engine for Operation Jarvis on Windows 11.
Your task is to decompose the user's objective into a realistic, verifiable, step-by-step execution plan.

Rules:
1. Always ground your plan in the retrieved local memories, skills, and verified internet sources provided.
2. Select appropriate registered tools from the available capabilities.
3. Live Read-Only Internet Intelligence: When the objective involves finding current technical developments, news, software documentation, Wikipedia entries, research papers (arXiv), or cybersecurity advisories (CVE), use registered read-only tools: 'web_search', 'web_fetch', 'wikipedia_search', 'arxiv_search', 'cve_search', or 'tech_news_search'. All internet operations are strictly read-only GET/HEAD requests.
4. When the objective involves Chrome, browser pages, or inspecting emails / Gmail, select 'browser_read_gmail', 'browser_status', or 'browser_navigate'. When inspecting Gmail, first retrieve the emails with 'browser_read_gmail'; downstream summarization steps strictly depend on verified email retrieval and must not claim success if authentication fails or no emails are retrieved. Never claim browser access is unsupported.
5. When the objective involves desktop automation, listing running applications, inspecting windows, or GUI interaction, select the registered 'desktop' tool with argument 'subcommand' (e.g. {"subcommand": "list-apps"} or {"subcommand": "status"}). Do not invent hypothetical tools.
6. Open Intelligence & Security Separation: Support legitimate engineering, cybersecurity, reverse-engineering, and scientific research. Real mutating computer operations (writing files, modifying systems, running scripts) require verification and pass through the permission gateway. Read-only research and inspection do not mutate files.
7. Output MUST be strictly valid JSON matching this schema:
{
  "reasoning": "Brief explanation of the strategy",
  "steps": [
    {
      "step_number": 1,
      "description": "Specific action to perform",
      "tool_name": "name_of_tool_or_null",
      "tool_arguments": {"arg1": "val1"}
    }
  ]
}
Do not include conversational filler or markdown fences outside the JSON object.
"""

class DynamicPlanner:
    def __init__(self):
        self.llm = llm_client

    def create_plan(self, objective: str) -> TaskPlan:
        # 1. Retrieve relevant memory records
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

        # 2. Retrieve relevant procedural skills
        relevant_skills = skill_registry.find_relevant_skills(objective, max_count=2)
        skill_context = "\n".join([f"- Skill '{s.name}': {s.description}" for s in relevant_skills])

        # 3. Available tools summary (compact representation to conserve context budget)
        tools_summary = "\n".join([
            f"- {t['name']} (Level {t['permission_level']}): {t['description']}"
            for t in capability_registry.list_tools()[:25]
        ])

        # 4. Authoritative temporal context
        temporal_prompt = get_temporal_context_prompt()

        # 5. Prompt Assembly
        user_prompt = f"""{temporal_prompt}

OBJECTIVE:
{objective}

RELEVANT WORKSTATION MEMORIES:
{json.dumps(relevant_memories, indent=2) if relevant_memories else "No specific memory matches found."}

RELEVANT SKILLS:
{skill_context if skill_context else "Standard operational procedures apply."}

AVAILABLE CAPABILITIES:
{tools_summary}

Generate the step-by-step execution plan as strictly valid JSON:
"""
        messages = [
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]

        # Attempt 1: Standard generation
        last_error = None
        for attempt in (1, 2):
            try:
                res = self.llm.chat(messages, format_json=True, temperature=0.1, num_predict=768)
                content = res.get("content", "")
                parsed = self.llm.extract_json(content)
                
                raw_steps = parsed.get("steps", [])
                if not raw_steps or not isinstance(raw_steps, list):
                    raise ValueError(f"Plan contains 0 steps or invalid steps array: {parsed}")

                steps = []
                for item in raw_steps:
                    steps.append(ExecutionStep(
                        step_number=item.get("step_number", len(steps) + 1),
                        description=item.get("description", "Execute action"),
                        tool_name=item.get("tool_name"),
                        tool_arguments=item.get("tool_arguments", {}),
                        status=StepStatus.PENDING
                    ))

                return TaskPlan(
                    objective=objective,
                    reasoning=parsed.get("reasoning", "Autonomous plan generated."),
                    steps=steps,
                    relevant_memories=relevant_memories
                )

            except Exception as e:
                last_error = e
                logger.warning(f"Planner attempt {attempt} failed: {e}")
                if attempt == 1:
                    # Retry once with explicit corrective format enforcement
                    messages.append({"role": "assistant", "content": res.get("content", "") if 'res' in locals() else ""})
                    messages.append({
                        "role": "user",
                        "content": "ERROR: The output was not valid JSON conforming to the schema. Output ONLY valid JSON: {\"reasoning\": \"...\", \"steps\": [{\"step_number\": 1, \"description\": \"...\", \"tool_name\": null, \"tool_arguments\": {}}]}."
                    })

        # Fail-closed: raise explicit PlanGenerationError rather than returning a corrupt or hallucinated plan
        raise PlanGenerationError(f"Plan generation failed after 2 attempts: {last_error}")

dynamic_planner = DynamicPlanner()
