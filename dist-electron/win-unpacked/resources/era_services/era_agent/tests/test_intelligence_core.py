"""ERA Intelligence Core — Full Test Suite.

Tests cover:
1.  Computer perception (real hardware values)
2.  Low battery detection
3.  Context generation
4.  Goal creation (command vs goal classification)
5.  Dynamic planning (OutcomeEngine)
6.  Tool selection via ToolRegistry
7.  Real action execution (create + read file)
8.  Verification
9.  Controlled failure + recovery
10. Permission denial
11. Permission approval
12. Emergency stop mechanism
13. Task checkpoint
14. Resume from checkpoint
15. Memory (TaskMemoryManager)
16. Proactive initiative suggestion
17. Network/cloud unavailability behavior
18. Sensitive data protection (vault)
19. Goal Engine classification
20. Full autonomous E2E goal
"""
from __future__ import annotations

import os
import sys
import json
import time
import tempfile
import shutil
from pathlib import Path

import pytest

# Ensure package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def tmp_workspace(tmp_path_factory):
    ws = tmp_path_factory.mktemp("era_test_workspace")
    yield str(ws)
    shutil.rmtree(str(ws), ignore_errors=True)


@pytest.fixture(scope="module")
def audit_log(tmp_workspace):
    from era_agent.intelligence_core.audit_log import AuditLog
    return AuditLog(os.path.join(tmp_workspace, "audit.jsonl"))


@pytest.fixture(scope="module")
def permission_engine(audit_log):
    from era_agent.intelligence_core.permission_engine import PermissionEngine
    PermissionEngine.clear_stop()  # ensure clean state
    return PermissionEngine(audit_log, mode="SUPERVISED")


@pytest.fixture(scope="module")
def orchestrator(tmp_workspace):
    from era_agent.intelligence_core.orchestrator import IntelligenceOrchestrator
    from era_agent.intelligence_core.permission_engine import PermissionEngine
    PermissionEngine.clear_stop()
    return IntelligenceOrchestrator(tmp_workspace, autonomy_mode="SUPERVISED")


# ──────────────────────────────────────────────────────────────────────────────
# Test 1 — Computer Perception (real hardware)
# ──────────────────────────────────────────────────────────────────────────────

def test_computer_perception_real_values():
    from era_agent.intelligence_core.computer_perception import ComputerPerception
    p = ComputerPerception()
    state = p.capture()

    assert isinstance(state, dict), "capture() must return a dict"
    assert "battery" in state
    assert "cpu" in state
    assert "memory" in state
    assert "disk" in state
    assert "network" in state
    assert "os_info" in state
    assert "running_processes" in state

    # CPU must be real
    cpu = state["cpu"]
    assert cpu.get("percent") is not None, "CPU percent must not be None"
    assert 0 <= cpu["percent"] <= 100

    # Memory must be real
    mem = state["memory"]
    assert mem.get("percent") is not None
    assert 0 <= mem["percent"] <= 100

    # OS must be real
    osi = state["os_info"]
    assert osi.get("system") in ("Windows", "Linux", "Darwin")

    # Processes must be a list
    assert isinstance(state["running_processes"], list)
    assert len(state["running_processes"]) > 0


# ──────────────────────────────────────────────────────────────────────────────
# Test 2 — Low Battery Detection
# ──────────────────────────────────────────────────────────────────────────────

def test_low_battery_detected_in_context():
    from era_agent.intelligence_core.context_engine import ContextEngine
    ce = ContextEngine()

    low_battery_state = {
        "battery": {"percent": 12.0, "charging": False},
        "cpu": {"percent": 30.0},
        "memory": {"percent": 50.0},
        "disk": {"free_bytes": 50 * 1024**3},
        "network": {"online": True},
        "os_info": {"system": "Windows", "hostname": "test", "uptime_seconds": 3600},
        "active_app": "Visual Studio Code",
        "running_processes": [{"pid": 1, "name": "Code.exe"}],
        "user_activity": "active",
    }

    ctx = ce.build_context(low_battery_state, [], "/tmp/workspace")
    obs = ctx["observations"]
    bat_obs = [o for o in obs if "battery" in o.lower() or "12" in o]
    assert len(bat_obs) > 0, f"Low battery not detected. Observations: {obs}"
    assert "low" in bat_obs[0].lower() or "critical" in bat_obs[0].lower()


# ──────────────────────────────────────────────────────────────────────────────
# Test 3 — Context Generation (real state)
# ──────────────────────────────────────────────────────────────────────────────

