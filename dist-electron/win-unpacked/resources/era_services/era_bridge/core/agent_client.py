"""HTTP client for Era Local Agent, with automatic, safe startup.

This is the only part of Era Bridge that ever touches Era Local
Agent, and it only ever does so through Local Agent's existing,
unmodified HTTP endpoints (GET /status, POST /execute) or by
launching Local Agent's own, existing start command as a subprocess.
Nothing here imports, edits, or depends on Local Agent's source code.

Startup safety:
    1. A live GET /status check is always tried first -- if Local
       Agent is already up, nothing is spawned.
    2. An asyncio.Lock serializes concurrent "ensure running" calls,
       so two nearly-simultaneous requests can't both decide to spawn
       a second process.
    3. A PID file records a process Bridge itself spawned. Before
       spawning, Bridge checks whether that PID is still alive (via
       `tasklist` on Windows) -- if so, it waits for that one instead
       of starting another.
    4. After spawning, Bridge polls GET /status until it responds or
       a startup timeout is reached -- callers never hang forever.
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)


def _is_windows() -> bool:
    return platform.system().lower() == "windows"


def _is_process_alive(pid: int) -> bool:
    """Checks whether a PID is still a live process. Windows-only; this
    project targets Windows, matching Era Local Agent's own scope.
    """
    if not _is_windows():
        return False
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return str(pid) in result.stdout
    except (OSError, subprocess.SubprocessError):
        return False


class AgentUnreachableError(Exception):
    """Raised when Local Agent could not be reached or started in time."""


class AgentClient:
    def __init__(self, transport: Optional[httpx.BaseTransport] = None) -> None:
        # `transport` lets tests inject a mock transport (see tests/test_agent_client.py)
        # without ever making a real network call. Production code never passes it.
        self._client = httpx.AsyncClient(
            base_url=str(settings.AGENT_BASE_URL),
            transport=transport,
            headers={"X-Era-Agent-Key": settings.AGENT_API_KEY},
        )
        self._start_lock = asyncio.Lock()

    async def close(self) -> None:
        await self._client.aclose()

    # -- Health -----------------------------------------------------------

    async def is_running(self) -> bool:
        """A quick, cheap check -- does NOT attempt to start anything."""
        try:
            response = await self._client.get("/status", timeout=settings.AGENT_STATUS_CHECK_TIMEOUT)
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def get_status_body(self) -> Optional[Dict[str, Any]]:
        try:
            response = await self._client.get("/status", timeout=settings.AGENT_STATUS_CHECK_TIMEOUT)
            if response.status_code == 200:
                return response.json()
        except (httpx.HTTPError, ValueError):
            pass
        return None

    # -- Auto-start ---------------------------------------------------------

    async def ensure_running(self) -> bool:
        """Makes sure Local Agent is up, starting it if needed. Returns
        True once healthy, False if it couldn't be reached/started within
        the configured timeout. Safe to call concurrently.
        """
        if await self.is_running():
            return True

        async with self._start_lock:
            # Re-check: another request may have already brought it up
            # while we were waiting for the lock.
            if await self.is_running():
                return True

            self._spawn_if_needed()

            deadline = time.monotonic() + settings.AGENT_STARTUP_TIMEOUT
            while time.monotonic() < deadline:
                if await self.is_running():
                    logger.info("Era Local Agent became healthy.")
                    return True
                await asyncio.sleep(settings.AGENT_HEALTH_POLL_INTERVAL)

            logger.error(
                "Era Local Agent did not become healthy within %.1fs.",
                settings.AGENT_STARTUP_TIMEOUT,
            )
            return False

    def _spawn_if_needed(self) -> None:
        if settings.AGENT_PROJECT_DIR is None:
            logger.warning(
                "AGENT_PROJECT_DIR is not configured -- cannot auto-start Era Local Agent. "
                "Set it via environment variable to enable auto-start."
            )
            return

        existing_pid = self._read_pid_file()
        if existing_pid is not None and _is_process_alive(existing_pid):
            logger.info(
                "Era Local Agent process (PID %s) already appears to be starting up; "
                "waiting for it instead of launching another.",
                existing_pid,
            )
            return

        logger.info(
            "Era Local Agent not detected. Launching it now from %s ...", settings.AGENT_PROJECT_DIR
        )
        settings.AGENT_PROCESS_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(settings.AGENT_PROCESS_LOG_FILE, "ab") as log_file:
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if _is_windows() else 0
                process = subprocess.Popen(
                    shlex.split(settings.AGENT_START_COMMAND),
                    cwd=str(settings.AGENT_PROJECT_DIR),
                    stdout=log_file,
                    stderr=log_file,
                    creationflags=creationflags,
                    env={**os.environ, "ERA_AGENT_API_KEY": settings.AGENT_API_KEY},
                )
            self._write_pid_file(process.pid)
            logger.info("Era Local Agent launched (PID %s). Waiting for it to become healthy...", process.pid)
        except (OSError, ValueError) as exc:
            logger.error("Failed to launch Era Local Agent: %s", exc)

    def _read_pid_file(self) -> Optional[int]:
        try:
            return int(settings.AGENT_PID_FILE.read_text().strip())
        except (OSError, ValueError):
            return None

    def _write_pid_file(self, pid: int) -> None:
        try:
            settings.AGENT_PID_FILE.write_text(str(pid))
        except OSError as exc:
            logger.warning("Could not write agent PID file: %s", exc)

    # -- Command execution (Class 1 only, per Phase 1+2 scope) -------------

    async def execute_command(self, command: str, auth_token: Optional[str] = None) -> Dict[str, Any]:
        """Calls Local Agent's POST /execute (authenticated with the Agent key).

        Only ever sends {"command": ...} -- no params field, because
        Local Agent's current /execute contract has nowhere to put one.

        ``auth_token`` is the short-lived, HMAC-signed lease token generated
        by routes_execute._run_on_agent. It is forwarded as ``X-Era-Auth-Token``
        so that Local Agent's agent_security layer can verify it independently.
        When not provided (e.g. in unit tests that mock execute_command directly),
        the header is omitted and Local Agent falls back to its legacy behaviour.
        """
        extra_headers: Dict[str, str] = {}
        if auth_token:
            extra_headers["X-Era-Auth-Token"] = auth_token
        response = await self._client.post(
            "/execute",
            json={"command": command},
            headers=extra_headers,
            timeout=settings.AGENT_EXECUTE_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
