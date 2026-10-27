"""Telemetry controls (local only, API-key protected): consent, enrollment, transparency."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from api.routes_memory import require_local
from core.auth import verify_api_key
from core.telemetry.service import TelemetryError, TelemetryService

router = APIRouter(prefix="/v1/telemetry", tags=["telemetry"], dependencies=[Depends(verify_api_key), Depends(require_local)])


def get_telemetry() -> TelemetryService:
    from bridge_server import telemetry_service  # local import avoids a circular import at module load

    return telemetry_service


def safe_telemetry() -> "TelemetryService | None":
    """For hot paths: returns the service, or None -- never raises."""
    try:
        return get_telemetry()
    except Exception:  # noqa: BLE001
        return None


class ConsentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool


class EnrollRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id_token: str = Field(min_length=20, max_length=4096)  # Firebase ID token of the signed-in user


@router.get("/status")
async def status(svc: TelemetryService = Depends(get_telemetry)) -> Dict[str, Any]:
    return svc.status()


@router.get("/queue")
async def queue(svc: TelemetryService = Depends(get_telemetry)) -> Dict[str, Any]:
    """Everything that is waiting to be sent, verbatim."""
    return svc.preview()


@router.post("/consent")
async def set_consent(req: ConsentRequest, svc: TelemetryService = Depends(get_telemetry)) -> Dict[str, Any]:
    await svc.set_consent(req.enabled)
    return svc.status()


@router.post("/enroll")
async def enroll(req: EnrollRequest, svc: TelemetryService = Depends(get_telemetry)) -> Dict[str, Any]:
    try:
        await svc.enroll(req.id_token)
    except TelemetryError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from None
    return svc.status()
