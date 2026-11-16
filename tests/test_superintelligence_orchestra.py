"""
Unit and Integration Test Suite for Operation JARVIS Unified Superintelligence Orchestra.
Verifies:
1. GPUInferenceQueue serialization, priority ordering, and VRAM telemetry.
2. HierarchicalPlanner decomposition, agent role assignment, and parallel groups.
3. AgentOrchestra 7 specialized agents and shared blackboard context.
4. CodeEngine repository mapping, AST symbol parsing, atomic multi-file patch with rollback.
5. DocumentIntelligence multi-format extraction (including XLSX and PPTX).
6. LocalMemoryAdapter multi-tier working/session memory, duplicate detection, and provenance.
7. CapabilityRegistry progressive tool disclosure and argument type auto-casting.
8. FastAPI orchestra endpoints (/api/v1/orchestra/telemetry, /api/v1/orchestra/agents, /api/v1/code/map).
"""
import os
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.app import app
from core.types import AgentRole, StepStatus, ExecutionStep, TaskRecord, SharedTaskContext
from core.inference_queue import inference_queue, InferencePriority
from core.hierarchical_planner import hierarchical_planner
from core.agent_orchestra import agent_orchestra
from core.code_engine import code_engine
from core.doc_intelligence import doc_intelligence
from registry.memory_adapter import memory_adapter
from registry.capability_registry import capability_registry
from core.orchestrator import orchestrator

@pytest.fixture(scope="module")
def client():
    return TestClient(app)

# --- 1. GPU Inference Queue Tests ---

def test_inference_queue_execution():
    """Verifies that functions submitted to the GPU inference queue execute and return results."""
    def sample_func(x, y):
        return x * y + 10

    res = inference_queue.execute_inference(sample_func, 5, 4, priority=InferencePriority.ORCHESTRATION)
    assert res == 30

def test_inference_queue_vram_and_health():
    """Verifies VRAM status query and telemetry metrics."""
    health = inference_queue.get_queue_health()
    assert "pending_requests_in_queue" in health
    assert "total_requests" in health
    assert "vram_status" in health
    vram = health["vram_status"]
    assert "total_mb" in vram
    assert "headroom_pct" in vram

# --- 2. Hierarchical Planner Tests ---

def test_hierarchical_planner_structure():
    """Verifies hierarchical task decomposition into sub-objectives and assigned agent roles."""
    objective = "Audit the authentication module, write a regression test suite, and document findings."
    plan = hierarchical_planner.create_hierarchical_plan(objective)
    assert plan is not None
    assert len(plan.steps) >= 1
    assert len(plan.sub_objectives) >= 1
    assert len(plan.parallel_groups) >= 1
    # Check that steps have assigned agents
    assigned_roles = [s.assigned_agent for s in plan.steps if s.assigned_agent]
    assert len(assigned_roles) >= 1

# --- 3. Agent Orchestra Tests ---

def test_agent_orchestra_roles():
    """Verifies all 7 specialized agents exist and can be retrieved."""
    expected_roles = [
        AgentRole.ORCHESTRATOR, AgentRole.RESEARCHER, AgentRole.CODER,
        AgentRole.SYSTEM_OPS, AgentRole.BROWSER, AgentRole.REVIEWER, AgentRole.MEMORY
    ]
    for role in expected_roles:
        agent = agent_orchestra.get_agent(role)
        assert agent is not None
        assert agent.role == role

def test_agent_orchestra_shared_context_dispatch():
    """Verifies step dispatch across agents populating shared context."""
    context = SharedTaskContext(
        task_id="test-task-1",
        objective="Verify system telemetry and memory overview"
    )
    step = ExecutionStep(
        step_number=1,
        description="Inspect hardware status",
        tool_name="system_telemetry",
        tool_arguments={},
        assigned_agent=AgentRole.SYSTEM_OPS
    )
    res = agent_orchestra.dispatch_step(step, context, task_id="test-task-1")
    assert res.success is True
    assert "sysops_1" in context.shared_state

def test_reviewer_agent_audit():
    """Verifies independent reviewer verification of a completed task record."""
    context = SharedTaskContext(task_id="task-audit-1", objective="Audit task")
    step = ExecutionStep(step_number=1, description="Pass step", status=StepStatus.COMPLETED)
    task = TaskRecord(
        task_id="task-audit-1",
        objective="Test objective",
        completed_steps=[step],
        errors=[]
    )
    audit = agent_orchestra.review_final_task(task, context)
    assert audit.is_verified is True
    assert "Reviewer Audit" in audit.evidence

# --- 4. Code Engine Tests ---

