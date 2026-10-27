"""FastAPI server for Era Agent (copied).
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool

try:
    from commands import registry
    from commands.registry import CommandResult
except ImportError:
    from era_agent.commands import registry
    from era_agent.commands.registry import CommandResult


app = FastAPI(
    title="Era Agent API",
    description="Local REST HTTP API allowing external apps to connect to and trigger Era Agent Windows commands.",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.get("/status")
def get_status() -> Dict[str, Any]:
    return {"status": "online", "available_commands": len(registry.list_commands())}


@app.post("/execute")
async def execute_command(request: ExecuteRequest) -> ExecuteResponse:
    command_name = request.command.lower()
    try:
        result: CommandResult = await run_in_threadpool(registry.execute, command_name, **request.params)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected server error: {exc}") from exc
    return ExecuteResponse(success=result.success, message=result.message)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_server:app", host="127.0.0.1", port=8000, reload=True)
