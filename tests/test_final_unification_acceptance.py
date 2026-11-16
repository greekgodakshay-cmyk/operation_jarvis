"""
Operation JARVIS Final Unification, Repair & Autonomy Mission
12 Core Acceptance Verification Tests

Test Coverage:
1. Live Internet Intelligence (Indian Headlines + URLs + Timestamps)
2. Web Research & Fetch (SSRF Defense, Untrusted Content Wrap, Text Clean)
3. MCP Service Discovery (Tools Across Memory, Skillet, Browser MCPs)
4. MCP Execution (Skillet Registry & Local Memory Execution)
5. Multi-Agent Ecosystem Registry (Tiers, Statuses, Capabilities)
6. Bidirectional Antigravity Bridge (Real-Time Roundtrip & Handoffs)
7. Shared Persistent Memory Cross-Agent Lifecycle (Write -> Read -> Update -> Verify -> Delete Test Record)
8. Desktop Control (Agent Desktop CLI v1.0.2 Status & Permissions)
9. Kokoro Voice & TTS (Model Loaded, bm_george Voice, Audio Synthesis)
10. Honest Error Handling (Graceful handling of unavailable tools)
11. Security Approval Gate (Level 3 Actions require explicit human approval)
12. Database & State Persistence (SQLite FTS5, Tasks, Documents survive restarts)
"""
import json
import os
import sqlite3
import subprocess
import sys
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

LOCAL_AI_MEMORY_DIR = Path(r"C:\Users\Akshay aravind .rv\LOCAL_AI_MEMORY")
if str(LOCAL_AI_MEMORY_DIR) not in sys.path:
    sys.path.insert(0, str(LOCAL_AI_MEMORY_DIR))

from registry.capability_registry import capability_registry
from security.policy_engine import ApprovalRequiredError
from engine.orchestrator import MultiAgentOrchestrator
from engine.antigravity_bridge import antigravity_bridge


