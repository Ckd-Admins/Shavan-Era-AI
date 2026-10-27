"""Minimal, non-identifying hardware facts. No hostname, username, serial numbers, MACs, IPs or paths."""

from __future__ import annotations

import os
import platform
from typing import Any, Dict, Optional


def _ram_gb() -> Optional[int]:
    try:
        if platform.system() == "Windows":
            import ctypes

            class MEMSTAT(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

            stat = MEMSTAT()
            stat.dwLength = ctypes.sizeof(MEMSTAT)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))  # type: ignore[attr-defined]
            return max(1, round(stat.ullTotalPhys / 1024**3))
        with open("/proc/meminfo", encoding="ascii") as fh:
            kb = int(fh.readline().split()[1])
        return max(1, round(kb / 1024**2))
    except Exception:  # noqa: BLE001 - optional field
        return None


def collect(era_version: str) -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "era_version": era_version,
        "os": platform.system() or "Unknown",
        "os_version": (platform.release() or "")[:60] or None,
        "arch": (platform.machine() or "")[:30] or None,
        "cpu_cores": os.cpu_count(),
        "ram_gb": _ram_gb(),
    }
    return {k: v for k, v in info.items() if v is not None}  # GPU model is not collected in this phase
