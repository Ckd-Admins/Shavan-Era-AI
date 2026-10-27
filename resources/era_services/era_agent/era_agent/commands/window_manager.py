"""Window management utilities for Era Agent.

Provides cross-window positioning, snapping, and layout helpers using the
Windows Win32 API via ctypes (no third-party dependencies required).

Supported positions:
    left, right, top, bottom,
    top-left, top-right, bottom-left, bottom-right,
    maximize, minimize, restore
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional, Tuple, List

# ---------------------------------------------------------------------------
# Win32 constants
# ---------------------------------------------------------------------------
SW_RESTORE = 9
SW_MINIMIZE = 6
SW_MAXIMIZE = 3
SW_SHOWNORMAL = 1

SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SWP_FRAMECHANGED = 0x0020

HWND_TOP = 0

user32 = ctypes.windll.user32
user32.GetSystemMetrics.restype = ctypes.c_int
user32.FindWindowW.restype = ctypes.wintypes.HWND
user32.SetWindowPos.restype = ctypes.wintypes.BOOL
user32.ShowWindow.restype = ctypes.wintypes.BOOL
user32.EnumWindows.restype = ctypes.wintypes.BOOL
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.IsWindowVisible.restype = ctypes.wintypes.BOOL
user32.GetForegroundWindow.restype = ctypes.wintypes.HWND
user32.SetForegroundWindow.restype = ctypes.wintypes.BOOL

ENUM_CALLBACK = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)


def get_screen_dimensions() -> Tuple[int, int]:
    """Returns (width, height) of the primary monitor in pixels."""
    w = user32.GetSystemMetrics(0)
    h = user32.GetSystemMetrics(1)
    return w, h


def _compute_rect(position: str) -> Tuple[int, int, int, int]:
    """Returns (x, y, width, height) for the given named position."""
    W, H = get_screen_dimensions()
    half_w = W // 2
    half_h = H // 2
    pos = position.strip().lower()
    rects = {
        "left":         (0,       0,       half_w, H),
        "right":        (half_w,  0,       half_w, H),
        "top":          (0,       0,       W,      half_h),
        "bottom":       (0,       half_h,  W,      half_h),
        "top-left":     (0,       0,       half_w, half_h),
        "top-right":    (half_w,  0,       half_w, half_h),
        "bottom-left":  (0,       half_h,  half_w, half_h),
        "bottom-right": (half_w,  half_h,  half_w, half_h),
        "upper-left":   (0,       0,       half_w, half_h),
        "upper-right":  (half_w,  0,       half_w, half_h),
        "lower-left":   (0,       half_h,  half_w, half_h),
        "lower-right":  (half_w,  half_h,  half_w, half_h),
    }
    return rects.get(pos, (0, 0, W, H))


def _enum_windows() -> List[ctypes.wintypes.HWND]:
    handles: List[ctypes.wintypes.HWND] = []
    def callback(hwnd, lparam):
        if user32.IsWindowVisible(hwnd):
            handles.append(hwnd)
        return True
    user32.EnumWindows(ENUM_CALLBACK(callback), 0)
    return handles


def _get_window_title(hwnd) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def find_window_by_name(app_name: str) -> Optional[int]:
    """Find a visible top-level window whose title contains app_name."""
    name_lower = app_name.strip().lower()
    title_hints = {
        "whatsapp":         ["whatsapp"],
        "vscode":           ["visual studio code", "vscode"],
        "code":             ["visual studio code", "vscode"],
        "visual studio code": ["visual studio code"],
        "chrome":           ["google chrome", "chrome"],
        "edge":             ["microsoft edge", "msedge", "edge"],
        "microsoft edge":   ["microsoft edge"],
        "firefox":          ["mozilla firefox", "firefox"],
        "notepad":          ["notepad"],
        "calculator":       ["calculator"],
        "explorer":         ["file explorer", "windows explorer"],
        "store":            ["microsoft store"],
        "microsoft store":  ["microsoft store"],
        "xbox":             ["xbox"],
        "spotify":          ["spotify"],
        "discord":          ["discord"],
        "teams":            ["microsoft teams"],
        "word":             ["microsoft word", "word"],
        "excel":            ["microsoft excel", "excel"],
        "powerpoint":       ["microsoft powerpoint", "powerpoint"],
        "outlook":          ["outlook"],
    }
    hints = title_hints.get(name_lower, [name_lower])
    for hwnd in _enum_windows():
        title = _get_window_title(hwnd).lower()
        if not title:
            continue
        for hint in hints:
            if hint in title:
                return hwnd
    return None


def snap_window(hwnd: int, position: str) -> bool:
    """Snap a window to the given named position on screen."""
    pos = position.strip().lower()
    user32.ShowWindow(hwnd, SW_RESTORE)
    time.sleep(0.15)
    if pos == "maximize":
        user32.ShowWindow(hwnd, SW_MAXIMIZE)
        return True
    if pos == "minimize":
        user32.ShowWindow(hwnd, SW_MINIMIZE)
        return True
    if pos == "restore":
        user32.ShowWindow(hwnd, SW_SHOWNORMAL)
        return True
    x, y, w, h = _compute_rect(pos)
    result = user32.SetWindowPos(hwnd, HWND_TOP, x, y, w, h, SWP_NOZORDER | SWP_SHOWWINDOW | SWP_FRAMECHANGED)
    user32.SetForegroundWindow(hwnd)
    return bool(result)


def _find_uwp_app_id(app_name: str) -> Optional[str]:
    """Use PowerShell Get-StartApps to find an AppID for UWP/Store apps."""
    try:
        ps = ["powershell", "-NoProfile", "-Command",
              "Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress"]
        proc = subprocess.run(ps, capture_output=True, text=True, timeout=6.0)
        out = proc.stdout.strip()
        if not out:
            return None
        import json
        data = json.loads(out)
        apps = data if isinstance(data, list) else [data]
        name_lower = app_name.lower()
        for entry in apps:
            nm = entry.get("Name", "")
            aid = entry.get("AppID") or entry.get("AppId")
            if nm and aid and name_lower in nm.lower():
                return aid
    except Exception:
        pass
    return None


def _find_app_executable(app_name: str) -> Optional[str]:
    """Locate an app exe / UWP id by name."""
    if not app_name:
        return None
    candidate = Path(app_name)
    if candidate.exists():
        return str(candidate)
    which_result = shutil.which(app_name)
    if which_result:
        return which_result
    name_lower = app_name.lower()
    user = os.environ.get("USERNAME", "")
    known = {
        "chrome":   [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                     r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"],
        "edge":     [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                     r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"],
        "msedge":   [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                     r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"],
        "firefox":  [r"C:\Program Files\Mozilla Firefox\firefox.exe",
                     r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe"],
        "vscode":   [r"C:\Users\{user}\AppData\Local\Programs\Microsoft VS Code\Code.exe"],
        "code":     [r"C:\Users\{user}\AppData\Local\Programs\Microsoft VS Code\Code.exe"],
    }
    for key, paths in known.items():
        if key in name_lower or name_lower in key:
            for p in paths:
                resolved = p.replace("{user}", user)
                if Path(resolved).exists():
                    return resolved
    start_menu_locations = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        start_menu_locations.append(Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    programdata = os.environ.get("PROGRAMDATA")
    if programdata:
        start_menu_locations.append(Path(programdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    for sm in start_menu_locations:
        if not sm.exists():
            continue
        for root, _dirs, files in os.walk(sm):
            for f in files:
                if f.lower().endswith(".lnk") and name_lower in f.lower():
                    lnk_path = str(Path(root) / f)
                    try:
                        ps_cmd = ('$s=(New-Object -ComObject WScript.Shell).CreateShortcut("%s");$s.TargetPath') % lnk_path.replace("\\", "\\\\")
                        proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd],
                                              capture_output=True, text=True, timeout=3.0)
                        target = proc.stdout.strip()
                        if target:
                            return target
                    except Exception:
                        pass
                    return lnk_path
    uwp_id = _find_uwp_app_id(app_name)
    if uwp_id:
        return f"uwp:{uwp_id}"
    return None


def _launch_app(app_name: str) -> bool:
    """Launch an app by name. Returns True if the launch command was issued."""
    found = _find_app_executable(app_name)
    if not found:
        try:
            subprocess.Popen(["powershell", "-NoProfile", "-Command", f"Start-Process '{app_name}'"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False
    try:
        if found.startswith("uwp:"):
            appid = found.split("uwp:", 1)[1]
            subprocess.Popen(["explorer.exe", f"shell:Appsfolder\\{appid}"])
        elif found.lower().endswith(".lnk") or not found.lower().endswith(".exe"):
            os.startfile(found)
        else:
            subprocess.Popen([found])
        return True
    except OSError:
        return False


def launch_and_snap(app_name: str, position: str, wait_seconds: float = 5.0) -> Tuple[bool, str]:
    """Launch app_name if not visible, then snap it to position.

    Returns (success, message).
    """
    hwnd = find_window_by_name(app_name)
    if hwnd is None:
        launched = _launch_app(app_name)
        if not launched:
            return False, f"Could not find or launch '{app_name}'."
        deadline = time.time() + wait_seconds
        while time.time() < deadline:
            time.sleep(0.6)
            hwnd = find_window_by_name(app_name)
            if hwnd is not None:
                break
    if hwnd is None:
        time.sleep(2.0)
        hwnd = find_window_by_name(app_name)
    if hwnd is None:
        return False, (f"'{app_name}' was launched but its window could not be detected. "
                       "It may take longer to start.")
    time.sleep(0.3)
    pos_lbl = position.strip().lower()
    if pos_lbl in ("maximize", "minimize", "restore"):
        success = snap_window(hwnd, pos_lbl)
        action_word = pos_lbl.capitalize() + "d"
        return (True, f"'{app_name}' {action_word} successfully.") if success else (False, f"Failed to {pos_lbl} '{app_name}'.")
    success = snap_window(hwnd, pos_lbl)
    if success:
        W, H = get_screen_dimensions()
        x, y, w, h = _compute_rect(pos_lbl)
        return True, f"'{app_name}' snapped to {pos_lbl} (x={x}, y={y}, w={w}, h={h}) on {W}x{H} screen."
    else:
        return False, f"Found '{app_name}' window but could not reposition it."
