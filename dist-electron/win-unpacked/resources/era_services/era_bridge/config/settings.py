"""Era Bridge configuration -- entirely environment-driven.

Nothing here hardcodes a path to your Era Local Agent installation,
because that path is specific to your machine and wasn't part of the
uploaded project. Set AGENT_PROJECT_DIR (and AGENT_START_COMMAND, if
your setup differs from the default) via environment variables, or a
.env file loaded before this module is imported.

Every setting has a safe default so Bridge still starts without any
configuration -- auto-start of the Agent is simply skipped (with a
logged warning) until AGENT_PROJECT_DIR is set.
"""

from __future__ import annotations

import os
from pathlib import Path

from config.secrets_store import era_home, load_or_create_key

# --- Bridge's own network settings ---------------------------------------
BRIDGE_HOST: str = os.environ.get("BRIDGE_HOST", "127.0.0.1")
BRIDGE_PORT: int = int(os.environ.get("BRIDGE_PORT", "8100"))

# --- Security -----------------------------------------------------------------
BRIDGE_VERSION: str = "1.0.0"

# Bridge's own API key: BRIDGE_API_KEY env var, else a stable owner-only file
# (<ERA_HOME>/bridge_api.key, created on first run). The key itself is NEVER
# logged -- only where it lives.
BRIDGE_API_KEY: str = load_or_create_key("BRIDGE_API_KEY", "bridge_api.key")
BRIDGE_API_KEY_SOURCE: str = (
    "environment variable BRIDGE_API_KEY" if os.environ.get("BRIDGE_API_KEY") else str(era_home() / "bridge_api.key")
)

# Shared secret Bridge sends to Era Local Agent (header X-Era-Agent-Key).
AGENT_API_KEY: str = load_or_create_key("ERA_AGENT_API_KEY", "agent_api.key")

