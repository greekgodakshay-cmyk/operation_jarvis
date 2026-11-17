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

    def conduct_deep_research(
        self,
        query: str,
        domain: str = "technical",
        reddit_authorized: bool = False,
        include_reddit: bool = False
    ) -> Dict[str, Any]:
        """
        Executes an advanced multi-source research workflow adhering to Section 8:
        1. Understand the research objective and comparison criteria.
        2. Retrieve primary technical documentation and Wikipedia foundational knowledge.
        3. Retrieve current benchmarks, specifications, or papers.
        4. Manage Reddit authorization explicitly (prompt if requested without prior approval).
        5. Retrieve Reddit community evidence only after explicit user approval.
        6. Compare retrieved evidence and distinguish verified facts, community opinions,
           reasoned conclusions, and uncertainties.
        7. Provide citations and original source links without permanent external data hoarding.
        """
        from registry.internet_gateway import internet_gateway
        logger.info(f"Conducting deep research for query: {query} (domain={domain}, reddit_auth={reddit_authorized})")

        # Check if Reddit authorization prompt should be returned
        needs_reddit = include_reddit or any(w in query.lower() for w in ["reddit", "community", "user experience", "developer opinion", "better for"])
        if needs_reddit and not reddit_authorized:
            return {
                "query": query,
                "requires_approval": True,
                "authorization_prompt": "I can answer using general knowledge and Wikipedia. Would you also like me to investigate Reddit discussions and real-world user experiences?",
                "message": "Reddit community research requires explicit user authorization before execution.",
                "subqueries": [query],
                "evidence_count": 0,
                "synthesis": "Pending Reddit authorization. To proceed with Reddit community research, grant authorization or re-run with approval.",
                "sources": []
            }

        # 1. Decompose Query
        subqueries = [query]
        if "compare" in query.lower() and " and " in query.lower():
            # Extract entities
            m = re.search(r"compare\s+([a-zA-Z0-9\+#\.]+)\s+and\s+([a-zA-Z0-9\+#\.]+)", query, re.IGNORECASE)
            if m:
                e1, e2 = m.group(1), m.group(2)
                subqueries = [
                    f"{e1} official documentation architecture",
                    f"{e2} official documentation architecture",
                    f"{e1} vs {e2} benchmarks performance"
                ]
        else:
            subqueries = [query, f"{query} documentation", f"{query} benchmarks analysis"]

        # 2. Gather Evidence Online (Zero-Footprint RAG)
        evidence_items = []
        source_links = []

        # Online Wikipedia retrieval
        wiki_hits = internet_gateway.search_wikipedia(query, limit=2)
        for w in wiki_hits:
            evidence_items.append({
                "type": "VERIFIED_FACT",
                "source": f"Wikipedia ({w['title']})",
                "url": w["url"],
                "content": w.get("extract") or w.get("snippet", "")
            })
            source_links.append({"title": w["title"], "url": w["url"]})

        # Online Technical Documentation retrieval
        for sq in subqueries[:2]:
            doc_hits = internet_gateway.search_technical_docs(sq, limit=2)
            for d in doc_hits:
                evidence_items.append({
                    "type": "TECHNICAL_SPEC",
                    "source": d.get("publisher", "Technical Docs"),
                    "url": d.get("url", ""),
                    "content": d.get("snippet", "")
                })
                if d.get("url"):
                    source_links.append({"title": d.get("title", "Technical Documentation"), "url": d["url"]})

        # Online Benchmarks & Research Papers (arXiv)
        arxiv_hits = internet_gateway.search_arxiv(query, max_results=2)
        for a in arxiv_hits:
            evidence_items.append({
                "type": "BENCHMARK_AND_RESEARCH",
                "source": f"arXiv ({a['title']})",
                "url": a["url"],
                "content": a.get("snippet", "")
            })
            source_links.append({"title": a["title"], "url": a["url"]})

        # Online Reddit Community Research (ONLY IF AUTHORIZED)
        if reddit_authorized:
            reddit_res = internet_gateway.search_reddit(query, authorized=True, limit=3)
            for disc in reddit_res.get("discussions", []):
                evidence_items.append({
                    "type": "COMMUNITY_OPINION",
                    "source": f"Reddit ({disc.get('subreddit')})",
                    "url": disc.get("url", ""),
                    "content": disc.get("snippet", "")
                })
                if disc.get("url"):
                    source_links.append({"title": disc.get("title", "Reddit Thread"), "url": disc["url"]})

        # Local personal memory integration
        mem_hits = memory_adapter.search(query, limit=2)
        for m in mem_hits:
            evidence_items.append({
                "type": "PERSONAL_MEMORY",
                "source": "Local SQLite Memory",
                "url": f"local://memory/{m.get('id')}",
                "content": m.get("snippet", "")
            })

        evidence_text = "\n".join([
            f"[{e['type']}] Source: {e['source']} | URL: {e['url']}\nDetails: {e['content']}"
            for e in evidence_items
        ])

        # 3. Local Model Synthesis (Distinguishing Facts, Community Opinions, Conclusions, Uncertainties)
        synthesis_prompt = f"""Conduct a deep comparative evaluation for:
Objective: "{query}"

Retrieved Multi-Source Evidence:
{evidence_text if evidence_text else "Base evaluation on established computer science, software engineering, and systems principles."}

Output your analysis in STRICT accordance with these four numbered sections:
### 1. VERIFIED FACTS & SPECIFICATIONS
(Concrete, indisputable physical/architectural properties verified by official documentation, language specifications, or compiler guarantees.)

### 2. COMMUNITY EXPERIENCES & ANECDOTAL OPINIONS
(Real-world developer discussions, community consensus, productivity feedback from forums and Reddit. Explicitly identify these as subjective experiences, not scientific laws.)

### 3. REASONED CONCLUSIONS & ARCHITECTURAL TRADE-OFFS
(Logical deductions comparing performance, ergonomics, safety guarantees, ecosystem maturity, and maintenance costs.)

### 4. UNCERTAIN OR UNAVAILABLE INFORMATION
(Empirical limitations, unverified benchmark boundary conditions, and areas where conclusive data is unavailable.)

Conclude with numbered source citations containing original links."""

        synth_res = llm_client.chat(
            messages=[
                {"role": "system", "content": "You are a senior AI systems architect and researcher. Strictly separate verified facts, community opinions, reasoned conclusions, and empirical uncertainties."},
                {"role": "user", "content": synthesis_prompt}
            ],
            temperature=0.2,
            think=False,
            task_budget=TaskBudget.RESEARCH
        )

        synthesis_content = synth_res.get("content", "").strip()

        return {
            "query": query,
            "subqueries": subqueries,
            "evidence_count": len(evidence_items),
            "synthesis": synthesis_content,
            "sources": source_links,
            "requires_approval": False
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