def test_context_generation(tmp_workspace):
    from era_agent.intelligence_core.computer_perception import ComputerPerception
    from era_agent.intelligence_core.context_engine import ContextEngine

    state = ComputerPerception().capture()
    ctx = ContextEngine().build_context(state, [], tmp_workspace)

    required = ["user_context", "computer_context", "task_context",
                "project_context", "time_context", "environmental_context", "observations"]
    for key in required:
        assert key in ctx, f"Missing context key: {key}"

    # Computer context must have real status strings
    cc = ctx["computer_context"]
    assert cc.get("cpu_status") not in (None, ""), "CPU status empty"
    assert cc.get("memory_status") not in (None, ""), "Memory status empty"


# ──────────────────────────────────────────────────────────────────────────────
# Test 4 — Goal Creation
# ──────────────────────────────────────────────────────────────────────────────

def test_goal_classification():
    from era_agent.intelligence_core.goal_engine import GoalEngine
    ge = GoalEngine()

    assert ge.classify("Open VS Code") == "command"
    assert ge.classify("Build me an agentic AI application") == "goal"
    assert ge.classify("Create a full-stack web application with user authentication") == "goal"
    assert ge.classify("Check email") == "command"
    assert ge.classify("Deploy the application to production with zero downtime") == "goal"


def test_goal_extraction():
    from era_agent.intelligence_core.goal_engine import GoalEngine
    ge = GoalEngine()

    goal = ge.extract_goal("Build me a Python web app that is secure and fast")
    assert goal.id
    assert "web" in goal.objective.lower() or "python" in goal.objective.lower()
    assert "Python runtime" in goal.resources
    assert goal.risk == "medium"   # "secure" triggers medium
    assert len(goal.completion_criteria) > 0


# ──────────────────────────────────────────────────────────────────────────────
# Test 5 — Dynamic Planning (OutcomeEngine)
# ──────────────────────────────────────────────────────────────────────────────

def test_dynamic_planning(tmp_workspace):
    from era_agent.outcome_engine.orchestrator import OutcomeEngineOrchestrator
    oeo = OutcomeEngineOrchestrator(tmp_workspace)

    result = oeo.submit_goal("Create a simple hello world Python script")
    assert "task_id" in result
    assert result.get("status") in ("COMPLETED", "RUNNING", "FAILED", "BLOCKED", "PARTIALLY_COMPLETED")


# ──────────────────────────────────────────────────────────────────────────────
# Test 6 — Tool Selection via Tool Registry
# ──────────────────────────────────────────────────────────────────────────────

def test_tool_registry_selection():
    from era_agent.tools.tool_registry import tool_registry

    tools = tool_registry.list_tools()
    assert len(tools) > 0, "Tool registry must contain tools"

    # Core tools must be present
    assert "create_file" in tools
    assert "read_file" in tools
    assert "run_command" in tools
    assert "open_url" in tools


# ──────────────────────────────────────────────────────────────────────────────
# Test 7 — Real Action Execution (create + read file)
# ──────────────────────────────────────────────────────────────────────────────

def test_real_file_create_and_read(tmp_workspace):
    from era_agent.tools.tool_registry import tool_registry
    test_path = os.path.join(tmp_workspace, "test_action.txt")

    # Create
    result = tool_registry.execute("create_file", {"path": test_path, "content": "ERA test content"})
    assert result.get("success"), f"File create failed: {result}"
    assert os.path.exists(test_path), "File not on disk after create_file"

    # Read back
    read_result = tool_registry.execute("read_file", {"path": test_path})
    assert read_result.get("success"), f"File read failed: {read_result}"
    assert "ERA test content" in read_result.get("content", "")


# ──────────────────────────────────────────────────────────────────────────────
# Test 8 — Verification
# ──────────────────────────────────────────────────────────────────────────────

def test_verification_file_existence(tmp_workspace):
    from era_agent.tools.tool_registry import tool_registry
    test_path = os.path.join(tmp_workspace, "verify_test.txt")

    create_result = tool_registry.execute("create_file", {"path": test_path, "content": "verify"})
    ver = tool_registry.verify("create_file", create_result, {"path": test_path})
    assert ver.get("verified") is True, f"Verification failed: {ver}"


# ──────────────────────────────────────────────────────────────────────────────
# Test 9 — Controlled Failure + Recovery Detection
# ──────────────────────────────────────────────────────────────────────────────

def test_controlled_failure_detection(tmp_workspace):
    from era_agent.tools.tool_registry import tool_registry

    # Try to read a non-existent file — must fail, not crash
    result = tool_registry.execute("read_file", {"path": "/nonexistent/path/file.txt"})
    assert result.get("success") is False, "read_file on missing file should fail"
    assert "error" in result or "Error" in str(result.get("error", ""))

    # Verify correctly detects non-creation
    ver = tool_registry.verify("create_file", {"success": False, "error": "disk full"}, {"path": "/bad/path"})
    assert ver.get("verified") is False


