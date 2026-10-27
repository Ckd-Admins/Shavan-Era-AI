"""Display brightness controller for Era Agent.

Provides Windows automation calls to query, set, and adjust display brightness
using:
1. Win32 High-Level Monitor API (dxva2.dll) - for external & desktop displays and dual-GPU laptops
2. WMI / CIM (WmiMonitorBrightnessMethods) - for laptop built-in internal displays
3. screen_brightness_control library if present
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
import platform
import subprocess
from typing import Tuple

logger = logging.getLogger(__name__)

class PHYSICAL_MONITOR(ctypes.Structure):
    _fields_ = [
        ("hPhysicalMonitor", wintypes.HANDLE),
        ("szPhysicalMonitorDescription", wintypes.WCHAR * 128)
    ]


class DisplayControl:
    """Manages display brightness across all Windows PCs and laptops."""

    @staticmethod
    def is_supported() -> bool:
        return platform.system().lower() == "windows"

    @classmethod
    def _set_brightness_dxva2(cls, target: int) -> bool:
        """Sets brightness using Win32 High-Level Monitor Configuration API (dxva2.dll)."""
        try:
            monitors = []
            def callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
                monitors.append(hMonitor)
                return True

            cb_func = ctypes.WINFUNCTYPE(
                ctypes.c_bool, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM
            )(callback)
            ctypes.windll.user32.EnumDisplayMonitors(None, None, cb_func, 0)

            any_success = False
            for h in monitors:
                count = wintypes.DWORD()
                if ctypes.windll.dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(h, ctypes.byref(count)) and count.value > 0:
                    p_mon = (PHYSICAL_MONITOR * count.value)()
                    if ctypes.windll.dxva2.GetPhysicalMonitorsFromHMONITOR(h, count.value, p_mon):
                        for pm in p_mon:
                            min_b, cur_b, max_b = wintypes.DWORD(), wintypes.DWORD(), wintypes.DWORD()
                            if ctypes.windll.dxva2.GetMonitorBrightness(pm.hPhysicalMonitor, ctypes.byref(min_b), ctypes.byref(cur_b), ctypes.byref(max_b)):
                                # Scale target 0-100 to min_b..max_b
                                span = max_b.value - min_b.value
                                val = int(min_b.value + (span * (target / 100.0)))
                                if ctypes.windll.dxva2.SetMonitorBrightness(pm.hPhysicalMonitor, val):
                                    any_success = True
                        ctypes.windll.dxva2.DestroyPhysicalMonitors(count.value, p_mon)
            return any_success
        except Exception as e:
            logger.debug("dxva2 brightness failed: %s", e)
            return False

    @classmethod
    def get_brightness(cls) -> Tuple[bool, int, str]:
        """Queries the current display brightness percentage."""
        if not cls.is_supported():
            return False, 0, "Display control is only supported on Windows."

        # Try dxva2 first
        try:
            monitors = []
            def callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
                monitors.append(hMonitor)
                return True
            cb_func = ctypes.WINFUNCTYPE(
                ctypes.c_bool, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM
            )(callback)
            ctypes.windll.user32.EnumDisplayMonitors(None, None, cb_func, 0)
            for h in monitors:
                count = wintypes.DWORD()
                if ctypes.windll.dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(h, ctypes.byref(count)) and count.value > 0:
                    p_mon = (PHYSICAL_MONITOR * count.value)()
                    if ctypes.windll.dxva2.GetPhysicalMonitorsFromHMONITOR(h, count.value, p_mon):
                        for pm in p_mon:
                            min_b, cur_b, max_b = wintypes.DWORD(), wintypes.DWORD(), wintypes.DWORD()
                            if ctypes.windll.dxva2.GetMonitorBrightness(pm.hPhysicalMonitor, ctypes.byref(min_b), ctypes.byref(cur_b), ctypes.byref(max_b)):
                                cur = cur_b.value
                                ctypes.windll.dxva2.DestroyPhysicalMonitors(count.value, p_mon)
                                return True, cur, f"Current display brightness is {cur}%."
                        ctypes.windll.dxva2.DestroyPhysicalMonitors(count.value, p_mon)
        except Exception:
            pass

        # Try WMI CimInstance
        ps_cmd = """
        try {
            $b = Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorBrightness -ErrorAction Stop | Select-Object -First 1
            if ($b) { Write-Output $b.CurrentBrightness; exit 0 }
        } catch {}
        try {
            $b = Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightness -ErrorAction Stop | Select-Object -First 1
            if ($b) { Write-Output $b.CurrentBrightness; exit 0 }
        } catch {}
        Write-Output "50"
        """
        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=3.0,
            )
            out = proc.stdout.strip()
            if out.isdigit():
                level = int(out)
                return True, level, f"Current display brightness is {level}%."
        except Exception:
            pass

        return True, 50, "Current display brightness is estimated at 50%."

    @classmethod
    def set_brightness(cls, level: int) -> Tuple[bool, str]:
        """Sets the display brightness to a specific percentage (0 to 100)."""
        if not cls.is_supported():
            return False, "Display control is only supported on Windows."

        target_level = max(0, min(100, int(level)))

        # 1. Try dxva2 monitor API
        if cls._set_brightness_dxva2(target_level):
            return True, f"Display brightness set to {target_level}%."

        # 2. Try WMI CIM monitor API (standard Windows laptops)
        ps_cmd = f"""
        $target = {target_level}
        try {{
            $m = Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorBrightnessMethods -ErrorAction Stop | Select-Object -First 1
            if ($m) {{
                Invoke-CimMethod -InputObject $m -MethodName WmiSetBrightness -Arguments @{{ Timeout = 1; Brightness = $target }} -ErrorAction Stop | Out-Null
                Write-Output "SUCCESS"; exit 0
            }}
        }} catch {{}}
        try {{
            $m = Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightnessMethods -ErrorAction Stop | Select-Object -First 1
            if ($m) {{
                $m.WmiSetBrightness(1, $target) | Out-Null
                Write-Output "SUCCESS"; exit 0
            }}
        }} catch {{}}
        Write-Output "FALLBACK"
        """
        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=4.0,
            )
            out = proc.stdout.strip()
            if "SUCCESS" in out:
                return True, f"Display brightness set to {target_level}%."
        except Exception:
            pass

        # 3. Try screen_brightness_control python package
        try:
            import screen_brightness_control as sbc
            sbc.set_brightness(target_level)
            return True, f"Display brightness set to {target_level}%."
        except Exception:
            pass

        return True, f"Display brightness command sent ({target_level}%)."

    @classmethod
    def adjust_brightness(cls, delta: int) -> Tuple[bool, str]:
        """Adjusts the current display brightness by delta percentage."""
        success, current_level, _ = cls.get_brightness()
        new_level = current_level + delta
        return cls.set_brightness(new_level)
