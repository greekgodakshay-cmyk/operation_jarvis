"""
Comprehensive Forensic Verification & Repair Test Suite for:
Operation JARVIS Tool Execution, Real Database Queries, Browser State & Status Discrepancy

Verifies:
1. Tool pipeline execution (tool call parsing, dispatch, execution, observation loop).
2. Real SQLite FTS5 database queries with verified schemas and record provenance.
3. Live web search returning actual current-day articles and source citations without hallucinations.
4. Browser status and list pages returning live system data.
5. Gmail indeterminate state handling: rejected by verifier, failed by orchestrator (NEVER COMPLETED).
6. Tool count parity between /status and /tools.
"""
import os
import sys
import uuid
import sqlite3
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

LOCAL_AI_MEMORY_DIR = Path(r"C:\Users\Akshay aravind .rv\LOCAL_AI_MEMORY")
if str(LOCAL_AI_MEMORY_DIR) not in sys.path:
    sys.path.insert(0, str(LOCAL_AI_MEMORY_DIR))

from registry.capability_registry import capability_registry
from registry.browser_adapter import browser_adapter
from registry.memory_adapter import memory_adapter
from registry.internet_gateway import internet_gateway
from core.types import TaskStatus, StepStatus, ExecutionStep, ToolResult, TaskPlan
from core.verification import verification_engine
from core.orchestrator import orchestrator
from storage.task_db import task_db
from engine.qwen_chat import QwenMemoryAgent


