"""Registers Era Bridge to start automatically at Windows logon.

Separate Task Scheduler entry from Era Local Agent's own (if any) --
installing or removing one has no effect on the other. Uses a
per-user ONLOGON trigger with /RL LIMITED (standard user rights), so
no administrator privileges are required.

Usage:
    python startup/install_task.py install
    python startup/install_task.py uninstall
    python startup/install_task.py status
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TASK_NAME = "EraBridgeService"


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _pythonw_path() -> str:
    exe = Path(sys.executable)
    pythonw = exe.parent / "pythonw.exe"
    return str(pythonw) if pythonw.exists() else str(exe)


def install() -> None:
    runner = _project_root() / "run_bridge.pyw"
    if not runner.exists():
        print(f"Cannot find {runner}. Run this from the project's startup/ folder.")
        return

    command = f'"{_pythonw_path()}" "{runner}"'
    result = subprocess.run(
        [
            "schtasks", "/Create",
            "/TN", TASK_NAME,
            "/TR", command,
            "/SC", "ONLOGON",
            "/RL", "LIMITED",
            "/F",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(f"Task '{TASK_NAME}' installed. Era Bridge will start automatically at your next logon.")
        print(f"To start it right now without logging off, run: schtasks /Run /TN {TASK_NAME}")
    else:
        print("Failed to install the task:")
        print(result.stderr or result.stdout)


def uninstall() -> None:
    result = subprocess.run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"], capture_output=True, text=True)
    print(result.stdout or result.stderr)


def status() -> None:
    result = subprocess.run(["schtasks", "/Query", "/TN", TASK_NAME], capture_output=True, text=True)
    print(result.stdout or result.stderr)


if __name__ == "__main__":
    actions = {"install": install, "uninstall": uninstall, "status": status}
    if len(sys.argv) != 2 or sys.argv[1] not in actions:
        print("Usage: python startup/install_task.py [install|uninstall|status]")
        sys.exit(1)
    actions[sys.argv[1]]()
