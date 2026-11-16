"""
Personal Assistant Engine for Operation JARVIS.
Tailored for operator "Batman": 21-year-old 4th-sem CSE student (BTU),
bodybuilder / YouTuber (Mr Mysto), developer of Student Internship Portal,
and cybersecurity/systems researcher.

Provides:
1. Daily Brief: Integrates calendar events, active tasks, academic priorities, and workout schedule.
2. Deep Research Mode: Decomposes queries, gathers evidence, structures facts vs inferences vs uncertainties,
   and archives into data/research_index.db.
3. Content Assistant: Researches YouTube topics, writes retention hooks, outlines beats,
   generates titles & descriptions, and enforces Level 3 approval for publishing.
"""
from datetime import datetime, date
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from config.settings import settings
from core.llm_client import llm_client
from core.types import TaskBudget
from storage.task_db import task_db
from registry.calendar_adapter import calendar_adapter
from registry.memory_adapter import memory_adapter
from core.research_indexer import research_indexer

logger = logging.getLogger("jarvis.assistant")


class PersonalAssistant:
    def __init__(self):
        self.operator_alias = "Batman"

    def generate_daily_brief(self, target_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Synthesizes a daily briefing aggregating calendar events, active tasks,
        academic deadlines, and workout/personal priorities into a direct,
        first-principles action plan.
        """
        today_str = target_date or datetime.now().strftime("%Y-%m-%d")
        
        # 1. Fetch Calendar Events
        events = calendar_adapter.get_events(limit=10)
        # Filter for relevant events
        active_events = [e for e in events if e.get("status") != "cancelled"]

        # 2. Fetch Pending Tasks
        recent_tasks = task_db.list_tasks(limit=15)
        pending_tasks = [t for t in recent_tasks if t.status.value in ["pending", "in_progress", "waiting_for_approval"]]

        # 3. Fetch Memory Priorities (Academics, Fitness, Workstation)
        academic_mems = memory_adapter.search(query="BTU 4th semester CSE exam syllabus internship", project="student_internship", limit=3)
        fitness_mems = memory_adapter.search(query="workout bodybuilding gym creatine training", project="global", limit=2)
        youtube_mems = memory_adapter.search(query="Mr Mysto YouTube channel video concept editing", project="mr_mysto", limit=2)

        # 4. Construct Context for Live Model
        context_payload = {
            "date": today_str,
            "operator": self.operator_alias,
            "calendar_events": [
                {"title": e["title"], "start": e["start_time"], "location": e.get("location")}
                for e in active_events[:5]
            ],
            "pending_workstation_tasks": [
                {"id": t.task_id, "status": t.status.value, "objective": t.objective}
                for t in pending_tasks[:5]
            ],
            "academic_context": [m.get("title") for m in academic_mems],
            "fitness_context": [m.get("title") for m in fitness_mems],
            "content_context": [m.get("title") for m in youtube_mems]
        }

        prompt = f"""You are JARVIS, an autonomous workstation assistant for operator '{self.operator_alias}'.
Operator Profile: 21yo 4th-semester CSE student (BTU), runs YouTube channel 'Mr Mysto' (bodybuilding/motivation),
trains heavy in the gym, builds student software, and researches systems & security.
Tone requirement: Direct, intellectually honest, first-principles, cause-and-effect. No generic motivation, no flattery.

Date: {today_str}
Context Data:
{json.dumps(context_payload, indent=2)}

Generate a structured daily briefing with exactly these 5 numbered sections:
1. CRITICAL PRIORITIES (Top 3 mission-critical focus areas for today)
2. SCHEDULE & CALENDAR (Time-blocked overview of confirmed commitments)
3. ACADEMIC & CSE ENGINE (BTU coursework, project roadmap, deliverables)
4. CONTENT & FITNESS EXECUTION (Mr Mysto upload progress, training schedule)
5. WORKSTATION HEALTH & PENDING TASKS (Pending task state and system actions)

Keep it actionable, precise, and concise."""

        response = llm_client.chat(
            messages=[
                {"role": "system", "content": "You are JARVIS. Produce direct, structured, objective operational briefings."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            think=False,
            task_budget=TaskBudget.RESEARCH
        )

        briefing_text = response.get("content", "").strip()

        return {
            "date": today_str,
            "operator": self.operator_alias,
            "briefing": briefing_text,
            "active_event_count": len(active_events),
            "pending_task_count": len(pending_tasks),
            "raw_context": context_payload
        }

    def conduct_deep_research(self, query: str, domain: str = "technical") -> Dict[str, Any]:
        """
        Executes a rigorous research workflow:
        1. Query decomposition into subqueries.
        2. Local FTS retrieval across research_index.db and memory.db.
        3. Fact vs Inference vs Uncertainty synthesis.
        4. Structured archival into research_index.db.
        """
        logger.info(f"Conducting deep research for query: {query} (domain={domain})")
        
        # 1. Decompose Query
        decomp_prompt = f"""Decompose this research objective into 3 distinct technical search queries for documentation and research indexing:
Objective: "{query}"

Output ONLY a JSON array of 3 strings, e.g. ["query 1", "query 2", "query 3"]."""

        decomp_res = llm_client.chat(
            messages=[
                {"role": "system", "content": "You are a research indexing analyzer. Output valid JSON arrays only."},
                {"role": "user", "content": decomp_prompt}
            ],
            temperature=0.1,
            think=False,
            task_budget=TaskBudget.SHORT_ANSWER
        )

        subqueries = [query]
        try:
            raw_decomp = decomp_res.get("content", "").strip()
            # Clean possible markdown fence
            if "```json" in raw_decomp:
                raw_decomp = raw_decomp.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_decomp:
                raw_decomp = raw_decomp.split("```")[1].split("```")[0].strip()
            parsed = json.loads(raw_decomp)
            if isinstance(parsed, list) and len(parsed) > 0:
                subqueries = parsed[:3]
        except Exception:
            subqueries = [query, f"{query} architecture", f"{query} security analysis"]

        # 2. Gather Evidence from Local Repositories
        evidence_items = []
        # Search public research index
        for sq in subqueries:
            hits = research_indexer.db.search_research(sq, limit=3)
            for h in hits:
                evidence_items.append({
                    "source": f"research_index:{h.get('url', 'local')}",
                    "title": h.get("title", ""),
                    "snippet": h.get("snippet", "")
                })
        
        # Search internal memory
        mem_hits = memory_adapter.search(query, limit=3)
        for m in mem_hits:
            evidence_items.append({
                "source": f"memory:{m.get('id')}",
                "title": m.get("title", ""),
                "snippet": m.get("snippet", "")
            })

        evidence_text = "\n".join([
            f"- [{e['source']}] {e['title']}: {e['snippet']}"
            for e in evidence_items[:6]
        ])

        # 3. Live Model Synthesis: Fact vs Inference vs Uncertainty
        synthesis_prompt = f"""Conduct a first-principles technical evaluation for:
Objective: "{query}"

Available Verified Evidence:
{evidence_text if evidence_text else "No existing indexed local documents found. Base evaluation on established computer science, software engineering, and systems principles."}

Output your analysis in STRICT accordance with these three sections:
### 1. VERIFIED FACTS & DIRECT EVIDENCE
(Concrete, indisputable physical or architectural properties verified by specifications, source code, or standards.)

### 2. ARCHITECTURAL & TECHNICAL INFERENCES
(Logical deductions derived from verified facts, trade-offs, and operational mechanics.)

### 3. KNOWN UNCERTAINTIES & SYSTEM CONSTRAINTS
(Open questions, hardware limitations, unverified assumptions, and empirical boundary conditions.)"""

        synth_res = llm_client.chat(
            messages=[
                {"role": "system", "content": "You are a senior systems researcher. Maintain strict separation between verified facts, logical inferences, and empirical uncertainties."},
                {"role": "user", "content": synthesis_prompt}
            ],
            temperature=0.2,
            think=False,
            task_budget=TaskBudget.RESEARCH
        )

        synthesis_content = synth_res.get("content", "").strip()

        # 4. Archive into research_index.db
        item_id = f"res-{uuid.uuid4().hex[:10]}"
        research_url = f"local://research/{item_id}"
        research_indexer.db.insert_item(
            source_id="src-hn-tech",  # reuse existing source relation
            url=research_url,
            title=f"Deep Research: {query[:60]}",
            snippet=synthesis_content[:300] + "...",
            content=synthesis_content,
            published_date=datetime.now().isoformat(),
            freshness_category="deep_research"
        )

        return {
            "query": query,
            "subqueries": subqueries,
            "evidence_count": len(evidence_items),
            "synthesis": synthesis_content,
            "archived_id": item_id,
            "archived_url": research_url
        }

    def generate_youtube_concept(
        self,
        topic: str,
        niche: str = "bodybuilding_motivation"
    ) -> Dict[str, Any]:
        """
        Generates a high-retention YouTube package for 'Mr Mysto':
        - 0-15s Hook Options (scored on retention pull)
        - Retention Beat Outline (Story/Demonstration/Climax)
        - 3 Tested Title & Description pairs
        - Gating: Explicitly tags any publish action as Restricted (Requires Approval).
        """
        logger.info(f"Generating YouTube concept for topic: {topic} (niche={niche})")

        # Fetch relevant channel preferences from memory
        channel_mems = memory_adapter.search(query="Mr Mysto YouTube bodybuilding audience retention", project="mr_mysto", limit=3)
        context_notes = [m.get("title") for m in channel_mems]

        prompt = f"""You are the creative strategist and script director for the YouTube channel 'Mr Mysto'.
Niche: {niche} (Bodybuilding, physical transformation, discipline, mental resilience, no-nonsense lifting).
Operator: Batman (21yo, student lifter, direct first-principles mentality).
Audience: Young men training hard, wanting reality over fake influencer aesthetics.

Topic: "{topic}"
Channel Context Notes: {json.dumps(context_notes)}

Generate an end-to-end production package containing:
1. HOOK OPTIONS (0–15 Seconds):
   - Provide 2 contrasting spoken hook options.
   - For each hook, state the Psychological Trigger (e.g. Curiosity Gap, Status Threat, Counter-Intuitive Truth) and Estimated Retention Score (/10).
2. CORE RETENTION BEAT OUTLINE:
   - Beat 1 (0:15 - 1:30): The Common Lie / Mistake.
   - Beat 2 (1:30 - 4:00): The Biomechanical / Psychological Mechanism (First principles).
   - Beat 3 (4:00 - 7:00): The Practical Protocol / Execution in the Gym.
   - Beat 4 (7:00 - End): The Reality Check & Call to Focus.
3. PACKAGING (3 Title & Description Pairs):
   - Pair A: Direct Curiosity (Short, punchy, high CTR).
   - Pair B: Counter-Intuitive / Bold Claim.
   - Pair C: Pure First-Principles / Utility.
   Each with a 2-line SEO description and 5 essential tags.
4. PUBLICATION GATEWAY NOTICE:
   - Explicit confirmation that publishing requires Level 3 Operator Approval."""

        res = llm_client.chat(
            messages=[
                {"role": "system", "content": "You are a professional YouTube production strategist. Deliver high-retention video architectures."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            think=False,
            task_budget=TaskBudget.RESEARCH
        )

        package_text = res.get("content", "").strip()

        return {
            "topic": topic,
            "niche": niche,
            "package": package_text,
            "requires_approval_for_publish": True,
            "approval_level": 3
        }


assistant = PersonalAssistant()