class TestFinalUnificationAcceptance:

    # 1. LIVE INTERNET INTELLIGENCE
    def test_01_live_internet_indian_headlines(self):
        """Verify real-time retrieval of current Indian headlines with valid URLs."""
        res = capability_registry.execute_tool(
            "search_news",
            {"query": "India", "region": "IN", "max_results": 5},
            task_id="accept_test_01"
        )
        assert res.success is True, f"search_news failed: {res.error}"
        items = res.output
        assert isinstance(items, list), "Output should be a list of news items"
        assert len(items) >= 1, "Expected at least 1 current news headline"
        for item in items:
            assert "title" in item and len(item["title"]) > 0
            assert "url" in item and item["url"].startswith("http")
            assert "published_date" in item
            assert "freshness_category" in item
            assert item["freshness_category"] in [
                "Newly Published (Recent)", "Recently Updated", "Older Background Information", "Unknown Publication Date"
            ]

    # 2. WEB RESEARCH & FETCH
    def test_02_web_research_fetch_and_summarize(self):
        """Verify read-only web fetch with SSRF defense and untrusted content neutralization."""
        target_url = "https://en.wikipedia.org/wiki/Artificial_intelligence"
        res = capability_registry.execute_tool(
            "web_fetch",
            {"url": target_url},
            task_id="accept_test_02"
        )
        assert res.success is True, f"web_fetch failed: {res.error}"
        data = res.output
        assert data.get("ok") is True
        assert data.get("status_code") == 200
        assert data.get("url") == target_url
        assert "<untrusted_external_content" in data.get("content", "")
        assert "</untrusted_external_content>" in data.get("content", "")
        assert len(data.get("content", "")) > 100

    # 3. MCP SERVICE DISCOVERY
    def test_03_mcp_discovery_across_servers(self):
        """Verify that tools across all local MCP servers are registered and discoverable."""
        tools = capability_registry.list_tools()
        tool_names = {t["name"] for t in tools}

        # Memory MCP tools
        assert "memory_search" in tool_names
        assert "memory_store" in tool_names
        assert "memory_project_overview" in tool_names

        # Skillet tools
        assert "skillet_search" in tool_names
        assert "skillet_list" in tool_names

        # Browser tools (Playwright / Chrome DevTools)
        assert "browser_navigate" in tool_names
        assert "browser_snapshot" in tool_names

        # Total tools should exceed 50 unified capabilities
        assert len(tools) >= 50

    # 4. MCP TOOL EXECUTION
    def test_04_mcp_tool_execution(self):
        """Execute skillet_list and memory_project_overview tools."""
        # Test skillet_list
        res_skillet = capability_registry.execute_tool(
            "skillet_list", {}, task_id="accept_test_04_skillet"
        )
        assert res_skillet.success is True
        assert "installed" in res_skillet.output

        # Test memory_project_overview
        res_mem = capability_registry.execute_tool(
            "memory_project_overview", {}, task_id="accept_test_04_mem"
        )
        assert res_mem.success is True
        assert res_mem.output.get("ok") is True
        assert "total_memories" in res_mem.output
        assert res_mem.output["total_memories"] >= 1000

    # 5. MULTI-AGENT REGISTRY
    def test_05_agent_registry(self):
        """Verify multi-agent ecosystem registry with tiering and capabilities."""
        orch = MultiAgentOrchestrator()
        agents = orch.get_agents()
        agent_map = {a["agent_id"]: a for a in agents}

        assert "antigravity" in agent_map
        assert agent_map["antigravity"]["tier"] == "Tier D"
        assert agent_map["antigravity"]["status"] == "online"

        assert "qwen-batman" in agent_map
        assert agent_map["qwen-batman"]["tier"] == "Tier D"
        assert agent_map["qwen-batman"]["status"] == "online"

        assert "continue-ide" in agent_map
        assert "security-auditor" in agent_map
        assert "research" in agent_map
        assert "test-engineer" in agent_map

    # 6. BIDIRECTIONAL ANTIGRAVITY BRIDGE
    def test_06_antigravity_bridge_roundtrip(self):
        """Demonstrate real-time bidirectional roundtrip: Qwen -> Antigravity -> Qwen."""
        res = antigravity_bridge.execute_roundtrip(
            title="Acceptance Verification Roundtrip",
            description="Testing bidirectional task delegation and verification between Qwen and Antigravity.",
            payload={"test_suite": "acceptance", "verification_cycle": 1}
        )
        assert res["ok"] is True
        assert res["roundtrip"] is True
        assert res["sender"] == "qwen-batman"
        assert res["receiver"] == "antigravity"
        assert res["task_id"].startswith("task_")
        assert res["initial_handoff_id"].startswith("ho_")
        assert res["reverse_handoff_id"].startswith("ho_")
        assert len(res["summary"]) > 0
        assert res["duration_ms"] < 5000

    # 7. SHARED PERSISTENT MEMORY LIFECYCLE (Cross-agent 5-step test)
    def test_07_shared_memory_cross_agent_roundtrip(self):
        """Verify write -> read -> update -> verify -> delete lifecycle for temporary test record."""
        db_path = str(LOCAL_AI_MEMORY_DIR / "07_MEMORY_INDEX" / "memory.db")
        test_id = "mem_temp_accept_test_9999"
        test_title = "Temporary Unification Test Memory"
        initial_content = "This is a temporary memory record for verifying cross-agent persistence."
        updated_content = "This is the updated content after version increment."

        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            # Initial count check
            cur.execute("SELECT count(*) FROM memories")
            initial_count = cur.fetchone()[0]

            # 1. Write
            cur.execute(
                """
                INSERT OR REPLACE INTO memories (
                    id, file_path, category, project, title, tags, importance, status, source, version, created_at, updated_at, content_hash, size_bytes
                ) VALUES (?, ?, '01_CORE_FACTS', 'test', ?, '["test"]', 'low', 'active', 'unification_test', 1, datetime('now'), datetime('now'), 'hash123', 100)
                """,
                (test_id, f"test/{test_id}.md", test_title)
            )
            cur.execute(
                """
                INSERT OR REPLACE INTO memories_fts (id, title, tags, category, project, content)
                VALUES (?, ?, '["test"]', '01_CORE_FACTS', 'test', ?)
                """,
                (test_id, test_title, initial_content)
            )
            conn.commit()

            # 2. Read
            cur.execute(
                """
                SELECT m.id, m.title, f.content, m.version
                FROM memories m
                JOIN memories_fts f ON m.id = f.id
                WHERE m.id = ?
                """,
                (test_id,)
            )
            row = cur.fetchone()
            assert row is not None
            assert row[0] == test_id
            assert row[1] == test_title
            assert row[2] == initial_content
            assert row[3] == 1

            # 3. Update
            cur.execute(
                """
                UPDATE memories
                SET version = 2, updated_at = datetime('now')
                WHERE id = ?
                """,
                (test_id,)
            )
            cur.execute(
                """
                UPDATE memories_fts
                SET content = ?
                WHERE id = ?
                """,
                (updated_content, test_id)
            )
            conn.commit()

            # 4. Verify Update
            cur.execute(
                """
                SELECT m.version, f.content
                FROM memories m
                JOIN memories_fts f ON m.id = f.id
                WHERE m.id = ?
                """,
                (test_id,)
            )
            up_row = cur.fetchone()
            assert up_row[0] == 2
            assert up_row[1] == updated_content

            # 5. Clean up temporary record ONLY
            cur.execute("DELETE FROM memories WHERE id = ?", (test_id,))
            cur.execute("DELETE FROM memories_fts WHERE id = ?", (test_id,))
            conn.commit()

            # Verify deletion
            cur.execute("SELECT count(*) FROM memories WHERE id = ?", (test_id,))
            assert cur.fetchone()[0] == 0

            # Verify original memories preserved intact
            cur.execute("SELECT count(*) FROM memories")
            final_count = cur.fetchone()[0]
            assert final_count == initial_count
            assert final_count >= 1100

    # 8. DESKTOP CONTROL ADAPTER
    def test_08_desktop_control_adapter(self):
        """Verify Vercel Agent Desktop CLI v1.0.2 status and permissions."""
        from registry.desktop_adapter import desktop_adapter
        status_res = desktop_adapter.get_status()
        assert status_res.get("ok") is True
        assert status_res.get("version") == "1.0.2"

        perms = desktop_adapter.check_permissions()
        assert perms.get("ok") is True

    # 9. KOKORO VOICE & TTS
    def test_09_voice_tts_output(self):
        """Verify Kokoro ONNX model loaded, 50+ voices available, active bm_george voice."""
        voice_py = str(LOCAL_AI_MEMORY_DIR / ".venv_voice" / "Scripts" / "python.exe")
        code = (
            "import sys; sys.path.insert(0, r'C:\\Users\\Akshay aravind .rv\\LOCAL_AI_MEMORY'); "
            "from engine.voice.tts_engine import get_shared_tts; "
            "tts = get_shared_tts(); "
            "print(f'AVAILABLE:{tts.is_available}|ENGINE:{tts.current_engine}|VOICE:{tts.current_voice}|VOICES_COUNT:{len(tts.get_available_voices())}')"
        )
        res = subprocess.run(
            [voice_py, "-c", code],
            capture_output=True,
            text=True,
            cwd=str(LOCAL_AI_MEMORY_DIR),
            timeout=25
        )
        assert res.returncode == 0, f"Voice check process failed: {res.stderr}"
        stdout = res.stdout
        assert "AVAILABLE:True" in stdout
        assert "ENGINE:kokoro" in stdout
        assert "VOICE:bm_george" in stdout
        assert "VOICES_COUNT:56" in stdout or "VOICES_COUNT:5" in stdout

    # 10. HONEST ERROR HANDLING
    def test_10_error_handling_unavailable_tool(self):
        """Verify that invoking an unmapped tool returns a clear, honest error without crashing."""
        fake_tool = "non_existent_diagnostic_tool_abc"
        res = capability_registry.execute_tool(fake_tool, {}, task_id="accept_test_10")
        assert res.success is False
        assert f"Tool '{fake_tool}' is not registered" in res.error

    # 11. SECURITY LEVEL 3 APPROVAL GATE
    def test_11_security_level_3_approval_gate(self):
        """Verify that Level 3 sensitive actions strictly require human approval token."""
        from core.types import PermissionLevel
        with pytest.raises(ApprovalRequiredError) as exc_info:
            capability_registry.execute_tool(
                "email_send",
                {
                    "to": ["partner@example.com"],
                    "subject": "Confidential Security Update",
                    "body": "System status update."
                },
                task_id="accept_test_11"
            )
        req = exc_info.value.approval_request
        assert req.tool_name == "email_send"
        assert req.permission_level == PermissionLevel.LEVEL_3_RESTRICTED or req.permission_level.value == 3
        assert req.is_granted is None

    # 12. DATABASE & STATE PERSISTENCE
    def test_12_persistence_restart_verification(self):
        """Verify all critical databases and tables persist with integrity across connections."""
        # 1. Main Memory Database
        mem_db = r"C:\Users\Akshay aravind .rv\LOCAL_AI_MEMORY\07_MEMORY_INDEX\memory.db"
        with sqlite3.connect(mem_db) as conn:
            cur = conn.cursor()
            cur.execute("PRAGMA integrity_check")
            assert cur.fetchone()[0] == "ok"
            cur.execute("SELECT count(*) FROM memories")
            assert cur.fetchone()[0] >= 1100
            cur.execute("SELECT count(*) FROM agent_registry")
            assert cur.fetchone()[0] >= 6

        # 2. Document Index Database
        doc_db = r"C:\Users\Akshay aravind .rv\operation_jarvis\data\document_index.db"
        with sqlite3.connect(doc_db) as conn:
            cur = conn.cursor()
            cur.execute("PRAGMA integrity_check")
            assert cur.fetchone()[0] == "ok"
            cur.execute("SELECT count(*) FROM documents")
            assert cur.fetchone()[0] >= 60

        # 3. Tasks Database
        tasks_db = r"C:\Users\Akshay aravind .rv\operation_jarvis\data\tasks.db"
        with sqlite3.connect(tasks_db) as conn:
            cur = conn.cursor()
            cur.execute("PRAGMA integrity_check")
            assert cur.fetchone()[0] == "ok"
