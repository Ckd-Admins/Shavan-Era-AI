"""GET /v1/health (public), GET /v1/status and GET /v1/commands (authenticated)."""

from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from config import settings
from core.agent_client import AgentClient
from core.auth import verify_api_key
from core.command_catalog import CATALOG

router = APIRouter()


class HealthResponse(BaseModel):
    status: str


class StatusResponse(BaseModel):
    status: str
    bridge_version: str
    agent_reachable: bool
    agent_status: dict | None = None


class ParamInfo(BaseModel):
    name: str
    prompt: str
    required: bool


class CommandInfo(BaseModel):
    description: str
    enabled: bool
    command_class: str  # "direct" | "pending_agent_extension"
    params: List[ParamInfo]
    requires_confirmation: bool


class CommandsResponse(BaseModel):
    commands: Dict[str, CommandInfo]


def get_agent_client() -> AgentClient:
    from bridge_server import agent_client  # local import avoids a circular import at module load

    return agent_client


@router.get("/v1/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """Unauthenticated liveness probe. Reveals nothing but "Bridge is up"."""
    return HealthResponse(status="ok")


@router.get("/v1/status", response_model=StatusResponse, dependencies=[Depends(verify_api_key)])
async def get_status(client: AgentClient = Depends(get_agent_client)) -> StatusResponse:
    """Authenticated: Bridge status plus a live check of Local Agent."""
    agent_status = await client.get_status_body()
    return StatusResponse(
        status="online",
        bridge_version=settings.BRIDGE_VERSION,
        agent_reachable=agent_status is not None,
        agent_status=agent_status,
    )


@router.get("/v1/commands", response_model=CommandsResponse, dependencies=[Depends(verify_api_key)])
async def get_commands() -> CommandsResponse:
    return CommandsResponse(
        commands={
            name: CommandInfo(
                description=spec.description,
                enabled=spec.enabled,
                command_class="direct" if spec.enabled else "pending_agent_extension",
                params=[ParamInfo(name=p.name, prompt=p.prompt, required=p.required) for p in spec.params],
                requires_confirmation=spec.requires_confirmation,
            )
            for name, spec in CATALOG.items()
        }
    )


def get_vision_client():
    from bridge_server import vision_client
    return vision_client


@router.get("/v1/vision/status", dependencies=[Depends(verify_api_key)])
async def get_vision_status(vision = Depends(get_vision_client)):
    status = await vision.get_vision_status()
    return status or {"error": "Vision Agent unreachable", "reachable": False}


@router.get("/v1/vision/screen", dependencies=[Depends(verify_api_key)])
async def get_current_screen(vision = Depends(get_vision_client)):
    result = await vision.get_current_screen_state()
    return result or {"current_state": None, "error": "Vision Agent unreachable"}


@router.get("/v1/vision/chart/latest", dependencies=[Depends(verify_api_key)])
async def get_latest_chart_via_bridge(vision = Depends(get_vision_client)):
    result = await vision.get_latest_chart()
    return result or {"chart": None, "error": "Vision Agent unreachable"}
