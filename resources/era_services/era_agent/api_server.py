"""FastAPI server for Era Agent, Mission Engine & Autonomous Outcome Engine.

Exposes local commands, flagship ERA Mission Engine, and real Gmail/WhatsApp API endpoints.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

# Load .env file before importing adapters so env vars are available at init time
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env", override=False)
except ImportError:
    pass  # python-dotenv not installed — env vars must be set in shell

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool

try:
    from agent_security import require_authorized_execution
except ImportError:
    # Fallback: if agent_security cannot be imported (e.g. during migration),
    # log a warning and use a no-op dependency so existing functionality is
    # preserved. This is a TEMPORARY safety net only.
    import logging as _logging
    _logging.getLogger(__name__).warning(
        "agent_security.py not found — authorization boundary enforcement is DISABLED. "
        "This is unsafe outside development. Ensure agent_security.py is present."
    )
    async def require_authorized_execution(**_):  # type: ignore[misc]
        pass

try:
    from commands import registry
    from commands.registry import CommandResult
    from communication.gmail_adapter import gmail_adapter
    from communication.router import comm_router
    from communication.whatsapp_adapter import whatsapp_adapter
    from mission_engine.engine import era_mission_engine
    from outcome_engine.orchestrator import OutcomeEngineOrchestrator
    from tools.tool_registry import tool_registry
except ImportError:
    from era_agent.commands import registry
    from era_agent.commands.registry import CommandResult
    from era_agent.communication.gmail_adapter import gmail_adapter
    from era_agent.communication.router import comm_router
    from era_agent.communication.whatsapp_adapter import whatsapp_adapter
    from era_agent.mission_engine.engine import era_mission_engine
    from era_agent.outcome_engine.orchestrator import OutcomeEngineOrchestrator
    from era_agent.tools.tool_registry import tool_registry


app = FastAPI(
    title="Era Agent & Mission Engine API",
    description="Local REST HTTP API allowing external apps to trigger system commands, real Gmail/WhatsApp tools, and autonomous ERA missions.",
    version="3.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Outcome Engine Orchestrator
WORKSPACE_DIR = os.getenv("WORKSPACE_DIR", str(Path(__file__).parent / "workspace"))
orchestrator = OutcomeEngineOrchestrator(WORKSPACE_DIR)


class ExecuteRequest(BaseModel):
    command: str
    params: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("command")
    @classmethod
    def command_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("command must not be empty")
        return cleaned


class ExecuteResponse(BaseModel):
    success: bool
    message: str


class MissionCreateRequest(BaseModel):
    goal: str
    context: Dict[str, Any] = Field(default_factory=dict)


class GoalSubmitRequest(BaseModel):
    prompt: str


@app.get("/")
def read_root() -> Dict[str, str]:
    return {
        "message": "Era Agent & Mission Engine REST API online.",
        "docs": "/docs",
        "status": "/status",
        "commands": "/commands",
        "tools": "/tools",
    }


@app.get("/status")
def get_status() -> Dict[str, Any]:
    return {
        "status": "online",
        "agent": "Era Agent with Flagship Mission Engine",
        "version": app.version,
        "available_commands": len(registry.list_commands()),
        "available_tools": len(tool_registry.list_tools()),
        "communication": comm_router.get_status(),
    }


@app.get("/commands")
def get_commands() -> Dict[str, Any]:
    return {"commands": registry.get_command_specs()}


@app.get("/tools")
def get_tools() -> Dict[str, Any]:
    return {"tools": tool_registry.list_tools()}


@app.post("/execute", response_model=ExecuteResponse, dependencies=[Depends(require_authorized_execution)])
async def execute_command(request: ExecuteRequest) -> ExecuteResponse:
    command_name = request.command.lower()
    try:
        # Prioritize system command registry first (robust paths, UWP, zero-beep)
        if registry.get(command_name):
            result: CommandResult = await run_in_threadpool(
                registry.execute,
                command_name,
                **request.params,
            )
            return ExecuteResponse(success=result.success, message=result.message)

        # Then check tool registry
        if tool_registry.get_tool(command_name):
            res = tool_registry.execute(command_name, request.params)
            return ExecuteResponse(
                success=res.get("success", False),
                message=res.get("message") or res.get("error") or str(res),
            )

        # Fallback to command registry
        result: CommandResult = await run_in_threadpool(
            registry.execute,
            command_name,
            **request.params,
        )
        if not result.success and "Unknown command:" in result.message:
            nl_result: CommandResult = await run_in_threadpool(
                registry.execute,
                "process_natural_language_control",
                query=request.command,
            )
            if nl_result.success or "Could not interpret system control request:" not in nl_result.message:
                result = nl_result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected server error: {exc}") from exc

    return ExecuteResponse(success=result.success, message=result.message)


# --------------------------------------------------------------------------
# ERA FLAGSHIP MISSION ENGINE API ENDPOINTS
# --------------------------------------------------------------------------

@app.post("/api/missions", dependencies=[Depends(require_authorized_execution)])
async def create_mission(request: MissionCreateRequest) -> Dict[str, Any]:
    """Creates and starts an ERA Mission."""
    try:
        mission = era_mission_engine.create_mission(request.goal, request.context)
        await run_in_threadpool(era_mission_engine.run, mission)
        return mission.to_dict()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Mission Engine execution error: {exc}") from exc


@app.get("/api/missions/{mission_id}")
def get_mission(mission_id: str) -> Dict[str, Any]:
    """Retrieves status and step breakdown for a mission."""
    mission = era_mission_engine.missions.get(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail=f"Mission '{mission_id}' not found.")
    return mission.to_dict()


@app.post("/api/missions/{mission_id}/approve", dependencies=[Depends(require_authorized_execution)])
async def approve_mission_step(mission_id: str) -> Dict[str, Any]:
    """Approves a pending step waiting for confirmation."""
    return await run_in_threadpool(era_mission_engine.approve_step, mission_id)


@app.post("/api/missions/{mission_id}/cancel")
def cancel_mission(mission_id: str) -> Dict[str, Any]:
    """Cancels a mission in progress."""
    mission = era_mission_engine.missions.get(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail=f"Mission '{mission_id}' not found.")
    mission.state = "CANCELLED"
    return mission.to_dict()


@app.get("/api/missions/{mission_id}/events")
def get_mission_events(mission_id: str) -> Dict[str, Any]:
    """Returns execution trace events for a mission."""
    mission = era_mission_engine.missions.get(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail=f"Mission '{mission_id}' not found.")
    return {
        "mission_id": mission_id,
        "recovery_attempts": mission.recovery_attempts,
        "failures": mission.failures,
        "steps": [s.to_dict() for s in mission.steps],
    }


# --------------------------------------------------------------------------
# REAL COMMUNICATION PROVIDER API & OAUTH ENDPOINTS
# --------------------------------------------------------------------------

@app.get("/api/gmail/status")
def gmail_status() -> Dict[str, Any]:
    """Returns detailed Gmail integration status."""
    return gmail_adapter.get_status()


@app.get("/api/gmail/auth-url")
def gmail_auth_url(redirect_uri: Optional[str] = None) -> Dict[str, Any]:
    """Generates Google OAuth consent URL for user authentication."""
    r_uri = redirect_uri or "http://127.0.0.1:8000/api/gmail/oauth-callback"
    return gmail_adapter.get_auth_url(redirect_uri=r_uri)


@app.get("/api/gmail/oauth-callback")
def gmail_oauth_callback(
    request: Request,
    code: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
    state: Optional[str] = None,
) -> HTMLResponse:
    """Handles OAuth callback from Google consent screen."""
    import logging
    cb_log = logging.getLogger("era.gmail.oauth_callback")

    # Log all query params (names only — no secret values)
    all_params = list(request.query_params.keys())
    cb_log.info("OAuth callback received. Query params present: %s", all_params)

    if error:
        cb_log.error("Google returned error: %s | description: %s", error, error_description)
        return HTMLResponse(content=f"""
            <html><body style="font-family:system-ui;background:#0f172a;color:#f8fafc;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
                <div style="background:#1e293b;padding:2rem;border-radius:12px;border:1px solid #ef4444;text-align:center;max-width:500px;">
                    <h2 style="color:#ef4444;">❌ Gmail OAuth Error</h2>
                    <p><strong>Error:</strong> {error}</p>
                    <p style="color:#94a3b8;">{error_description or ''}</p>
                    <p style="font-size:0.85rem;color:#64748b;">If error is <em>redirect_uri_mismatch</em>, add<br>
                    <code>http://127.0.0.1:8000/api/gmail/oauth-callback</code><br>
                    to Google Cloud Console → OAuth Client → Authorized redirect URIs.</p>
                </div>
            </body></html>
        """)
    if not code:
        cb_log.warning("OAuth callback received without code or error. Params: %s", all_params)
        return HTMLResponse(content="""
            <html><body style="font-family:system-ui;background:#0f172a;color:#f8fafc;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
                <div style="background:#1e293b;padding:2rem;border-radius:12px;border:1px solid #f59e0b;text-align:center;max-width:500px;">
                    <h2 style="color:#f59e0b;">⚠️ Gmail Auth Incomplete</h2>
                    <p>Authorization code not received from Google.</p>
                    <p style="color:#94a3b8;font-size:0.9rem;">Please complete the Google sign-in and allow permissions.</p>
                </div>
            </body></html>
        """)

    res = gmail_adapter.finish_auth(code=code)

    if res.get("success"):
        return HTMLResponse(content=f"""
            <html>
                <body style="font-family: system-ui, sans-serif; background: #0f172a; color: #f8fafc; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0;">
                    <div style="background: #1e293b; padding: 2rem; border-radius: 12px; border: 1px solid #334155; text-align: center; max-width: 450px;">
                        <h2 style="color: #38bdf8;">✅ Gmail Connected to ERA!</h2>
                        <p style="color: #94a3b8;">Account: <strong>{res.get('user_email')}</strong></p>
                        <p style="color: #cbd5e1; font-size: 0.9rem;">You may close this browser tab and return to ERA Autonomy Dashboard.</p>
                    </div>
                </body>
            </html>
        """)
    return HTMLResponse(content=f"<h2>Gmail OAuth Exchange Failed</h2><p>{res.get('error')}</p>")


class GmailSendRequest(BaseModel):
    recipient: str
    subject: str
    body: str
    draft_id: Optional[str] = None


@app.post("/api/gmail/send")
def gmail_send_endpoint(request: GmailSendRequest) -> Dict[str, Any]:
    """Sends an email via connected Gmail account."""
    return gmail_adapter.send_email(
        recipient=request.recipient,
        subject=request.subject,
        body=request.body,
        draft_id=request.draft_id,
    )


@app.post("/api/gmail/disconnect")
def gmail_disconnect() -> Dict[str, Any]:
    """Disconnects Gmail account."""
    return gmail_adapter.disconnect()


@app.get("/api/whatsapp/status")
def whatsapp_status() -> Dict[str, Any]:
    """Returns WhatsApp Business Cloud API integration status."""
    return whatsapp_adapter.get_status()


@app.get("/api/whatsapp/webhook")
def whatsapp_webhook_verification(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
):
    """Meta WhatsApp Webhook Verification Endpoint."""
    verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "era_webhook_token")
    if hub_mode == "subscribe" and hub_verify_token == verify_token:
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Webhook verification token mismatch.")


@app.post("/api/whatsapp/webhook")
async def whatsapp_webhook_event(request: Request) -> Dict[str, Any]:
    """Meta WhatsApp Inbound Message Webhook Endpoint."""
    payload = await request.json()
    return whatsapp_adapter.receive_webhook_event(payload)


# --------------------------------------------------------------------------
# OUTCOME ENGINE V2 COMPATIBILITY ENDPOINTS
# --------------------------------------------------------------------------

@app.post("/v1/outcome/submit", dependencies=[Depends(require_authorized_execution)])
async def submit_goal(request: GoalSubmitRequest) -> Dict[str, Any]:
    """Submits a natural language goal to the Autonomous Outcome Engine."""
    try:
        return await run_in_threadpool(orchestrator.submit_goal, request.prompt)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Outcome Engine execution error: {exc}") from exc


@app.get("/v1/outcome/status/{task_id}")
async def get_task_status(task_id: str) -> Dict[str, Any]:
    """Retrieves live status, dynamic graph, why-trace, and report for a task."""
    res = orchestrator.get_task_status(task_id)
    if not res.get("success"):
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return res


@app.post("/v1/outcome/approve/{task_id}", dependencies=[Depends(require_authorized_execution)])
async def approve_task(task_id: str) -> Dict[str, Any]:
    """Approves a pending task waiting for user confirmation."""
    return await run_in_threadpool(orchestrator.approve_task, task_id)


@app.post("/v1/outcome/pause/{task_id}")
async def pause_task(task_id: str) -> Dict[str, Any]:
    """Pauses task execution."""
    return orchestrator.pause_task(task_id)


@app.post("/v1/outcome/resume/{task_id}")
async def resume_task(task_id: str) -> Dict[str, Any]:
    """Resumes paused task execution."""
    return await run_in_threadpool(orchestrator.resume_task, task_id)


@app.post("/v1/outcome/cancel/{task_id}")
async def cancel_task(task_id: str) -> Dict[str, Any]:
    """Cancels task execution."""
    return orchestrator.cancel_task(task_id)


@app.get("/v1/outcome/list")
def list_tasks() -> Dict[str, Any]:
    """Lists all task checkpoints stored in the engine."""
    return {"tasks": orchestrator.checkpoint_manager.list_checkpoints()}


# --------------------------------------------------------------------------
# ERA INTELLIGENCE CORE v4.0 — API ENDPOINTS
# --------------------------------------------------------------------------
try:
    from era_agent.intelligence_core.orchestrator import get_orchestrator as _get_ic
    _intelligence_core = _get_ic(WORKSPACE_DIR)
    _ic_available = True
except Exception as _ic_err:
    _ic_available = False
    _intelligence_core = None
    import logging as _ic_log_mod
    _ic_log_mod.getLogger("era.intelligence_core").warning("Intelligence Core unavailable: %s", _ic_err)


def _ic() -> Any:
    if not _ic_available or _intelligence_core is None:
        raise HTTPException(status_code=503, detail="Intelligence Core not available")
    return _intelligence_core


class IntelligenceProcessRequest(BaseModel):
    input: str
    context_hint: Optional[Dict[str, Any]] = None


class PermissionRespondRequest(BaseModel):
    request_id: str
    approved: bool


class ModeChangeRequest(BaseModel):
    mode: str


class VaultStoreRequest(BaseModel):
    label: str
    data: Any
    category: str = "general"
    allow_cloud: bool = False


@app.get("/intelligence/status")
def intelligence_status() -> Dict[str, Any]:
    """ERA Intelligence Core status."""
    return _ic().get_status()


@app.get("/intelligence/computer")
def get_computer_state() -> Dict[str, Any]:
    """Real-time hardware telemetry: battery, CPU, RAM, disk, network, BT."""
    return _ic().get_computer_state()


@app.get("/intelligence/context")
def get_context() -> Dict[str, Any]:
    """Semantic context built from current computer state."""
    return _ic().get_context()


@app.post("/intelligence/process")
async def process_intelligence_input(request: IntelligenceProcessRequest) -> Dict[str, Any]:
    """Main ERA intelligence entry-point — process any user input (command or goal)."""
    return await run_in_threadpool(_ic().process, request.input, request.context_hint)


@app.get("/intelligence/goals")
def list_intelligence_goals() -> Dict[str, Any]:
    """List all active intelligence-core goals with live task status."""
    return {"goals": _ic().get_active_goals()}


@app.get("/intelligence/insights")
def get_insights() -> Dict[str, Any]:
    """Proactive initiative engine — returns current suggestions."""
    return {"insights": _ic().get_insights()}


@app.get("/intelligence/events")
def get_audit_events(minutes: int = 60) -> Dict[str, Any]:
    """Audit log events from the last N minutes."""
    return {"events": _ic().audit_log.get_recent(minutes=minutes)}


@app.get("/intelligence/permissions/pending")
def list_pending_permissions() -> Dict[str, Any]:
    """All pending permission requests awaiting user response."""
    return {"pending": _ic().permission_engine.list_pending()}


@app.post("/intelligence/permissions/respond")
def respond_to_permission(request: PermissionRespondRequest) -> Dict[str, Any]:
    """Approve or deny a pending permission request."""
    return _ic().permission_engine.respond(request.request_id, request.approved)


@app.post("/intelligence/stop")
def emergency_stop() -> Dict[str, Any]:
    """EMERGENCY STOP — immediately halts all autonomous ERA execution."""
    return _ic().emergency_stop()


@app.post("/intelligence/resume")
def resume_era() -> Dict[str, Any]:
    """Resume ERA after emergency stop."""
    return _ic().resume()


@app.post("/intelligence/mode")
def set_mode(request: ModeChangeRequest) -> Dict[str, Any]:
    """Change ERA autonomy mode: OFF | ASSIST | SUPERVISED | AUTONOMOUS."""
    return _ic().set_mode(request.mode)


@app.post("/intelligence/vault/store")
def vault_store(request: VaultStoreRequest) -> Dict[str, Any]:
    """Store sensitive data in the local encrypted personal vault."""
    item_id = _ic().vault.store(
        label=request.label,
        data=request.data,
        category=request.category,
        allow_cloud=request.allow_cloud,
    )
    return {"success": True, "item_id": item_id}


@app.get("/intelligence/vault/list")
def vault_list(category: Optional[str] = None) -> Dict[str, Any]:
    """List vault items (metadata only — no decrypted content exposed)."""
    return {"items": _ic().vault.list_items(category=category)}


@app.delete("/intelligence/vault/{item_id}")
def vault_delete(item_id: str) -> Dict[str, Any]:
    """Delete a vault item by id."""
    deleted = _ic().vault.delete(item_id)
    return {"success": deleted, "item_id": item_id}


if __name__ == "__main__":
    import uvicorn
    print("Starting Era Agent & Mission Engine API Server on http://127.0.0.1:8000 ...")
    uvicorn.run("api_server:app", host="127.0.0.1", port=8000, reload=True)