# Browser origins allowed to call Bridge (CORS). Defaults to local dev servers
# only; set BRIDGE_ALLOWED_ORIGINS="https://your-app.example,http://localhost:5173".
BRIDGE_ALLOWED_ORIGINS: list[str] = [
    o.strip()
    for o in os.environ.get(
        "BRIDGE_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if o.strip()
]
# Host headers Bridge answers to (blocks DNS-rebinding). Loopback names only.
BRIDGE_ALLOWED_HOSTS: list[str] = [
    h.strip() for h in os.environ.get("BRIDGE_ALLOWED_HOSTS", "127.0.0.1,localhost,[::1]").split(",") if h.strip()
]
# Multi-turn conversations idle longer than this are discarded.
SESSION_TTL_SECONDS: int = int(os.environ.get("SESSION_TTL_SECONDS", "900"))

# --- Era Local Agent connection ---------------------------------------------
AGENT_BASE_URL: str = os.environ.get("AGENT_BASE_URL", "http://127.0.0.1:8000")

# Path to your era_agent project folder (the one containing api_server.py).
# Required only for auto-start; leave unset to disable auto-start entirely.
_agent_dir_env = os.environ.get("AGENT_PROJECT_DIR")
AGENT_PROJECT_DIR: Path | None = Path(_agent_dir_env) if _agent_dir_env else None

# The command Bridge runs (with AGENT_PROJECT_DIR as its working directory)
# to bring the Agent up. Override this if you use a virtualenv's python,
# a different port, etc.
AGENT_START_COMMAND: str = os.environ.get(
    "AGENT_START_COMMAND", "python -m uvicorn api_server:app --host 127.0.0.1 --port 8000"
)

# --- Health check / auto-start tuning ---------------------------------------
AGENT_STATUS_CHECK_TIMEOUT: float = float(os.environ.get("AGENT_STATUS_CHECK_TIMEOUT", "1.5"))
AGENT_EXECUTE_TIMEOUT: float = float(os.environ.get("AGENT_EXECUTE_TIMEOUT", "10.0"))
AGENT_STARTUP_TIMEOUT: float = float(os.environ.get("AGENT_STARTUP_TIMEOUT", "20.0"))
AGENT_HEALTH_POLL_INTERVAL: float = float(os.environ.get("AGENT_HEALTH_POLL_INTERVAL", "0.5"))

# If true, Bridge also tries to warm up the Agent once at Bridge's own
# startup (in addition to the on-demand check before every request).
# Off by default -- auto-start remains purely on-demand, as requested.
AGENT_AUTOSTART_ON_BRIDGE_BOOT: bool = os.environ.get("AGENT_AUTOSTART_ON_BRIDGE_BOOT", "false").lower() == "true"

# --- Paths -------------------------------------------------------------------
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
AGENT_PID_FILE: Path = PROJECT_ROOT / "agent.pid"
AGENT_PROCESS_LOG_FILE: Path = PROJECT_ROOT / "logs" / "agent_process_output.log"

# --- ERA Vision Agent connection ---------------------------------------------
VISION_AGENT_URL: str = os.environ.get("VISION_AGENT_URL", "http://127.0.0.1:8200")
VISION_AGENT_API_KEY: str = os.environ.get("VISION_AGENT_API_KEY", "era_vision_secret_key_2026")

# --- Persistent memory (era_memory) -------------------------------------------
# Everything is local by default: a SQLite file on this machine, no network
# calls, no extra API keys. See README.md ("Persistent memory").
MEMORY_DB_PATH: Path = Path(os.environ.get("ERA_MEMORY_DB_PATH") or (PROJECT_ROOT / "data" / "memory.db"))
# Master switch. False = automatic retrieval/extraction is off and cannot be
# turned on at runtime (explicit save/list/delete endpoints still work).
MEMORY_ENABLED: bool = os.environ.get("MEMORY_ENABLED", "true").lower() == "true"
# Default for the runtime "automatic memory" toggle (POST /v1/memory/settings
# overrides it and the choice is persisted in the memory database).
MEMORY_AUTO_DEFAULT: bool = os.environ.get("MEMORY_AUTO_DEFAULT", "true").lower() == "true"
MEMORY_MAX_CONTEXT_CHARS: int = int(os.environ.get("MEMORY_MAX_CONTEXT_CHARS", "2000"))
MEMORY_MAX_RETRIEVED: int = int(os.environ.get("MEMORY_MAX_RETRIEVED", "8"))
# Keep short-lived data (working memory, raw conversation turns) this long.
MEMORY_RETENTION_DAYS: int = int(os.environ.get("MEMORY_RETENTION_DAYS", "14"))
MEMORY_STORE_TURNS: bool = os.environ.get("MEMORY_STORE_TURNS", "true").lower() == "true"
# Only accept memory-management requests that originate from this machine.
MEMORY_LOCAL_ONLY: bool = os.environ.get("MEMORY_LOCAL_ONLY", "true").lower() == "true"

# --- Telemetry (opt-in, metadata only; see README "Telemetry & privacy") -----------
# Nothing is ever sent unless the user enables it AND enrolls this installation.
TELEMETRY_CENTRAL_URL: str = os.environ.get("ERA_CENTRAL_URL", "").rstrip("/")
TELEMETRY_DIR: Path = Path(os.environ.get("ERA_TELEMETRY_DIR") or (era_home() / "telemetry"))
TELEMETRY_HEARTBEAT_SECONDS: int = int(os.environ.get("ERA_TELEMETRY_HEARTBEAT_SECONDS", "300"))
TELEMETRY_FLUSH_SECONDS: int = int(os.environ.get("ERA_TELEMETRY_FLUSH_SECONDS", "60"))
TELEMETRY_OUTBOX_MAX: int = int(os.environ.get("ERA_TELEMETRY_OUTBOX_MAX", "5000"))
TELEMETRY_BATCH_SIZE: int = int(os.environ.get("ERA_TELEMETRY_BATCH_SIZE", "100"))
