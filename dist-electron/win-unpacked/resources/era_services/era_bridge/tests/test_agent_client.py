"""Tests for core/agent_client.py -- health checks, auto-start, and no-duplicate-process logic.

Uses httpx.MockTransport so no real network calls are made, and
monkeypatches subprocess.Popen / process-liveness checks so no real
subprocess is ever spawned during tests.
"""

from __future__ import annotations

import core.agent_client as agent_client_module
from config import settings
from core.agent_client import AgentClient

import pytest


def _agent_up_transport() -> "httpx.MockTransport":
    import httpx

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/status"
        return httpx.Response(200, json={"status": "online", "available_commands": 12})

    return httpx.MockTransport(handler)


def _agent_down_transport() -> "httpx.MockTransport":
    import httpx

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_is_running_true_when_agent_responds():
    client = AgentClient(transport=_agent_up_transport())
    assert await client.is_running() is True
    await client.close()


@pytest.mark.asyncio
async def test_is_running_false_when_agent_unreachable():
    client = AgentClient(transport=_agent_down_transport())
    assert await client.is_running() is False
    await client.close()


@pytest.mark.asyncio
async def test_ensure_running_skips_spawn_entirely_when_already_up(monkeypatch):
    client = AgentClient(transport=_agent_up_transport())
    spawn_calls = []
    monkeypatch.setattr(client, "_spawn_if_needed", lambda: spawn_calls.append(1))

    result = await client.ensure_running()

    assert result is True
    assert spawn_calls == []  # never attempted to spawn -- already healthy
    await client.close()


@pytest.mark.asyncio
async def test_ensure_running_spawns_once_then_times_out_if_agent_never_comes_up(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "AGENT_STARTUP_TIMEOUT", 0.3)
    monkeypatch.setattr(settings, "AGENT_HEALTH_POLL_INTERVAL", 0.05)
    monkeypatch.setattr(settings, "AGENT_PID_FILE", tmp_path / "agent.pid")

    client = AgentClient(transport=_agent_down_transport())
    spawn_calls = []
    monkeypatch.setattr(client, "_spawn_if_needed", lambda: spawn_calls.append(1))

    result = await client.ensure_running()

    assert result is False
    assert spawn_calls == [1]  # exactly one spawn attempt, then honest timeout -- no hang
    await client.close()


def test_spawn_skipped_when_agent_project_dir_not_configured(monkeypatch, caplog):
    monkeypatch.setattr(settings, "AGENT_PROJECT_DIR", None)
    client = AgentClient(transport=_agent_down_transport())

    client._spawn_if_needed()  # must log a warning and do nothing, never raise

    assert "AGENT_PROJECT_DIR is not configured" in caplog.text


def test_spawn_skipped_when_pid_file_points_to_a_still_alive_process(monkeypatch, tmp_path):
    """The core no-duplicate-processes guarantee: if Bridge already has a
    record of a live Agent process, it must not launch a second one.
    """
    pid_file = tmp_path / "agent.pid"
    pid_file.write_text("4242")
    monkeypatch.setattr(settings, "AGENT_PID_FILE", pid_file)
    monkeypatch.setattr(settings, "AGENT_PROJECT_DIR", tmp_path)
    monkeypatch.setattr(agent_client_module, "_is_process_alive", lambda pid: pid == 4242)

    popen_calls = []
    monkeypatch.setattr(agent_client_module.subprocess, "Popen", lambda *a, **k: popen_calls.append((a, k)))

    client = AgentClient(transport=_agent_down_transport())
    client._spawn_if_needed()

    assert popen_calls == []


def test_spawn_proceeds_when_pid_file_points_to_a_dead_process(monkeypatch, tmp_path):
    pid_file = tmp_path / "agent.pid"
    pid_file.write_text("9999")
    monkeypatch.setattr(settings, "AGENT_PID_FILE", pid_file)
    monkeypatch.setattr(settings, "AGENT_PROJECT_DIR", tmp_path)
    monkeypatch.setattr(settings, "AGENT_PROCESS_LOG_FILE", tmp_path / "agent_output.log")
    monkeypatch.setattr(agent_client_module, "_is_process_alive", lambda pid: False)  # stale PID

    class _FakeProcess:
        pid = 5555

    popen_calls = []

    def fake_popen(*args, **kwargs):
        popen_calls.append((args, kwargs))
        return _FakeProcess()

    monkeypatch.setattr(agent_client_module.subprocess, "Popen", fake_popen)

    client = AgentClient(transport=_agent_down_transport())
    client._spawn_if_needed()

    assert len(popen_calls) == 1
    assert pid_file.read_text().strip() == "5555"  # new PID recorded
