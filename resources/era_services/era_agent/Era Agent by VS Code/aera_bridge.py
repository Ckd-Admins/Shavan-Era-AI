"""Aera Bridge (copied)"""

from __future__ import annotations

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.responses import JSONResponse

try:
    from commands import registry
except Exception:
    from era_agent.commands import registry


class ForwardRequest(BaseModel):
    command: str
    params: dict = {}


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
        resp = requests.get("http://127.0.0.1:8000/status", timeout=1.0)
        return resp.status_code == 200
    except Exception:
        return False


@app.post("/forward")
def forward_command(req: ForwardRequest):
    payload = {"command": req.command, "params": req.params}
    if _era_api_available():
        try:
            r = requests.post(ERA_AGENT_API, json=payload, timeout=5.0)
            r.raise_for_status()
            return JSONResponse(status_code=200, content=r.json())
        except Exception:
            pass
    try:
        result = registry.execute(req.command, **req.params)
        return {"success": result.success, "message": result.message}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Bridge execution failed: {exc}") from exc


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("aera_bridge:app", host="127.0.0.1", port=9000, reload=False)
