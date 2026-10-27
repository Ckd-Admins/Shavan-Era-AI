"""FastAPI server for Era Agent.

Exposes the local command agent over HTTP so external apps (Web applications,
mobile apps, desktop software, or AI assistants like Era) can discover and
trigger system commands with parameters.

Run with:
    python api_server.py
  OR:
    uvicorn api_server:app --reload --port 8000

Then test it with a browser, curl, or Postman -- see README.md for instructions.
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool

try:
    from era_agent.commands import registry
    from era_agent.commands.registry import CommandResult
except ImportError:
    from commands import registry
    from commands.registry import CommandResult



app = FastAPI(
    title="Era Agent API",
    description="Local REST HTTP API allowing external apps to connect to and trigger Era Agent Windows commands.",
    version="1.1.0",
)

# Enable CORS for local development and web app connectivity from any origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ExecuteRequest(BaseModel):
    """Request body for POST /execute, e.g. {"command": "open_app", "params": {"app_name": "notepad"}}."""

    command: str
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Optional command parameters keyed by parameter name.",
        example={},
    )

    @field_validator("command")
    @classmethod
    def command_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("command must not be empty")
        return cleaned


class ExecuteResponse(BaseModel):
    """Response body for POST /execute."""

    success: bool
    message: str


class StatusResponse(BaseModel):
    """Response body for GET /status."""

    status: str
    agent: str
    version: str
    available_commands: int


class CommandsResponse(BaseModel):
    """Response body for GET /commands."""

    commands: Dict[str, Any]


@app.get("/", include_in_schema=False)
def read_root() -> Dict[str, str]:
    """A friendly landing message with helpful navigation links."""
    return {
        "message": "Era Agent REST API is online and ready for connections.",
        "docs": "/docs",
        "status": "/status",
        "commands": "/commands",
    }


@app.get("/status", response_model=StatusResponse)
def get_status() -> StatusResponse:
    """Simple health check to confirm the agent API is running and reachable."""
    return StatusResponse(
        status="online",
        agent="Era Agent for Windows",
        version=app.version,
        available_commands=len(registry.list_commands()),
    )


@app.get("/commands", response_model=CommandsResponse)
def get_commands() -> CommandsResponse:
    """Lists every registered command, description, and parameter specification."""
    return CommandsResponse(
        commands=registry.get_command_specs(),
    )


@app.post("/execute", response_model=ExecuteResponse)
async def execute_command(request: ExecuteRequest) -> ExecuteResponse:
    """Executes a registered command by name with optional parameters.

    Example JSON payload:
    {
        "command": "open_app",
        "params": {
            "app_name": "notepad"
        }
    }
    """
    command_name = request.command.lower()

    try:
        # Command functions run in a threadpool to prevent blocking the event loop.
        result: CommandResult = await run_in_threadpool(
            registry.execute,
            command_name,
            **request.params,
        )
        if not result.success and "Unknown command:" in result.message:
            # Attempt natural language resolution fallback
            nl_result: CommandResult = await run_in_threadpool(
                registry.execute,
                "process_natural_language_control",
                query=request.command,
            )
            if nl_result.success or "Could not interpret system control request:" not in nl_result.message:
                result = nl_result
    except Exception as exc:  # noqa: BLE001 - return clean JSON error response
        raise HTTPException(status_code=500, detail=f"Unexpected server error: {exc}") from exc

    return ExecuteResponse(success=result.success, message=result.message)



if __name__ == "__main__":
    import uvicorn

    print("Starting Era Agent API Server on http://127.0.0.1:8000 ...")
    uvicorn.run("api_server:app", host="127.0.0.1", port=8000, reload=True)