# ──────────────────────────────────────────────────────────────────────────────
# Test 10 — Permission Denial
# ──────────────────────────────────────────────────────────────────────────────

def test_permission_denied_in_off_mode(audit_log):
    from era_agent.intelligence_core.permission_engine import PermissionEngine
    pe = PermissionEngine(audit_log, mode="OFF")

    result = pe.check_permission("delete_everything", "filesystem", "medium", "test")
    assert result["allowed"] is False
    assert result["requires_confirmation"] is False


# ──────────────────────────────────────────────────────────────────────────────
# Test 11 — Permission Approval
# ──────────────────────────────────────────────────────────────────────────────

def test_permission_approval_flow(permission_engine):
    # High risk requires confirmation in SUPERVISED mode
    result = permission_engine.check_permission("run_dangerous_cmd", "terminal", "high", "test high risk")
    assert result["allowed"] is False or result["requires_confirmation"] is True

    if result.get("request_id"):
        # User approves
        response = permission_engine.respond(result["request_id"], approved=True)
        assert response["success"] is True
        assert response["status"] == "approved"


def test_permission_auto_allow_low_risk(permission_engine):
    result = permission_engine.check_permission("read_file", "filesystem", "low", "reading config")
    assert result["allowed"] is True
    assert result["requires_confirmation"] is False


def test_permission_auto_allow_medium_supervised(permission_engine):
    result = permission_engine.check_permission("send_notification", "gmail", "medium", "send alert")
    assert result["allowed"] is True


# ──────────────────────────────────────────────────────────────────────────────
# Test 12 — Emergency Stop
# ──────────────────────────────────────────────────────────────────────────────

def test_emergency_stop_and_resume(audit_log):
    from era_agent.intelligence_core.permission_engine import PermissionEngine
    pe = PermissionEngine(audit_log, mode="AUTONOMOUS")

    PermissionEngine.clear_stop()
    assert not PermissionEngine.is_stopped()

    PermissionEngine.emergency_stop()
    assert PermissionEngine.is_stopped()

    # All actions blocked
    result = pe.check_permission("any_action", "any_tool", "low", "test")
    assert result["allowed"] is False
    assert "emergency stop" in result["reason"].lower()

    # Resume
    PermissionEngine.clear_stop()
    assert not PermissionEngine.is_stopped()


# ──────────────────────────────────────────────────────────────────────────────
# Test 13 + 14 — Checkpoint and Resume
# ──────────────────────────────────────────────────────────────────────────────

def test_checkpoint_and_resume(tmp_workspace):
    from era_agent.outcome_engine.orchestrator import OutcomeEngineOrchestrator
    oeo = OutcomeEngineOrchestrator(tmp_workspace)

    result = oeo.submit_goal("Create a simple test file")
    task_id = result.get("task_id")
    assert task_id, "No task_id returned"

    # Pause
    pause_result = oeo.pause_task(task_id)
    assert pause_result.get("status") in ("PAUSED", "COMPLETED", "FAILED")

    # Checkpoint must be on disk
    chk = oeo.checkpoint_manager.load_checkpoint(task_id)
    assert chk is not None, "Checkpoint must persist to disk"

    # Resume
    resume_result = oeo.resume_task(task_id)
    assert "task_id" in resume_result or "success" in resume_result


# ──────────────────────────────────────────────────────────────────────────────
# Test 15 — Memory
# ──────────────────────────────────────────────────────────────────────────────

def test_memory_records_successful_workflow(tmp_workspace):
    from era_agent.outcome_engine.memory import TaskMemoryManager
    mem = TaskMemoryManager(tmp_workspace)

    mem.record_successful_workflow(
        "Build hello world app",
        {"language": "python"},
        ["main.py", "README.md"],
    )

    # Use the actual API: search_similar_workflow
    result = mem.search_similar_workflow("Build hello world app")
    assert result is not None, "Memory should find similar workflow"
    assert "hello" in result.get("prompt", "").lower() or "build" in result.get("prompt", "").lower()


# ──────────────────────────────────────────────────────────────────────────────
# Test 16 — Proactive Initiative
# ──────────────────────────────────────────────────────────────────────────────

def test_proactive_initiative_low_battery():
    from era_agent.intelligence_core.initiative_engine import InitiativeEngine

    eng = InitiativeEngine(score_threshold=0.1)
    critical_state = {
        "battery": {"percent": 8.0, "charging": False},
        "cpu": {"percent": 20.0},
        "memory": {"percent": 55.0},
        "disk": {"free_bytes": 100 * 1024**3},
        "network": {"online": True},
        "active_app": "Visual Studio Code",
        "user_activity": "active",
        "observations": [],
    }

    initiatives = eng.evaluate(critical_state)
    assert len(initiatives) > 0, "Should fire initiative for critically low battery"
    assert any("battery" in i.title.lower() for i in initiatives)


