"""
Adapter for Persistent Local AI Memory Ecosystem (LOCAL_AI_MEMORY).
Integrates seamlessly with existing SQLite FTS5 database, category budgets, and writer logic.
"""
import os
import sys
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from config.settings import settings

# Ensure engine package is importable
memory_root_str = str(settings.memory_root)
if memory_root_str not in sys.path:
    sys.path.insert(0, memory_root_str)

from engine.db import MemoryDB
from engine.indexer import MemoryIndexer
from engine.retriever import MemoryRetriever
from engine.writer import MemoryWriter
from engine.monitor import StorageMonitor

class LocalMemoryAdapter:
    def __init__(self, memory_root: Optional[Path] = None):
        self.root = memory_root or settings.memory_root
        self.db_path = settings.memory_db_path
        self.config_path = settings.memory_config_path

        self.db = MemoryDB(str(self.db_path))
        self.indexer = MemoryIndexer(str(self.root), self.db)
        self.retriever = MemoryRetriever(self.db, str(self.root))
        self.writer = MemoryWriter(str(self.root), self.db, self.indexer, self.retriever)
        self.monitor = StorageMonitor(str(self.root), str(self.config_path), self.db)

        # Multi-tier memory stores
        self._working_memory: Dict[str, Dict[str, Any]] = {}
        self._session_memory: List[Dict[str, str]] = []

    def get_working_memory(self, task_id: str) -> Dict[str, Any]:
        """Returns temporary working scratchpad for an active task."""
        return self._working_memory.get(task_id, {})

    def set_working_memory(self, task_id: str, key: str, value: Any):
        """Sets a key in active task working scratchpad."""
        if task_id not in self._working_memory:
            self._working_memory[task_id] = {}
        self._working_memory[task_id][key] = value

    def clear_working_memory(self, task_id: str):
        """Cleans up task working memory upon task completion."""
        self._working_memory.pop(task_id, None)

    def append_session_message(self, role: str, content: str):
        """Appends to short-term session conversation buffer."""
        self._session_memory.append({"role": role, "content": content})
        if len(self._session_memory) > 30:
            # Keep recent 25 messages, compress older
            self._session_memory = self._session_memory[-25:]

    def get_compressed_session_context(self, max_tokens: int = 1500) -> str:
        """Compresses session memory into compact markdown bullets."""
        if not self._session_memory:
            return ""
        lines = []
        for msg in self._session_memory[-10:]:
            lines.append(f"- **{msg['role'].capitalize()}**: {msg['content'][:180]}")
        return "\n".join(lines)

    def detect_duplicate_or_contradiction(self, title: str, content: str, project: Optional[str] = None) -> Dict[str, Any]:
        """
        Inspects existing records to identify duplicates or contradictions/supersessions
        before storing new memories.
        """
        existing = self.search(query=title, project=project, limit=5)
        title_lower = title.strip().lower()
        title_words = set(re.findall(r"\w+", title_lower)) - {"a", "an", "the", "in", "on", "for", "of", "and", "or", "is", "sacrificial"}

        for item in existing:
            item_title = item.get("title", "").lower()
            if title_lower == item_title:
                return {
                    "has_conflict": True,
                    "conflict_type": "exact_duplicate_title",
                    "matched_id": item.get("id"),
                    "matched_title": item.get("title"),
                    "recommendation": "Use memory_update with revision changelog instead of duplicate store."
                }
            
            # Check for semantic contradiction / supersession
            item_words = set(re.findall(r"\w+", item_title)) - {"a", "an", "the", "in", "on", "for", "of", "and", "or", "is", "sacrificial"}
            overlap = title_words.intersection(item_words)
            
            supersession_terms = {"migrate", "migrated", "migration", "deprecate", "deprecated", "deprecation", 
                                  "replace", "replaced", "moved", "changed", "superseded", "collision", "upgrade"}
            content_lower = content.lower()
            has_supersession_intent = any(term in content_lower or term in title_lower for term in supersession_terms)

            if len(overlap) >= 2 and has_supersession_intent:
                return {
                    "has_conflict": True,
                    "conflict_type": "entity_attribute_supersession",
                    "matched_id": item.get("id"),
                    "matched_title": item.get("title"),
                    "overlapping_terms": list(overlap),
                    "recommendation": f"New memory supersedes or contradicts '{item.get('title')}'. Archive or update older record."
                }

        return {"has_conflict": False, "conflict_type": None}

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        project: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Searches BM25 SQLite FTS5 memory index with timestamp supersession awareness
        and recency tie-breaking.
        """
        raw_results = self.retriever.search(
            query=query,
            category=category,
            project=project,
            limit=limit * 2
        )
        if not raw_results:
            return []

        # Analyze supersession relationships by entity and timestamps
        annotated: List[Dict[str, Any]] = []
        seen_topics: Dict[str, str] = {} # topic_key -> latest_id

        # First pass: sort chronologically to identify supersession
        # Sort by updated_at descending
        sorted_by_date = sorted(raw_results, key=lambda x: x.get("updated_at") or "", reverse=True)
        
        superseded_ids = set()
        for i, item in enumerate(sorted_by_date):
            words = set(re.findall(r"\w+", item.get("title", "").lower())) - {"a", "an", "the", "for", "in", "on", "of", "sacrificial"}
            snippet_words = set(re.findall(r"\w+", item.get("snippet", "").lower()))
            combined_terms = words.union(snippet_words)
            
            # Check if this older item was superseded by an earlier (newer) item
            for newer_item in sorted_by_date[:i]:
                newer_words = set(re.findall(r"\w+", newer_item.get("title", "").lower())) - {"a", "an", "the", "for", "in", "on", "of", "sacrificial"}
                shared = words.intersection(newer_words)
                newer_snippet = newer_item.get("snippet", "").lower()
                if len(shared) >= 2 and any(t in newer_snippet for t in ["migrated", "deprecated", "moved", "superseded", "changed"]):
                    superseded_ids.add(item.get("id"))
                    item["is_superseded"] = True
                    item["superseded_by"] = newer_item.get("id")
                    item["snippet"] = f"[SUPERSEDED by {newer_item.get('id')}]: {item.get('snippet')}"
                    break

        # Re-sort giving preference to non-superseded recent records while respecting BM25
        # Penalize superseded records in rank
        for item in raw_results:
            if item.get("id") in superseded_ids:
                item["is_superseded"] = True
                # Increase BM25 rank value (in SQLite BM25, lower/more negative is better)
                item["rank"] = item.get("rank", 0.0) + 10.0
            else:
                item["is_superseded"] = False

        raw_results.sort(key=lambda x: (x.get("is_superseded", False), x.get("rank", 0.0)))
        return raw_results[:limit]

    def store(
        self,
        title: str,
        content: str,
        category: Optional[str] = None,
        project: str = "global",
        importance: str = "normal",
        tags: Optional[List[str]] = None,
        source: str = "operation_jarvis",
        confidence: float = 1.0,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Stores a new verified memory record with provenance tracking and duplicate guard."""
        conflict = self.detect_duplicate_or_contradiction(title, content)
        if conflict["has_conflict"] and conflict["conflict_type"] == "exact_duplicate_title":
            matched_id = conflict["matched_id"]
            return self.update(
                target_id_or_title=matched_id or title,
                content=content,
                changelog=f"Automatic non-destructive update from task {task_id or source}",
                category=category,
                importance=importance
            )

        provenance_tag = f"provenance:task={task_id or 'direct'}|conf={confidence}"
        merged_tags = list(tags or [])
        if provenance_tag not in merged_tags:
            merged_tags.append(provenance_tag)

        return self.writer.store(
            title=title,
            content=content,
            category=category,
            project=project,
            importance=importance,
            tags=merged_tags,
            source=source
        )

    def update(
        self,
        target_id_or_title: str,
        content: str,
        changelog: str,
        category: Optional[str] = None,
        importance: Optional[str] = None
    ) -> Dict[str, Any]:
        """Updates an existing memory record with version tracking."""
        return self.writer.update(
            target=target_id_or_title,
            content=content,
            changelog=changelog,
            category=category,
            importance=importance
        )

    def get(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single memory record by its ID."""
        row = self.db.find_by_id(memory_id)
        if not row:
            return None
        return dict(row)

    def get_status(self) -> Dict[str, Any]:
        """Returns storage utilization across categories."""
        try:
            data = self.monitor.check_storage()
            data["healthy"] = len(data.get("alerts", [])) == 0
            return data
        except Exception as e:
            return {"healthy": False, "error": str(e), "total_used_mb": 0}

    def get_project_overview(self, project: str = "global") -> Dict[str, Any]:
        """Provides an aggregated overview of memory records by project."""
        try:
            with self.db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT count(*) FROM memories")
                total = cur.fetchone()[0]
                cur.execute("SELECT category, count(*) FROM memories GROUP BY category")
                cats = {r[0]: r[1] for r in cur.fetchall()}
                return {
                    "ok": True,
                    "project": project,
                    "total_memories": total,
                    "categories": cats
                }
        except Exception as e:
            return {"ok": False, "error": str(e), "total_memories": 0}

memory_adapter = LocalMemoryAdapter()