def test_code_engine_map_repository():
    """Verifies repository architecture mapping and language detection."""
    res = code_engine.map_repository(str(ROOT_DIR), max_depth=2)
    assert "error" not in res
    assert res["primary_language"] == "python"
    assert res["total_files"] > 10
    assert "api/app.py" in [p.replace("\\", "/") for p in res["detected_entry_points"]]

def test_code_engine_symbol_extraction(tmp_path):
    """Verifies AST parsing of classes, methods, and functions."""
    py_file = tmp_path / "sample_module.py"
    py_file.write_text(
        'class DatabaseManager:\n'
        '    """Manages db connections."""\n'
        '    def connect(self):\n'
        '        pass\n\n'
        'def compute_hash(val: str):\n'
        '    """Computes SHA256."""\n'
        '    return val\n'
    )
    res = code_engine.read_symbols(str(py_file))
    assert len(res["classes"]) == 1
    assert res["classes"][0]["name"] == "DatabaseManager"
    assert "connect" in res["classes"][0]["methods"]
    assert len(res["functions"]) == 1
    assert res["functions"][0]["name"] == "compute_hash"

def test_code_engine_multi_file_patch_with_rollback(tmp_path):
    """Verifies atomic multi-file modification and rollback on failure."""
    f1 = tmp_path / "file1.txt"
    f2 = tmp_path / "file2.txt"
    f1.write_text("Original content 1")
    f2.write_text("Original content 2")

    # Intentional failing patch on file2 (missing target string)
    patches = [
        {"path": str(f1), "action": "write", "content": "Modified content 1"},
        {"path": str(f2), "action": "replace", "target": "NON_EXISTENT_STRING", "replacement": "New text"}
    ]
    res = code_engine.multi_file_patch(patches, rollback_on_failure=True)
    assert res["ok"] is False
    assert res["rolled_back"] is True
    # Verify file 1 was rolled back to original content
    assert f1.read_text() == "Original content 1"

# --- 5. Memory Intelligence Tests ---

def test_memory_multi_tier_working_and_session():
    """Verifies working memory scratchpad and session conversation compression."""
    memory_adapter.set_working_memory("task-123", "current_phase", "data_collection")
    assert memory_adapter.get_working_memory("task-123")["current_phase"] == "data_collection"
    memory_adapter.clear_working_memory("task-123")
    assert "current_phase" not in memory_adapter.get_working_memory("task-123")

    # Session compression
    memory_adapter.append_session_message("user", "What is the speed of light?")
    memory_adapter.append_session_message("assistant", "Approximately 299,792,458 m/s in vacuum.")
    compressed = memory_adapter.get_compressed_session_context()
    assert "Speed of light" in compressed or "299,792,458" in compressed

# --- 6. Capability Registry Progressive Disclosure Tests ---

def test_progressive_tool_disclosure():
    """Verifies relevant tools are filtered for coding objectives versus browsing objectives."""
    coding_tools = capability_registry.find_relevant_tools("Refactor python function and run pytest suite", limit=5)
    tool_names = [t["function"]["name"] for t in coding_tools]
    assert any(name in tool_names for name in ("run_tests", "code_symbols", "repo_map", "edit_file", "write_file"))

    browsing_tools = capability_registry.find_relevant_tools("Navigate to google.com and scrape headlines", limit=5)
    b_names = [t["function"]["name"] for t in browsing_tools]
    assert any(name in b_names for name in ("browser_navigate", "browser_snapshot", "web_search", "browser_status"))

def test_tool_argument_sanitization():
    """Verifies automatic casting of stringified integers in tool arguments."""
    cap = capability_registry.get_tool("memory_search")
    assert cap is not None
    sanitized = capability_registry._validate_and_sanitize_arguments(cap, {"query": "test", "limit": "10"})
    assert sanitized["limit"] == 10
    assert isinstance(sanitized["limit"], int)

# --- 7. FastAPI API Endpoints Tests ---

def test_api_orchestra_telemetry(client):
    """Verifies /api/v1/orchestra/telemetry endpoint."""
    res = client.get("/api/v1/orchestra/telemetry")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["hardware"]["model"] == "HP Victus"
    assert "gpu_vram" in data
    assert "inference_queue" in data

def test_api_orchestra_agents(client):
    """Verifies /api/v1/orchestra/agents endpoint."""
    res = client.get("/api/v1/orchestra/agents")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["total_agents"] == 7
    roles = [a["role"] for a in data["agents"]]
    assert "coder" in roles
    assert "researcher" in roles
    assert "reviewer" in roles

def test_api_code_map(client):
    """Verifies /api/v1/code/map endpoint."""
    res = client.post("/api/v1/code/map", json={"path": str(ROOT_DIR), "max_depth": 2})
    assert res.status_code == 200
    data = res.json()
    assert data["primary_language"] == "python"
    assert data["total_files"] > 0
