"""Aera Bridge: receives commands from Aera Voice Assistant and forwards them to Era Agent.

This lightweight FastAPI service accepts the same payload as Era Agent's /execute
endpoint and forwards it to the local Era Agent API (http://127.0.0.1:8000/execute).
If the Era Agent API is unavailable, it falls back to calling the local registry
directly so the bridge still works when run on the same machine.

Run locally for testing:
    python aera_bridge.py

Then emulate the voice assistant with a POST to http://127.0.0.1:9000/forward
with JSON: {"command": "open_app", "params": {"app_name": "notepad"}}
"""

from __future__ import annotations

import json
import socket
from typing import Any, Dict

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.responses import JSONResponse


class ForwardRequest(BaseModel):
    command: str
    params: Dict[str, Any] = {}


app = FastAPI(title="Aera Bridge", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


ERA_AGENT_API = "http://127.0.0.1:8000/execute"


def _era_api_available() -> bool:
    try:
        # quick connectivity check
        resp = requests.get("http://127.0.0.1:8000/status", timeout=1.0)
        return resp.status_code == 200
    except Exception:
        return False


@app.post("/forward")
def forward_command(req: ForwardRequest):
    payload = {"command": req.command, "params": req.params}

    # Try to forward to running Era Agent HTTP API first
    if _era_api_available():
        try:
            r = requests.post(ERA_AGENT_API, json=payload, timeout=5.0)
            r.raise_for_status()
            return JSONResponse(status_code=200, content=r.json())
        except Exception as exc:
            # fall through to local fallback
            pass

    # Fallback: import local registry and execute directly
    try:
        from commands import registry

        result = registry.execute(req.command, **req.params)
        return {"success": result.success, "message": result.message}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Bridge execution failed: {exc}") from exc


if __name__ == "__main__":
    import uvicorn

    host = "127.0.0.1"
    port = 9000
    print(f"Starting Aera Bridge on http://{host}:{port} (forwards to {ERA_AGENT_API})")
    uvicorn.run("aera_bridge:app", host=host, port=port, reload=False)
