"""
Phase 1 Foundation and Reliability Regression Test Suite.
Tests:
1. Missing `re` import fix in api/app.py.
2. Model routing across qwen-batman, qwen-text, qwen3.5:9b, and cloud tiers.
3. OpenRouter privacy boundary enforcement.
4. Agent ecosystem discovery (reconciliation of the 6 agents from memory.db).
5. Error handling in TaskRecord (no AttributeError on .errors).
"""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from core.types import TaskRecord, TaskStatus
from core.model_router import model_router, ModelTier
from core.llm_client import llm_client
from registry.capability_registry import capability_registry
from api.app import is_action_objective

def test_is_action_objective_classification():
    assert is_action_objective("/task create a report") is True
    assert is_action_objective("/exec python test.py") is True
    assert is_action_objective("/do check memory") is True
    assert is_action_objective("What is the capital of France?") is False
    assert is_action_objective("Explain quantum computing") is False

def test_model_router_batman():
    res = model_router.route_task("Batman, can you check my internship project status?")
    assert res.selected_tier == ModelTier.LOCAL_QWEN_BATMAN
    assert res.model_name == "qwen-batman:latest"
    assert res.is_cloud is False

def test_model_router_qwen_text():
    res = model_router.route_task("Provide a deep dive theoretical analysis and first principles explanation of malware architecture")
    assert res.selected_tier == ModelTier.LOCAL_QWEN_TEXT
    assert res.model_name == "qwen-text:latest"
    assert res.is_cloud is False

def test_model_router_autonomous_execution():
    res = model_router.route_task("Create a python script to parse CSV files and verify output")
    assert res.selected_tier == ModelTier.LOCAL_QWEN
    assert res.model_name == "qwen3.5:9b"
    assert res.is_cloud is False

def test_model_router_privacy_boundary():
    # If cloud is requested but private markers (e.g. password, private key, local memory path) are present
    res = model_router.route_task("Cloud analysis for C:\\Users\\Akshay aravind .rv\\LOCAL_AI_MEMORY with api_key=secret123", prefer_local=False, allow_cloud_privacy=False)
    assert res.privacy_blocked_cloud is True
    assert res.is_cloud is False
    assert res.model_name in ("qwen-text:latest", "qwen3.5:9b")

def test_agent_discovery_capabilities():
    tools = {t["name"] for t in capability_registry.list_tools()}
    assert "agent_list" in tools
    assert "agent_status" in tools

    # Execute agent_list
    res_list = capability_registry.get_tool("agent_list").handler()
    assert res_list["ok"] is True
    assert res_list["count"] == 6
    agent_ids = {a["agent_id"] for a in res_list["agents"]}
    assert "antigravity" in agent_ids
    assert "qwen-batman" in agent_ids
    assert "continue-ide" in agent_ids
    assert "security-auditor" in agent_ids
    assert "research" in agent_ids
    assert "test-engineer" in agent_ids

    # Execute agent_status
    res_status = capability_registry.get_tool("agent_status").handler(agent_id="qwen-batman")
    assert res_status["ok"] is True
    assert res_status["agent"]["name"] == "Qwen 3.5 9B Local Coworker Agent"
    assert res_status["agent"]["tier"] == "Tier D"

def test_task_record_errors_attribute():
    rec = TaskRecord(task_id="t-test", objective="Test objective", status=TaskStatus.FAILED, errors=["Initial validation failed"])
    assert len(rec.errors) == 1
    assert rec.errors[0] == "Initial validation failed"
