"""
Sequential Thinking Adapter for Operation JARVIS.
Adapts the Model Context Protocol (MCP) sequentialthinking reference implementation for in-memory reflective reasoning.
"""
from typing import Any, Dict, List, Optional

class SequentialThinkingSession:
    def __init__(self):
        self.thoughts: List[Dict[str, Any]] = []
        self.branches: Dict[str, List[Dict[str, Any]]] = {}

    def add_thought(
        self,
        thought: str,
        thought_number: int,
        total_thoughts: int,
        next_thought_needed: bool,
        is_revision: bool = False,
        revises_thought: Optional[int] = None,
        branch_from_thought: Optional[int] = None,
        branch_id: Optional[str] = None
    ) -> Dict[str, Any]:
        record = {
            "thought_number": thought_number,
            "total_thoughts": total_thoughts,
            "thought": thought,
            "is_revision": is_revision,
            "revises_thought": revises_thought,
            "branch_from_thought": branch_from_thought,
            "branch_id": branch_id,
            "next_thought_needed": next_thought_needed
        }

        if branch_id:
            if branch_id not in self.branches:
                self.branches[branch_id] = []
            self.branches[branch_id].append(record)

        self.thoughts.append(record)

        return {
            "ok": True,
            "thought_number": thought_number,
            "total_thoughts": total_thoughts,
            "next_thought_needed": next_thought_needed,
            "branches_count": len(self.branches),
            "thought_history_length": len(self.thoughts),
            "summary": f"Thought {thought_number}/{total_thoughts} recorded ({'branch: ' + branch_id if branch_id else 'main line'})."
        }

    def reset(self):
        self.thoughts.clear()
        self.branches.clear()

_session = SequentialThinkingSession()

def tool_sequential_thinking(
    thought: str,
    thought_number: int,
    total_thoughts: int,
    next_thought_needed: bool,
    is_revision: Optional[bool] = False,
    revises_thought: Optional[int] = None,
    branch_from_thought: Optional[int] = None,
    branch_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes a step in dynamic sequential thinking:
    Facilitates step-by-step reasoning, hypothesis evaluation, revisions, and branching.
    """
    return _session.add_thought(
        thought=thought,
        thought_number=thought_number,
        total_thoughts=total_thoughts,
        next_thought_needed=next_thought_needed,
        is_revision=bool(is_revision),
        revises_thought=revises_thought,
        branch_from_thought=branch_from_thought,
        branch_id=branch_id
    )

def reset_sequential_thinking():
    _session.reset()