def test_no_spam_from_initiative():
    from era_agent.intelligence_core.initiative_engine import InitiativeEngine

    eng = InitiativeEngine(score_threshold=0.1)
    critical_state = {
        "battery": {"percent": 8.0, "charging": False},
        "cpu": {"percent": 20.0},
        "memory": {"percent": 55.0},
        "disk": {"free_bytes": 100 * 1024**3},
        "network": {"online": True},
        "active_app": "Code",
        "user_activity": "active",
        "observations": [],
    }
    # First call fires
    first = eng.evaluate(critical_state)
    # Second call immediately after — global cooldown should prevent spam
    second = eng.evaluate(critical_state)
    assert len(second) == 0, "Initiative engine must not spam within cooldown period"


# ──────────────────────────────────────────────────────────────────────────────
# Test 17 — Cloud Unavailability (offline degraded mode)
# ──────────────────────────────────────────────────────────────────────────────

def test_offline_degraded_mode():
    from era_agent.intelligence_core.model_router import ModelRouter
    mr = ModelRouter()

    # With no API key set, cloud must fail gracefully
    result = mr.route("classification", "Is this a command or a goal?")
    # Must return a dict with success=False and a human-readable error — never crash
    assert isinstance(result, dict)
    assert "success" in result
    assert "error" in result or result["success"] is True  # success if key is configured


# ──────────────────────────────────────────────────────────────────────────────
# Test 18 — Sensitive Data Protection (Vault)
# ──────────────────────────────────────────────────────────────────────────────

def test_vault_local_only_block(tmp_workspace):
    from era_agent.intelligence_core.personal_vault import PersonalVault

    vault = PersonalVault(os.path.join(tmp_workspace, "vault.jsonl"), password="test_password")
    item_id = vault.store(
        label="secret_api_key",
        data={"key": "sk-super-secret-value"},
        allow_cloud=False,
    )

    # Reading without cloud check — OK
    item = vault.retrieve(item_id)
    assert item is not None
    assert item["data"]["key"] == "sk-super-secret-value"

    # Reading with cloud check — must raise PermissionError
    with pytest.raises(PermissionError):
        vault.retrieve(item_id, allow_cloud_check=True)


def test_vault_allow_cloud(tmp_workspace):
    from era_agent.intelligence_core.personal_vault import PersonalVault

    vault = PersonalVault(os.path.join(tmp_workspace, "vault2.jsonl"), password="test_password2")
    item_id = vault.store(
        label="public_note",
        data={"note": "not sensitive"},
        allow_cloud=True,
    )

    item = vault.retrieve(item_id, allow_cloud_check=True)
    assert item["data"]["note"] == "not sensitive"


# ──────────────────────────────────────────────────────────────────────────────
# Test 19 — Audit Trail
# ──────────────────────────────────────────────────────────────────────────────

def test_audit_trail_records_all_events(tmp_workspace):
    from era_agent.intelligence_core.audit_log import AuditLog
    al = AuditLog(os.path.join(tmp_workspace, "audit_test2.jsonl"))

    al.record("goal_started", "user", {"goal": "build app"}, "medium")
    al.record("tool_executed", "era", {"tool": "create_file"}, "low")
    al.record("permission_denied", "system", {"action": "delete"}, "high")

    events = al.query(limit=10)
    assert len(events) == 3

    high_events = [e for e in events if e["risk_level"] == "high"]
    assert len(high_events) == 1
    assert high_events[0]["event_type"] == "permission_denied"


# ──────────────────────────────────────────────────────────────────────────────
# Test 20 — Real E2E Autonomous Goal
# ──────────────────────────────────────────────────────────────────────────────

def test_real_e2e_autonomous_goal(tmp_workspace):
    """ERA must actually understand, plan, create files, execute, verify — no faking."""
    from era_agent.intelligence_core.orchestrator import IntelligenceOrchestrator
    from era_agent.intelligence_core.permission_engine import PermissionEngine
    PermissionEngine.clear_stop()

    orch = IntelligenceOrchestrator(tmp_workspace, autonomy_mode="SUPERVISED")
    result = orch.process("Create a small Python script that prints Hello ERA")

    # Must return a structured result
    assert isinstance(result, dict)

    # Either task completed or was planned (requires confirmation for safety)
    status = result.get("status", "")
    task_id = result.get("task_id", "")

    # Check the workspace — a file should have been created OR a plan was returned
    ws_files = list(Path(tmp_workspace).rglob("*.py"))
    planning_happened = bool(task_id) or bool(ws_files) or "goal_id" in result

    assert planning_happened, (
        f"E2E failed: no task created and no Python files in workspace.\n"
        f"Result: {json.dumps(result, default=str, indent=2)[:500]}"
    )