class TestToolExecutionAndForensicRepair:

    @classmethod
    def setup_class(cls):
        cls.agent = QwenMemoryAgent()
        cls.db_path = r"C:\Users\Akshay aravind .rv\LOCAL_AI_MEMORY\07_MEMORY_INDEX\memory.db"

    # 1. TOOL DISCOVERY & COUNT PARITY (/status vs /tools)
    def test_01_tool_count_parity_between_status_and_tools(self):
        """Verify /status and /tools report identical total discoverable tool counts (55+)."""
        status_text, status_meta = self.agent.handle_slash_commands("/status")
        tools_text, tools_meta = self.agent.handle_slash_commands("/tools")

        assert status_meta is not None
        assert tools_meta is not None

        all_tools = self.agent.tool_registry.list_tools()
        total_tools_count = len(all_tools)

        # Both /status and /tools must reflect the unified capability count (55)
        assert total_tools_count >= 55
        assert f"{total_tools_count} registered tools" in status_text
        assert len(tools_meta.get("tools", [])) == total_tools_count

    # 2. REAL SQLITE DATABASE SCHEMA & BM25 FTS5 EVIDENCE
    def test_02_real_sqlite_memory_database_schema_and_query(self):
        """Verify real SQLite schema, tables (memories, memories_fts), and BM25 search without assumptions."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        # Check real table existence
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('memories', 'memories_fts');")
        tables = [r[0] for r in cur.fetchall()]
        assert "memories" in tables
        assert "memories_fts" in tables

        # Direct SQL FTS5 query
        cur.execute("SELECT id, title, rank FROM memories_fts WHERE memories_fts MATCH 'architecture' ORDER BY rank LIMIT 3;")
        fts_rows = cur.fetchall()
        assert len(fts_rows) > 0
        first_id, first_title, first_rank = fts_rows[0]
        assert first_id is not None
        assert len(first_title) > 0
        conn.close()

        # Search via memory_adapter
        mem_results = memory_adapter.search("architecture", limit=3)
        assert len(mem_results) > 0
        assert mem_results[0]["id"] == first_id

        # Verify step verification passes with real DB evidence
        step = ExecutionStep(step_number=1, description="Search memory", tool_name="memory_search", tool_arguments={"query": "architecture"})
        tool_res = ToolResult(call_id="call_test_mem", tool_name="memory_search", success=True, output=mem_results)
        verif = verification_engine.verify_step_result(step, tool_res)
        assert verif.is_verified is True
        assert "Database FTS5 search returned" in verif.evidence
        assert first_id in verif.evidence

    # 3. LIVE WEB SEARCH RETRIEVES REAL CURRENT-DAY CITATIONS
    def test_03_live_web_search_returns_actual_sources(self):
        """Verify web_search returns live citations with URLs, timestamps, and real data (not hallucinated)."""
        search_res = internet_gateway.unified_search(query="NVIDIA", max_results=3)
        assert search_res.get("count", 0) >= 1
        sources = search_res.get("sources", [])
        assert len(sources) >= 1

        first = sources[0]
        assert "url" in first and first["url"].startswith("http")
        assert "title" in first and len(first["title"]) > 0
        assert "retrieval_timestamp" in first

        # Verification engine must verify real web sources
        step = ExecutionStep(step_number=1, description="Web search", tool_name="web_search", tool_arguments={"query": "NVIDIA"})
        tool_res = ToolResult(call_id="call_test_web", tool_name="web_search", success=True, output=search_res)
        verif = verification_engine.verify_step_result(step, tool_res)
        assert verif.is_verified is True
        assert "Live search retrieved" in verif.evidence

    # 4. BROWSER STATUS AND LIST PAGES LIVE DATA
    def test_04_browser_status_and_list_pages_live_execution(self):
        """Verify browser_status and browser_list_pages return real process and page data."""
        # 1. browser_status
        status_res = browser_adapter.get_status()
        assert status_res.get("ok") is True
        assert "chrome" in status_res
        assert status_res["chrome"].get("running") is True

        # 2. browser_list_pages
        pages_res = browser_adapter.list_pages()
        assert pages_res.get("ok") is True
        assert "pages" in pages_res
        assert "## Pages" in pages_res["pages"] or "about:blank" in pages_res["pages"]

        # Step verification
        step_pages = ExecutionStep(step_number=1, description="List pages", tool_name="browser_list_pages", tool_arguments={})
        tool_res_pages = ToolResult(call_id="call_test_pages", tool_name="browser_list_pages", success=True, output=pages_res)
        verif_pages = verification_engine.verify_step_result(step_pages, tool_res_pages)
        assert verif_pages.is_verified is True
        assert "live session data" in verif_pages.evidence

    # 5. INDETERMINATE GMAIL SESSION MUST NEVER REPORT COMPLETED
    def test_05_indeterminate_gmail_session_is_failed_never_completed(self, monkeypatch):
        """Verify that indeterminate Gmail session state is strictly rejected and never marked COMPLETED."""
        monkeypatch.setenv("JARVIS_GMAIL_MOCK_STATE", "indeterminate")

        # 1. Adapter must return INDETERMINATE with current_url None and browser_access indeterminate
        gmail_res = browser_adapter.read_gmail(date_query="5 November 2026")
        assert gmail_res["ok"] is False
        assert gmail_res["status"] == "INDETERMINATE"
        assert gmail_res["browser_access"] == "indeterminate"
        assert gmail_res["current_url"] is None
        assert gmail_res["emails_found"] == 0

        # 2. Step verification must reject INDETERMINATE
        step = ExecutionStep(step_number=1, description="Read Gmail", tool_name="browser_read_gmail", tool_arguments={})
        tool_res = ToolResult(call_id="call_test_indet", tool_name="browser_read_gmail", success=False, output=gmail_res, error=gmail_res["error"])
        verif = verification_engine.verify_step_result(step, tool_res)
        assert verif.is_verified is False
        assert "INDETERMINATE" in verif.evidence

        # 3. Orchestrator must immediately halt task and mark FAILED, never COMPLETED
        test_task_id = f"test_indet_{uuid.uuid4().hex[:8]}"
        record = task_db.create_task(
            objective="Inspect Chrome Gmail session and summarize emails from 5 November 2026",
            task_id=test_task_id
        )
        plan = TaskPlan(
            objective=record.objective,
            reasoning="Read Gmail then summarize",
            steps=[
                ExecutionStep(
                    step_number=1,
                    description="Read Gmail inbox",
                    tool_name="browser_read_gmail",
                    tool_arguments={"date_query": "5 November 2026"}
                ),
                ExecutionStep(
                    step_number=2,
                    description="Summarize retrieved emails",
                    tool_name=None,
                    tool_arguments={}
                )
            ]
        )
        task_db.save_plan(test_task_id, plan)

        completed_record = orchestrator._run_execution_loop(test_task_id)

        # STRICT VERIFICATION: MUST BE FAILED OR BLOCKED, NEVER COMPLETED
        assert completed_record.status == TaskStatus.FAILED or completed_record.status == TaskStatus.BLOCKED
        assert completed_record.status != TaskStatus.COMPLETED
        # Step 2 must never have executed
        completed_step_nums = [s.step_number for s in completed_record.completed_steps]
        assert 2 not in completed_step_nums

    # 6. TOOL INVOCATION DISPATCH IN QWEN CHAT REGISTRY
    def test_06_qwen_tool_registry_dispatches_and_executes(self):
        """Verify Qwen ToolRegistry dispatches web_search, memory_search, and browser tools returning real data."""
        # 1. web_search
        ws_res = self.agent.tool_registry.execute_tool("web_search", {"query": "NVIDIA", "max_results": 2})
        assert "sources" in ws_res
        assert ws_res.get("count", 0) >= 1

        # 2. memory_search
        ms_res = self.agent.tool_registry.execute_tool("memory_search", {"query": "architecture"})
        assert ms_res.get("ok") is True
        assert ms_res.get("count", 0) >= 1
        assert len(ms_res.get("results", [])) >= 1

        # 3. browser_status
        bs_res = self.agent.tool_registry.execute_tool("browser_status", {})
        assert bs_res.get("ok") is True
        assert bs_res.get("chrome", {}).get("running") is True

        # 4. browser_list_pages
        blp_res = self.agent.tool_registry.execute_tool("browser_list_pages", {})
        assert blp_res.get("ok") is True
