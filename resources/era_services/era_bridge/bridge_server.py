"""Era Bridge -- FastAPI app.

Sits between Era (Gemini) and Era Local Agent. Era should only ever
talk to Bridge's /v1/* endpoints; Bridge is the only thing that talks
to Local Agent directly, and only through Local Agent's own existing,
unmodified HTTP API.

Run with:
    uvicorn bridge_server:app --host 127.0.0.1 --port 8100

Or via the Task Scheduler entry created by startup/install_task.py,
which launches run_bridge.pyw (windowless, no VS Code needed).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from config import settings
from core.agent_client import AgentClient
from core.telemetry.service import TelemetryService
from core.logging_config import setup_logging
from core.session_store import SessionStore
from era_memory import MemoryConfig, MemoryManager

setup_logging()
logger = logging.getLogger(__name__)

logger.info("Bridge API key source: %s (the key itself is never logged).", settings.BRIDGE_API_KEY_SOURCE)

# Module-level singletons, looked up lazily by the route modules
# (see api/routes_execute.py, api/routes_meta.py) to avoid a circular
# import between this file and the routers it mounts.
agent_client = AgentClient()
session_store = SessionStore()
from core.vision_client import VisionAgentClient
vision_client = VisionAgentClient()
# Persistent memory. Touches no files until first use (lazy), and every
# automatic memory path degrades safely -- it can never block a command.
memory_manager = MemoryManager(MemoryConfig.from_settings(settings))
# Opt-in telemetry (OFF until the user enables it and enrolls). Metadata only.
telemetry_service = TelemetryService(
    settings.TELEMETRY_DIR,
    settings.TELEMETRY_CENTRAL_URL,
    settings.BRIDGE_VERSION,
    heartbeat_seconds=settings.TELEMETRY_HEARTBEAT_SECONDS,
    flush_seconds=settings.TELEMETRY_FLUSH_SECONDS,
    batch_size=settings.TELEMETRY_BATCH_SIZE,
    outbox_max=settings.TELEMETRY_OUTBOX_MAX,
    reachability=agent_client.is_running,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.AGENT_AUTOSTART_ON_BRIDGE_BOOT:
        logger.info("AGENT_AUTOSTART_ON_BRIDGE_BOOT is enabled -- warming up Era Local Agent now.")
        await agent_client.ensure_running()
    else:
        reachable = await agent_client.is_running()
        logger.info("Startup check: Era Local Agent reachable=%s (auto-start happens on first request).", reachable)
    telemetry_service.start()  # idle unless the user opted in and enrolled
    yield
    await telemetry_service.close()
    await agent_client.close()
    await vision_client.close()


app = FastAPI(
    title="Era Bridge",
    description="Session-based bridge between Era and Era Local Agent, with automatic Agent startup.",
    version=settings.BRIDGE_VERSION,
    lifespan=lifespan,
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.BRIDGE_ALLOWED_HOSTS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BRIDGE_ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-Era-Bridge-Key"],
)

from api.routes_execute import router as execute_router  # noqa: E402
from api.routes_memory import router as memory_router  # noqa: E402
from api.routes_meta import router as meta_router  # noqa: E402
from api.routes_telemetry import router as telemetry_router  # noqa: E402

app.include_router(meta_router)
app.include_router(execute_router)
app.include_router(memory_router)
app.include_router(telemetry_router)


@app.get("/", include_in_schema=False)
def read_root() -> dict:
    return {"message": "Era Bridge is running.", "health": "/v1/health", "docs": "/docs"}
