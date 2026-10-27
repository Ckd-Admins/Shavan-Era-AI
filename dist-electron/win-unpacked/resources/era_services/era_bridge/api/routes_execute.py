"""POST /v1/execute and POST /v1/confirm -- the conversational core.

Auto-start is triggered here, and only here: the moment a command is
actually ready to run, ensure_running() is called. Nothing in Bridge
launches Era Local Agent just because Bridge itself started up
(unless AGENT_AUTOSTART_ON_BRIDGE_BOOT is explicitly set) -- it's
purely on-demand, tied to an actual request, as specified.

Authorization enforcement
    Before delegating to Local Agent, every execution checks the locally
    cached authorization lease (written by TelemetryService on each
    heartbeat). Three conditions must ALL hold:
      1. lease["status"] == "ACTIVE"
      2. time.time() < lease["lease_expires_at"]  (offline grace still valid)
      3. A valid, short-lived HMAC token can be generated (signing key present)
    A 401 from ERA Central causes *immediate* lease invalidation, so a
    revoked device stops executing protected commands at the next command
    attempt -- not at the next heartbeat.
    Unprotected diagnostics (GET /status, GET /commands) are not gated here.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from core.agent_client import AgentClient
from api.routes_telemetry import safe_telemetry
from core.auth import verify_api_key, create_command_auth_token
from core.command_catalog import CATALOG
from core.session_engine import resolve_next_step
from core.session_store import SessionStore

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(verify_api_key)])


def _get_telemetry_service():
    """Lazy import avoids circular import at module load time."""
    from bridge_server import telemetry_service
    return telemetry_service


class ExecuteRequest(BaseModel):
    session_id: Optional[str] = None
    command: Optional[str] = None
    params: Optional[Dict[str, str]] = None

    @field_validator("command")
    @classmethod
    def normalize_command(cls, value: Optional[str]) -> Optional[str]:
        return value.strip().lower() if value else value


class ConfirmRequest(BaseModel):
    session_id: str
    confirmed: bool


class ConversationResponse(BaseModel):
    state: str
    session_id: str
    message: str
    command: Optional[str] = None
    param: Optional[str] = None


def get_session_store() -> SessionStore:
    from bridge_server import session_store

    return session_store


def get_agent_client() -> AgentClient:
    from bridge_server import agent_client

    return agent_client


async def _run_on_agent(
    session_id: str, command_name: str, agent_client: AgentClient, session_store: SessionStore
) -> ConversationResponse:
    """Ensures Local Agent is up (auto-starting it if needed), then executes.

    Authorization gate (runs before any agent call):
        Reads the locally cached authorization lease that TelemetryService
        maintains. A device is allowed to execute iff:
          - lease status is ACTIVE
          - the offline grace window has not elapsed (lease_expires_at is in the future)
        A 401 from Central immediately invalidates the lease via TelemetryService,
        so revocation takes effect at the *next command*, not the next heartbeat.
        Telemetry is NOT collected for authorization-rejected events (no command
        name, no timing -- the rejection itself is the signal).
    """
    # -- Authorization lease check ------------------------------------------
    svc = _get_telemetry_service()
    if svc is not None and svc.store is not None:
        lease = svc.store.get_lease()
        lease_status = lease.get("status", "ACTIVE")
        lease_expires_at = lease.get("lease_expires_at", 0.0)
        now = time.time()

        # A lease_expires_at of 0.0 means "never initialized by Central" --
        # allow execution so the device isn't blocked before first heartbeat.
        lease_ever_set = lease_expires_at > 0.0

        if lease_status != "ACTIVE":
            logger.warning(
                "Session %s: authorization rejected — device status is %s.",
                session_id, lease_status,
            )
            session_store.delete(session_id)
            return ConversationResponse(
                state="authorization_rejected",
                session_id=session_id,
                message=(
                    f"This ERA installation has been {lease_status.lower()}. "
                    "Contact your administrator for assistance."
                ),
                command=command_name,
            )

        if lease_ever_set and now >= lease_expires_at:
            logger.warning(
                "Session %s: authorization rejected — offline grace period expired "
                "(lease_expires_at=%.0f, now=%.0f).",
                session_id, lease_expires_at, now,
            )
            session_store.delete(session_id)
            return ConversationResponse(
                state="authorization_rejected",
                session_id=session_id,
                message=(
                    "ERA cannot verify your authorization (offline grace period expired). "
                    "Please reconnect to the internet and try again."
                ),
                command=command_name,
            )

    # -- Build a short-lived signed token for the Local Agent ---------------
    # If telemetry is disabled/not enrolled, device_id falls back to "local".
    if svc is not None and svc.store is not None:
        lease = svc.store.get_lease()
        device_id = svc.store.get("device_id") or "local"
        auth_token = create_command_auth_token(
            device_id=device_id,
            status=lease.get("status", "ACTIVE"),
            lease_expires_at=lease.get("lease_expires_at", 0.0),
        )
    else:
        # Telemetry not configured (local-only mode) -- use a sentinel token
        # so agent_security.py can distinguish from a missing header.
        auth_token = create_command_auth_token(
            device_id="local",
            status="ACTIVE",
            lease_expires_at=0.0,
        )

    # -- Start agent and execute --------------------------------------------
    started = time.perf_counter()
    telemetry = safe_telemetry()  # metadata only: command id, outcome, duration. Never params or messages.
    healthy = await agent_client.ensure_running()
    if not healthy:
        if telemetry:
            telemetry.record_usage("pc_control", command_name, False, None, "AgentUnreachable")
            telemetry.record_error("bridge", "AgentUnreachable", "warning")
        # Keep the session around -- this is a transient infra issue, not a
        # conversational reset. Retrying with the same session_id resumes
        # cleanly without re-asking anything already collected.
        logger.warning("Session %s: Local Agent unreachable/unstartable.", session_id)
        return ConversationResponse(
            state="agent_unreachable",
            session_id=session_id,
            message="Era Local Agent isn't responding and could not be started automatically. "
            "Check that it's installed correctly, or start it manually and try again.",
            command=command_name,
        )

    try:
        result = await agent_client.execute_command(command_name, auth_token=auth_token)
    except Exception as exc:  # noqa: BLE001 - never let a raw agent error bubble as a 500
        logger.exception("Session %s: error calling Local Agent for '%s'", session_id, command_name)
        if telemetry:
            elapsed = int((time.perf_counter() - started) * 1000)
            telemetry.record_usage("pc_control", command_name, False, elapsed, exc)
            telemetry.record_error("bridge", exc, "error")
        session_store.delete(session_id)
        return ConversationResponse(
            state="failure",
            session_id=session_id,
            message=f"Era Local Agent returned an unexpected error: {exc}",
            command=command_name,
        )

    session_store.delete(session_id)
    success = bool(result.get("success"))
    if telemetry:
        telemetry.record_usage("pc_control", command_name, success, int((time.perf_counter() - started) * 1000),
                               None if success else "CommandFailed")
    logger.info("Session %s: executed '%s' on Local Agent -> success=%s", session_id, command_name, success)
    return ConversationResponse(
        state="success" if success else "failure",
        session_id=session_id,
        message=result.get("message", ""),
        command=command_name,
    )


@router.post("/v1/execute", response_model=ConversationResponse)
async def execute(
    request: ExecuteRequest,
    agent_client: AgentClient = Depends(get_agent_client),
    session_store: SessionStore = Depends(get_session_store),
) -> ConversationResponse:
    session_id = request.session_id or session_store.new_session_id()
    session = session_store.get(session_id) or {"command": None, "params": {}, "confirmed": False}

    if request.command and request.command != session.get("command"):
        session = {"command": request.command, "params": {}, "confirmed": False}
    if request.params:
        session.setdefault("params", {}).update(request.params)

    command_name = session.get("command")
    if not command_name:
        session_store.delete(session_id)
        raise HTTPException(status_code=422, detail="A 'command' is required to start a new conversation.")

    step = resolve_next_step(CATALOG, command_name, session.get("params", {}), session.get("confirmed", False))

    if step.kind == "unknown_command":
        session_store.delete(session_id)
        return ConversationResponse(state="error", session_id=session_id, message=step.message, command=command_name)

    if step.kind == "not_enabled":
        session_store.delete(session_id)
        logger.info("Session %s: '%s' requested but not enabled.", session_id, command_name)
        return ConversationResponse(
            state="not_enabled", session_id=session_id, message=step.message, command=command_name
        )

    if step.kind == "needs_input":
        session_store.save(session_id, session)
        return ConversationResponse(
            state="needs_input", session_id=session_id, message=step.message, command=command_name, param=step.param
        )

    if step.kind == "needs_confirmation":
        session_store.save(session_id, session)
        return ConversationResponse(
            state="needs_confirmation", session_id=session_id, message=step.message, command=command_name
        )

    # step.kind == "ready"
    return await _run_on_agent(session_id, command_name, agent_client, session_store)


@router.post("/v1/confirm", response_model=ConversationResponse)
async def confirm(
    request: ConfirmRequest,
    agent_client: AgentClient = Depends(get_agent_client),
    session_store: SessionStore = Depends(get_session_store),
) -> ConversationResponse:
    session = session_store.get(request.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or has expired. Start again with /v1/execute.")

    command_name = session.get("command")

    if not request.confirmed:
        session_store.delete(request.session_id)
        logger.info("Session %s: cancelled at confirmation step.", request.session_id)
        return ConversationResponse(
            state="cancelled",
            session_id=request.session_id,
            message=f"Okay, '{command_name}' was cancelled." if command_name else "Cancelled.",
            command=command_name,
        )

    if not command_name:
        session_store.delete(request.session_id)
        return ConversationResponse(
            state="error", session_id=request.session_id, message="No command was pending confirmation."
        )

    session["confirmed"] = True
    session_store.save(request.session_id, session)
    return await _run_on_agent(request.session_id, command_name, agent_client, session_store)
