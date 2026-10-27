"""Integration tests for Era Bridge's FastAPI routes.

Swaps in a temporary SQLite session store and a fake AgentClient (no
real network, no real subprocess) for each test.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi.testclient import TestClient

import bridge_server
from config import settings
from core.session_store import SessionStore

API_KEY_HEADER = {"X-Era-Bridge-Key": settings.BRIDGE_API_KEY}


class FakeAgentClient:
    """Stands in for AgentClient -- no network, no subprocess, fully scripted."""

    def __init__(self, healthy: bool = True, command_result: Optional[Dict[str, Any]] = None):
        self.healthy = healthy
        self.command_result = command_result or {"success": True, "message": "done"}
        self.ensure_running_calls = 0
        self.execute_calls = []

    async def ensure_running(self) -> bool:
        self.ensure_running_calls += 1
        return self.healthy

    async def execute_command(self, command: str, auth_token=None) -> Dict[str, Any]:
        self.execute_calls.append(command)
        return self.command_result

    async def is_running(self) -> bool:
        return self.healthy

    async def get_status_body(self) -> Optional[Dict[str, Any]]:
        return {"status": "online"} if self.healthy else None


def _client(tmp_path, healthy=True, command_result=None) -> TestClient:
    bridge_server.session_store = SessionStore(db_path=tmp_path / "test_sessions.db")
    bridge_server.agent_client = FakeAgentClient(healthy=healthy, command_result=command_result)
    return TestClient(bridge_server.app, base_url="http://127.0.0.1:8100", client=("127.0.0.1", 50000))


def test_health_is_public_and_minimal(tmp_path):
    client = _client(tmp_path)
    response = client.get("/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_status_requires_auth(tmp_path):
    client = _client(tmp_path)
    assert client.get("/v1/status").status_code == 401
    response = client.get("/v1/status", headers=API_KEY_HEADER)
    assert response.status_code == 200
    assert response.json()["agent_reachable"] is True


def test_commands_requires_auth(tmp_path):
    client = _client(tmp_path)
    response = client.get("/v1/commands")
    assert response.status_code == 401


def test_commands_with_valid_key_lists_five_enabled(tmp_path):
    client = _client(tmp_path)
    response = client.get("/v1/commands", headers=API_KEY_HEADER)
    assert response.status_code == 200
    commands = response.json()["commands"]
    enabled = [name for name, info in commands.items() if info["enabled"]]
    core_expected = ["open_calculator", "open_camera", "open_chrome", "open_file_explorer", "open_notepad"]
    for cmd in core_expected:
        assert cmd in enabled, f"Expected core command '{cmd}' to be enabled in catalog"
    assert len(enabled) >= 5


def test_execute_enabled_command_runs_end_to_end(tmp_path):
    client = _client(tmp_path, command_result={"success": True, "message": "Notepad opened successfully."})
    response = client.post("/v1/execute", json={"command": "open_notepad"}, headers=API_KEY_HEADER)
    body = response.json()
    assert body["state"] == "success"
    assert body["message"] == "Notepad opened successfully."


def test_execute_not_enabled_command_returns_clear_state(tmp_path):
    client = _client(tmp_path)
    response = client.post("/v1/execute", json={"command": "search_file"}, headers=API_KEY_HEADER)
    body = response.json()
    assert body["state"] == "not_enabled"
    assert "search_file" in body["message"]


def test_execute_unknown_command_returns_error(tmp_path):
    client = _client(tmp_path)
    response = client.post("/v1/execute", json={"command": "not_real"}, headers=API_KEY_HEADER)
    assert response.json()["state"] == "error"


def test_execute_without_api_key_is_rejected(tmp_path):
    client = _client(tmp_path)
    response = client.post("/v1/execute", json={"command": "open_notepad"})
    assert response.status_code == 401


def test_execute_triggers_auto_start_and_reports_unreachable_when_agent_wont_start(tmp_path):
    client = _client(tmp_path, healthy=False)
    response = client.post("/v1/execute", json={"command": "open_notepad"}, headers=API_KEY_HEADER)
    body = response.json()
    assert body["state"] == "agent_unreachable"
    assert bridge_server.agent_client.ensure_running_calls == 1


def test_missing_command_on_new_session_returns_422(tmp_path):
    client = _client(tmp_path)
    response = client.post("/v1/execute", json={}, headers=API_KEY_HEADER)
    assert response.status_code == 422


def test_confirm_with_unknown_session_returns_404(tmp_path):
    client = _client(tmp_path)
    response = client.post("/v1/confirm", json={"session_id": "nope", "confirmed": True}, headers=API_KEY_HEADER)
    assert response.status_code == 404
