"""Development entry point for Era Bridge.

    python main.py

For production/background use (no console window), use
run_bridge.pyw instead -- main.py is the same thing but with a
visible console, useful while developing/debugging.
"""

from __future__ import annotations

import os
from pathlib import Path

# Load .env BEFORE importing settings so env vars are available
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent / ".env"
    if _env_path.exists():
        load_dotenv(dotenv_path=_env_path, override=False)
except ImportError:
    pass

import uvicorn

from config import settings

if __name__ == "__main__":
    uvicorn.run("bridge_server:app", host=settings.BRIDGE_HOST, port=settings.BRIDGE_PORT, log_level="info")
