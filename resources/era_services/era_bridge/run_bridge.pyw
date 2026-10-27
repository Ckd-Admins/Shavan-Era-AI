"""Windowless launcher for Era Bridge.

Uses the .pyw extension so Windows runs it with pythonw.exe -- no
console window. Task Scheduler (see startup/install_task.py) launches
this file so Bridge comes up automatically at logon.
"""

import uvicorn

from config import settings

if __name__ == "__main__":
    uvicorn.run("bridge_server:app", host=settings.BRIDGE_HOST, port=settings.BRIDGE_PORT, log_level="info")
