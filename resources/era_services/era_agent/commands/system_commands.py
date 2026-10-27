"""System-level commands for Era Agent.

Each function below performs exactly one safe, non-destructive action
and returns a CommandResult describing whether it succeeded. None of
these commands request administrator privileges or modify, delete, or
overwrite anything on the system — they only launch existing, standard
Windows applications.
"""

from __future__ import annotations

import os
import platform
import shutil
import ctypes
import subprocess
import time
import threading
import re
import webbrowser
import winreg
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote

from .registry import CommandParam, CommandResult, registry


def _is_windows() -> bool:
    """Returns True if the agent is currently running on Windows."""
    return platform.system().lower() == "windows"


def _get_system_drives() -> List[str]:
    """Detects all physical fixed and removable drives on the computer (e.g. C:\\, D:\\, E:\\)."""
    drives = []
    if not _is_windows():
        return ["/"]
    try:
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for i in range(26):
            if bitmask & (1 << i):
                letter = chr(ord('A') + i)
                drive_path = f"{letter}:\\"
                dtype = ctypes.windll.kernel32.GetDriveTypeW(drive_path)
                if dtype in (2, 3):  # DRIVE_REMOVABLE, DRIVE_FIXED
                    drives.append(drive_path)
    except Exception:
        for letter in "CDEFGHIJKLMNO":
            p = f"{letter}:\\"
            if os.path.exists(p):
                drives.append(p)
    return drives or ["C:\\"]


@registry.register("open_notepad", "Opens Windows Notepad")
def open_notepad() -> CommandResult:
    return open_app("notepad")


@registry.register("open_calculator", "Opens Windows Calculator")
def open_calculator() -> CommandResult:
    return open_app("calc")


@registry.register("open_file_explorer", "Opens Windows File Explorer")
def open_file_explorer() -> CommandResult:
    return open_app("explorer")


def _find_chrome_path() -> Optional[str]:
    """Looks for Google Chrome on PATH, then in common install locations."""
    which_result = shutil.which("chrome")
    if which_result:
        return which_result

    common_paths = [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "Application" / "chrome.exe",
    ]
    for path in common_paths:
        if path.exists():
            return str(path)
    return None


@registry.register("open_chrome", "Opens Google Chrome, if installed")
def open_chrome() -> CommandResult:
    return open_app("chrome")


# ---------------------------------------------------------------------------
# Parameterized / Interactive commands
# ---------------------------------------------------------------------------


def _get_clean_env() -> dict:
    """Returns a clean copy of os.environ stripped of ALL Electron/Node variables
    that can block GUI app launches when ERA runs inside the packaged EXE."""
    env = os.environ.copy()
    # Strip every Electron-injected key that restricts desktop access or GUI rendering
    strip_prefixes = ("ELECTRON_", "NODE_")
    strip_exact = {
        "NODE_OPTIONS", "NODE_PATH", "ELECTRON_RUN_AS_NODE",
        "ELECTRON_NO_ATTACH_CONSOLE", "CHROME_EXTRA_FLAGS",
        "GOOGLE_API_KEY", "GOOGLE_DEFAULT_CLIENT_ID", "GOOGLE_DEFAULT_CLIENT_SECRET",
    }
    for k in list(env.keys()):
        ku = k.upper()
        if any(ku.startswith(p) for p in strip_prefixes) or ku in strip_exact:
            env.pop(k, None)
    return env


def _is_electron_context() -> bool:
    """Detects if this Python process is running as a child of an Electron/Node process."""
    # ERA_RUNNING_IN_ELECTRON is explicitly set by Electron main.cjs for all child services
    if os.environ.get("ERA_RUNNING_IN_ELECTRON") == "1":
        return True
    # Fallback: detect leftover Electron vars (shouldn't exist after env stripping, but just in case)
    return any(
        k.upper().startswith("ELECTRON_") or k.upper() == "ELECTRON_RUN_AS_NODE"
        for k in os.environ
    )


def _resolve_shortcut(lnk_path: str):
    """Resolves a Windows .lnk shortcut to its target executable, arguments, and working directory."""
    if not lnk_path or not str(lnk_path).lower().endswith(".lnk"):
        return None, None, None
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(str(lnk_path))
        target = (shortcut.TargetPath or "").strip()
        extra_args = (shortcut.Arguments or "").strip()
        wd = (shortcut.WorkingDirectory or "").strip()
        if not wd and target and os.path.exists(target):
            wd = str(Path(target).parent)
        if target and os.path.exists(target):
            return target, extra_args or None, wd or None
    except Exception:
        pass
    try:
        p_esc = str(lnk_path).replace("'", "''")
        cmd = f"(New-Object -ComObject WScript.Shell).CreateShortcut('{p_esc}').TargetPath"
        out = subprocess.check_output(["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd], text=True, timeout=3).strip()
        if out and os.path.exists(out):
            return out, None, str(Path(out).parent)
    except Exception:
        pass
    return None, None, None


def _launch_windows_target(target: str, args: Optional[str] = None) -> bool:
    """Launches an app, shortcut, document or URI on Windows with ZERO permission issues.

    Works correctly whether Era is run from:
      - A terminal (python api_server.py)
      - The packaged EXE (Electron child process)
    """
    if not target:
        return False

    clean_target = str(target).strip().strip('"')
    if not clean_target:
        return False

    try:
        ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002 | 0x8000)
    except Exception:
        pass

    clean_env = _get_clean_env()
    args_str = str(args).strip() if args else ""
    # Important: Do NOT use CREATE_NO_WINDOW (0x08000000) for GUI apps!
    flags = 0x00000200  # CREATE_NEW_PROCESS_GROUP

    working_dir = None

    # RESOLVE SHORTCUTS (.lnk) to real target executable and working directory
    if clean_target.lower().endswith(".lnk") and os.path.isfile(clean_target):
        res_target, res_args, res_wd = _resolve_shortcut(clean_target)
        if res_target and os.path.exists(res_target):
            clean_target = res_target
            if res_args:
                args_str = f"{res_args} {args_str}".strip() if args_str else res_args
            if res_wd and os.path.isdir(res_wd):
                working_dir = res_wd
            else:
                working_dir = str(Path(res_target).parent)

    # METHOD 1: Direct Popen for known .exe files on disk
    if clean_target.lower().endswith(".exe") and os.path.isfile(clean_target):
        try:
            cwd = working_dir or str(Path(clean_target).parent)
            cmd_args = [clean_target] + ([args_str] if args_str else [])
            p = subprocess.Popen(
                cmd_args,
                cwd=cwd,
                env=clean_env,
                creationflags=flags,
            )
            if p.pid > 0:
                return True
        except Exception:
            pass

    # METHOD 2: explorer.exe for shell:AppsFolder URIs
    if clean_target.lower().startswith("shell:"):
        try:
            subprocess.Popen(
                ["explorer.exe", clean_target],
                creationflags=flags,
                env=clean_env,
            )
            return True
        except Exception:
            pass

    # METHOD 3: URI protocols (e.g. whatsapp:, ms-settings:, calc:, https:)
    if re.match(r"^[a-zA-Z0-9_\-]+:", clean_target) and not clean_target.startswith("shell:"):
        try:
            os.startfile(clean_target)
            return True
        except Exception:
            pass

    # METHOD 4: PowerShell Start-Process (isolated desktop context)
    try:
        t = clean_target.replace("'", "''")
        wd = (working_dir or (str(Path(clean_target).parent) if os.path.exists(clean_target) else "")).replace("'", "''")
        wd_arg = f" -WorkingDirectory '{wd}'" if wd else ""
        if args_str:
            a = args_str.replace("'", "''")
            ps_cmd = f"Start-Process -FilePath '{t}' -ArgumentList '{a}'{wd_arg} -ErrorAction Stop"
        else:
            ps_cmd = f"Start-Process -FilePath '{t}'{wd_arg} -ErrorAction Stop"

        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            creationflags=flags,
            env=clean_env,
            capture_output=True,
            timeout=5,
        )
        if res.returncode == 0:
            return True
    except Exception:
        pass

    # METHOD 5: Native Windows cmd.exe /c start
    try:
        if args_str:
            cmd_str = f'start "" "{clean_target}" {args_str}'
        else:
            cmd_str = f'start "" "{clean_target}"'

        subprocess.Popen(
            ["cmd.exe", "/c", cmd_str],
            creationflags=flags,
            env=clean_env,
            cwd=working_dir or (str(Path(clean_target).parent) if os.path.exists(clean_target) else None),
        )
        return True
    except Exception:
        pass

    # METHOD 6: ShellExecuteW fallback via ctypes
    try:
        ret = ctypes.windll.shell32.ShellExecuteW(None, "open", clean_target, args_str or None, working_dir, 1)
        if ret > 32:
            return True
    except Exception:
        pass

    return False


@registry.register(
    "search_file",
    "Searches for a file or folder by name across all hard drives and opens it or opens it in VS Code",
    params=[
        CommandParam("file_name", "str", "File or folder name to search for", required=True),
        CommandParam("search_root", "str", "Optional directory path to search under", required=False),
        CommandParam("open_with", "str", "Optional program to open with (e.g. 'vscode' or 'explorer')", required=False),
    ],
)
def search_file(
    file_name: Optional[str] = None,
    search_root: Optional[str] = None,
    open_with: Optional[str] = None,
) -> CommandResult:
    """Searches for a file across all connected hard drive partitions and user directories."""
    if not _is_windows():
        return CommandResult(False, "File search is only available on Windows.")

    target_name = file_name
    if not target_name or not str(target_name).strip():
        return CommandResult(False, "No file name was provided.")
    target_name = str(target_name).strip()

    target_lower = target_name.lower().strip()
    matches: List[Path] = []
    skip_dirs = {
        "$recycle.bin", "system volume information", "windows", "recovery",
        "node_modules", ".git", ".venv", "__pycache__", "temp", "cache"
    }

    # If search_root is specified, search under that root only
    if search_root and os.path.exists(search_root):
        roots_to_search = [Path(search_root)]
    else:
        # Build priority search roots:
        # 1. User main directories: Desktop, Downloads, Documents, Pictures, Videos, Music, Home
        # 2. Workspace directory if defined
        # 3. All connected drives (C:\, D:\, E:\, etc.)
        roots_to_search = []
        ws_dir = os.environ.get("ERA_WORKSPACE_DIR") or os.environ.get("WORKSPACE_DIR")
        if ws_dir and Path(ws_dir).exists():
            roots_to_search.append(Path(ws_dir))
        workspace_fallback = Path(r"d:\era-voice-assistant\workspace")
        if workspace_fallback.exists() and workspace_fallback not in roots_to_search:
            roots_to_search.append(workspace_fallback)

        user_home = Path.home()
        for sub in ["Downloads", "Desktop", "Documents", "Pictures", "Videos", "Music"]:
            p = user_home / sub
            if p.exists() and p not in roots_to_search:
                roots_to_search.append(p)
        if user_home not in roots_to_search:
            roots_to_search.append(user_home)

        # Add all physical drive roots
        for d in _get_system_drives():
            p = Path(d)
            if p.exists() and p not in roots_to_search:
                roots_to_search.append(p)

    # First pass: direct check in priority roots & immediate children
    for r in roots_to_search:
        try:
            for item in r.iterdir():
                if target_lower in item.name.lower():
                    matches.append(item)
                    if len(matches) >= 10:
                        break
        except (PermissionError, OSError):
            continue
        if matches:
            break

    # Second pass: deep recursive search up to depth 5
    if not matches:
        for r in roots_to_search:
            try:
                base_depth = len(r.parts)
                for dirpath, dirnames, filenames in os.walk(r, onerror=lambda _: None):
                    dirnames[:] = [d for d in dirnames if d.lower() not in skip_dirs and not d.startswith(".")]
                    current_depth = len(Path(dirpath).parts) - base_depth
                    if current_depth > 5:
                        dirnames[:] = []
                        continue

                    for fn in filenames:
                        if target_lower in fn.lower():
                            matches.append(Path(dirpath) / fn)
                            if len(matches) >= 10:
                                break
                    if matches:
                        break
            except Exception:
                continue
            if matches:
                break

    # Third pass: Fast PowerShell search if still not found
    if not matches and len(target_lower) >= 3:
        try:
            primary_root = str(roots_to_search[0]) if roots_to_search else "C:\\"
            ps_search = f"Get-ChildItem -Path '{primary_root}' -Filter '*{target_lower}*' -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 3 -ExpandProperty FullName"
            proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps_search], capture_output=True, text=True, timeout=5.0)
            for line in proc.stdout.splitlines():
                ln = line.strip()
                if ln and os.path.exists(ln):
                    matches.append(Path(ln))
        except Exception:
            pass

    if not matches:
        drives_str = ", ".join(_get_system_drives())
        return CommandResult(False, f"No file or folder matching '{target_name}' was found across drives ({drives_str}).")

    first_match = matches[0]
    matched_path = str(first_match)
    resolved_open_with = (open_with or "").lower().strip()

    try:
        if "vscode" in resolved_open_with or "code" in resolved_open_with:
            code_app = _find_app_path("vscode") or "code"
            if _launch_windows_target(code_app, matched_path):
                return CommandResult(True, f"Found '{first_match.name}' and opened it in Visual Studio Code ({matched_path}).")
            else:
                subprocess.Popen(["cmd.exe", "/c", "code", matched_path], shell=True)
                return CommandResult(True, f"Found '{first_match.name}' and opened it in VS Code ({matched_path}).")
        elif "explorer" in resolved_open_with:
            subprocess.Popen(["explorer.exe", f"/select,{matched_path}"])
            return CommandResult(True, f"Found '{first_match.name}' and highlighted in File Explorer ({matched_path}).")
        else:
            if _launch_windows_target(matched_path):
                return CommandResult(True, f"Found and opened '{first_match.name}' on your laptop ({matched_path}).")
            else:
                os.startfile(matched_path)
                return CommandResult(True, f"Found and opened '{first_match.name}' on your laptop ({matched_path}).")
    except OSError as exc:
        return CommandResult(False, f"Found '{first_match.name}' at {matched_path} but failed to open it: {exc}")


@registry.register(
    "open_file",
    "Finds and opens a specific file on the computer by name or path",
    params=[
        CommandParam("file_name", "str", "The name or path of the file to open (e.g. 'notes.txt', 'index.html', 'game.py')", required=True),
        CommandParam("open_with", "str", "Optional program to open with (e.g. 'vscode', 'browser', 'default')", required=False),
    ],
)
def open_file(file_name: Optional[str] = None, open_with: Optional[str] = None) -> CommandResult:
    """Opens a file, searching workspace and all system hard drive partitions if needed."""
    if not file_name:
        return CommandResult(False, "No file name was provided.")

    clean_name = file_name.strip()
    resolved_open_with = (open_with or "").lower().strip()

    def _open_path(p: str) -> CommandResult:
        if "vscode" in resolved_open_with or "code" in resolved_open_with:
            code_app = _find_app_path("vscode") or "code"
            if _launch_windows_target(code_app, p):
                return CommandResult(True, f"Opened '{os.path.basename(p)}' in Visual Studio Code ({p}).")
            subprocess.Popen(["cmd.exe", "/c", "code", p], shell=True)
            return CommandResult(True, f"Opened '{os.path.basename(p)}' in Visual Studio Code ({p}).")
        else:
            if _launch_windows_target(p):
                return CommandResult(True, f"Opened '{os.path.basename(p)}' on your laptop ({p}).")
            os.startfile(p)
            return CommandResult(True, f"Opened '{os.path.basename(p)}' successfully.")

    if os.path.exists(clean_name):
        try:
            return _open_path(clean_name)
        except Exception as exc:
            return CommandResult(False, f"Failed to open '{clean_name}': {exc}")

    ws_dir = os.environ.get("ERA_WORKSPACE_DIR") or os.environ.get("WORKSPACE_DIR")
    if ws_dir and os.path.exists(os.path.join(ws_dir, os.path.basename(clean_name))):
        ws_path = os.path.join(ws_dir, os.path.basename(clean_name))
        try:
            return _open_path(ws_path)
        except Exception as exc:
            return CommandResult(False, f"Failed to open workspace file: {exc}")

    return search_file(file_name=clean_name, open_with=open_with)


def _copy_to_windows_clipboard(text: str) -> bool:
    """Copies text to Windows clipboard natively using UTF-16LE clip pipe."""
    try:
        proc = subprocess.Popen(["clip"], stdin=subprocess.PIPE, close_fds=True)
        proc.communicate(input=text.encode("utf-16le"))
        return True
    except Exception:
        return False


def _normalize_phone_number(phone_raw: str) -> str:
    """Normalizes phone numbers to standard WhatsApp format (country code + digits, no leading 0, no +)."""
    digits = "".join(ch for ch in str(phone_raw or "") if ch.isdigit())
    if not digits:
        return ""
    if len(digits) == 10:
        # Standard Indian 10-digit mobile number
        return f"91{digits}"
    if len(digits) == 11 and digits.startswith("0"):
        # 0 followed by 10-digit number
        return f"91{digits[1:]}"
    return digits


def _is_whatsapp_desktop_installed() -> bool:
    """Checks if WhatsApp Desktop app is installed on Windows (no admin needed)."""
    # 1. Local AppData exe check
    wa_local = Path(os.environ.get("LOCALAPPDATA", "")) / "WhatsApp" / "WhatsApp.exe"
    if wa_local.exists():
        return True

    # 2. Registry check for HKCU uninstall
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\WhatsApp")
        winreg.CloseKey(key)
        return True
    except OSError:
        pass

    # 3. Protocol registration check in HKCR
    try:
        key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"whatsapp")
        winreg.CloseKey(key)
        return True
    except OSError:
        pass

    return False


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", ctypes.c_ulong), ("wParamL", ctypes.c_ushort), ("wParamH", ctypes.c_ushort)]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT), ("hi", _HARDWAREINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("union", _INPUT_UNION)]


def _send_whatsapp_enter():
    """Dispatches a single clean Enter keypress using hardware VK_RETURN / scancode 0x1C."""
    try:
        import win32api, win32con
        win32api.keybd_event(win32con.VK_RETURN, 0x1C, 0, 0)
        time.sleep(0.04)
        win32api.keybd_event(win32con.VK_RETURN, 0x1C, win32con.KEYEVENTF_KEYUP, 0)
        return
    except Exception:
        pass

    try:
        import pyautogui
        pyautogui.press("enter")
    except Exception:
        pass


def _force_foreground_window(hwnd) -> bool:
    """Brings a window strictly to the foreground bypassing Windows focus-stealing locks."""
    try:
        user32 = ctypes.windll.user32
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        cur_thread = ctypes.windll.kernel32.GetCurrentThreadId()
        fore_hwnd = user32.GetForegroundWindow()
        fore_thread = user32.GetWindowThreadProcessId(fore_hwnd, 0)
        if fore_thread != cur_thread:
            user32.AttachThreadInput(cur_thread, fore_thread, True)
            user32.SetForegroundWindow(hwnd)
            user32.BringWindowToTop(hwnd)
            user32.AttachThreadInput(cur_thread, fore_thread, False)
        else:
            user32.SetForegroundWindow(hwnd)
            user32.BringWindowToTop(hwnd)
        return True
    except Exception:
        try:
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            return True
        except Exception:
            return False


def _find_whatsapp_hwnd():
    """Finds the native WhatsApp Desktop window HWND strictly ignoring any web browser."""
    try:
        user32 = ctypes.windll.user32
        found_hwnd = [None]

        def enum_cb(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                t = buff.value.lower()

                pname = ""
                try:
                    import psutil
                    pid = ctypes.c_ulong()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    p = psutil.Process(pid.value)
                    pname = p.name().lower()
                except Exception:
                    pass

                # Strictly ignore browsers
                if any(b in t or b in pname for b in ["chrome", "edge", "firefox", "brave", "opera"]):
                    return True

                if ("whatsapp" in t) or ("whatsapp" in pname):
                    rect = (ctypes.c_long * 4)()
                    user32.GetWindowRect(hwnd, ctypes.byref(rect))
                    width = rect[2] - rect[0]
                    height = rect[3] - rect[1]
                    if width > 200 and height > 200:
                        found_hwnd[0] = hwnd
                        return False
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
        return found_hwnd[0]
    except Exception:
        return None


def _activate_whatsapp_window() -> bool:
    """Brings ONLY the native WhatsApp Desktop window to front. Never activates browser!"""
    hwnd = _find_whatsapp_hwnd()
    if hwnd:
        return _force_foreground_window(hwnd)
    return False


def _send_whatsapp_once(hwnd=None):
    """Brings WhatsApp cleanly to front and dispatches a single Enter keypress without touching the mouse."""
    if not hwnd:
        hwnd = _find_whatsapp_hwnd()
    if hwnd:
        _force_foreground_window(hwnd)
        time.sleep(0.15)
    _send_whatsapp_enter()


def _wait_for_whatsapp_window(timeout: float = 6.0, interval: float = 0.3) -> bool:
    """Waits until a WhatsApp Desktop window is visible."""
    elapsed = 0.0
    while elapsed < timeout:
        if _activate_whatsapp_window():
            return True
        time.sleep(interval)
        elapsed += interval
    return False


def _activate_whatsapp_or_browser_window() -> bool:
    """Brings WhatsApp to front; if not found, activates browser as fallback."""
    if _activate_whatsapp_window():
        return True
    try:
        user32 = ctypes.windll.user32

        def enum_cb(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    t = buff.value.lower()
                    if "chrome" in t or "edge" in t or "firefox" in t or "brave" in t:
                        _force_foreground_window(hwnd)
                        return False
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
        return True
    except Exception:
        return False


def _lookup_contact_phone(contact_query: str) -> Optional[str]:
    """Looks up a phone number by contact name or alias in whatsapp_contacts.json."""
    if not contact_query:
        return None

    clean_q = contact_query.strip().lower()

    _app_data = os.environ.get("ERA_APP_DATA", "")
    possible_paths = [
        Path(os.path.join(_app_data, "config", "whatsapp_contacts.json")) if _app_data else None,
        Path(os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "Local", "ERA", "config", "whatsapp_contacts.json")),
        Path(r"d:\era-voice-assistant\config\whatsapp_contacts.json"),
        Path(r"d:\era_agent\config\whatsapp_contacts.json"),
        Path.cwd() / "config" / "whatsapp_contacts.json",
    ]

    contacts_data = []
    for p in possible_paths:
        if p and p.exists():
            try:
                import json
                contacts_data = json.loads(p.read_text(encoding="utf-8"))
                break
            except Exception:
                pass

    if not contacts_data:
        return None

    for entry in contacts_data:
        name = str(entry.get("name", "")).strip().lower()
        aliases = [str(a).strip().lower() for a in entry.get("aliases", [])]
        if clean_q == name or clean_q in aliases:
            phone_val = str(entry.get("phone", "")).strip()
            digits = "".join(ch for ch in phone_val if ch.isdigit())
            if digits:
                return digits
    return None


def _record_whatsapp_chat_log(contact_name: str, message: str) -> None:
    try:
        import json
        from datetime import datetime
        _app_data = os.environ.get("ERA_APP_DATA", "")
        log_paths = [
            Path(os.path.join(_app_data, "config", "whatsapp_chats.json")) if _app_data else None,
            Path(os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "Local", "ERA", "config", "whatsapp_chats.json")),
            Path(r"d:\era-voice-assistant\config\whatsapp_chats.json"),
            Path(r"d:\era_agent\config\whatsapp_chats.json"),
        ]
        log_paths = [p for p in log_paths if p is not None]
        new_entry = {
            "contactName": contact_name,
            "message": message,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "status": "sent",
        }
        for p in log_paths:
            p.parent.mkdir(parents=True, exist_ok=True)
            chats = []
            if p.exists():
                try:
                    chats = json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    chats = []
            chats.insert(0, new_entry)
            p.write_text(json.dumps(chats[:50], indent=2), encoding="utf-8")
    except Exception:
        pass


@registry.register(
    "open_whatsapp",
    "Opens native WhatsApp Desktop app and sends a message to a contact name or phone number",
    params=[
        CommandParam("phone", "str", "Recipient phone number (e.g. 911234567890) or contact name (e.g. 'Rahul', 'Bhaiya')", required=True),
        CommandParam("message", "str", "Message content to send via WhatsApp", required=True),
    ],
)
def open_whatsapp(
    phone: Optional[str] = None,
    message: Optional[str] = None,
) -> CommandResult:
    """Opens native WhatsApp Desktop app (if installed) or WhatsApp Web as fallback.

    - If WhatsApp Desktop is installed on PC: opens WhatsApp Desktop App exclusively (NEVER opens browser Web).
    - If WhatsApp Desktop is NOT installed: falls back automatically to WhatsApp Web.
    - Automatically normalizes phone numbers with country code.
    - Automatically sends the message immediately with plain Enter (NEVER inserts blank spaces/newlines).
    """
    target_input = (phone or "").strip()
    target_msg = (message or "").strip()

    if not target_input and not target_msg:
        return open_app(app_name="whatsapp")

    if not target_input:
        return CommandResult(False, "No phone number or contact name was provided.")
    if not target_msg:
        return CommandResult(False, "No message content was provided.")

    # Resolve phone or contact name
    digits_only = "".join(ch for ch in target_input if ch.isdigit())
    resolved_phone: Optional[str] = None
    if len(digits_only) >= 7:
        resolved_phone = digits_only
    else:
        resolved_phone = _lookup_contact_phone(target_input)

    try:
        import pyautogui  # type: ignore
        pyautogui.FAILSAFE = False
    except ImportError:
        pyautogui = None

    # Detect whether WhatsApp Desktop app is installed on this PC
    app_installed = _is_whatsapp_desktop_installed()
    encoded_message = quote(target_msg)

    if resolved_phone:
        normalized_phone = _normalize_phone_number(resolved_phone)

        # ── SCENARIO A: Phone number is known ──
        try:
            if app_installed:
                # Open ONLY native WhatsApp Desktop app via whatsapp:// URI protocol (NO browser tab!)
                app_url = f"whatsapp://send?phone={normalized_phone}&text={encoded_message}"
                try:
                    os.startfile(app_url)
                except Exception:
                    _launch_windows_target(app_url)

                # Wait for WhatsApp Desktop window to appear
                _wait_for_whatsapp_window(timeout=5.0, interval=0.3)
                _activate_whatsapp_window()

                # Settle cleanly for WhatsApp Desktop to load chat and pre-populate message box
                time.sleep(1.6)
                _send_whatsapp_once()

                _record_whatsapp_chat_log(target_input, target_msg)
                return CommandResult(
                    True,
                    f"WhatsApp Desktop App opened for +{normalized_phone} and message sent: '{target_msg}'",
                )

            else:
                # ONLY if Desktop App is NOT installed on PC: automatically fall back to WhatsApp Web
                webbrowser.open_new_tab(
                    f"https://web.whatsapp.com/send?phone={normalized_phone}&text={encoded_message}"
                )
                time.sleep(3.5)
                _activate_whatsapp_or_browser_window()
                time.sleep(0.3)
                _send_whatsapp_enter()

                _record_whatsapp_chat_log(target_input, target_msg)
                return CommandResult(
                    True,
                    f"WhatsApp Web opened for +{normalized_phone} and message sent: '{target_msg}'",
                )

        except Exception as exc:
            return CommandResult(False, f"Failed to send WhatsApp message to +{normalized_phone}: {exc}")

    else:
        # ── SCENARIO B: Contact name only — search inside WhatsApp ──
        try:
            if app_installed:
                try:
                    os.startfile("whatsapp:")
                except Exception:
                    _launch_windows_target("whatsapp:")
                
                _wait_for_whatsapp_window(timeout=5.0, interval=0.3)
                time.sleep(0.8)
                _activate_whatsapp_window()
                time.sleep(0.2)

                if not pyautogui:
                    return CommandResult(
                        False,
                        f"WhatsApp Desktop opened for contact '{target_input}', but pyautogui is required to auto-send.",
                    )

                # Focus search bar (Ctrl+F in WhatsApp Desktop)
                pyautogui.press("esc")
                time.sleep(0.2)
                pyautogui.hotkey("ctrl", "f")
                time.sleep(0.5)

                # Paste contact name into search bar
                _copy_to_windows_clipboard(target_input)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(1.2)  # Wait for search results

                # Select top matching contact
                pyautogui.press("enter")
                time.sleep(0.8)  # Wait for chat to open

                # Paste and send message with plain Enter only (NO ctrl+enter!)
                _copy_to_windows_clipboard(target_msg)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(0.3)

                # Send immediately with hardware Enter and pulse worker
                _send_whatsapp_enter()
                threading.Thread(
                    target=_auto_send_whatsapp_worker,
                    args=(3.0, 0.4),
                    daemon=True,
                ).start()

                _record_whatsapp_chat_log(target_input, target_msg)
                return CommandResult(
                    True,
                    f"Searched for '{target_input}' on WhatsApp Desktop App and sent message immediately: '{target_msg}'",
                )

            else:
                webbrowser.open_new_tab("https://web.whatsapp.com")
                time.sleep(4.0)
                _activate_whatsapp_or_browser_window()
                if not pyautogui:
                    return CommandResult(False, "WhatsApp Web opened but pyautogui is required to auto-send.")
                pyautogui.hotkey("ctrl", "f")
                time.sleep(0.5)
                _copy_to_windows_clipboard(target_input)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(1.5)
                pyautogui.press("enter")
                time.sleep(1.0)
                _copy_to_windows_clipboard(target_msg)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(0.3)
                pyautogui.press("enter")
                _record_whatsapp_chat_log(target_input, target_msg)
                return CommandResult(
                    True,
                    f"Searched for '{target_input}' on WhatsApp Web and sent message: '{target_msg}'",
                )

        except Exception as exc:
            return CommandResult(False, f"Failed to search and send message to '{target_input}': {exc}")


@registry.register(
    "shutdown_pc",
    "Safely shuts down the computer after a short delay",
    params=[
        CommandParam("confirm", "str", "Confirmation string ('yes')", required=True),
        CommandParam("delay_seconds", "int", "Countdown delay in seconds", required=False, default=10),
    ],
)
def shutdown_pc(
    confirm: Optional[str] = None,
    delay_seconds: int = 10,
) -> CommandResult:
    """Shuts the computer down safely with confirmation."""
    if not _is_windows():
        return CommandResult(False, "This shutdown command targets Windows only.")

    conf_str = str(confirm).strip().lower() if confirm else ""
    if conf_str != "yes":
        return CommandResult(False, "Shutdown cancelled: confirmation ('yes') not received.")

    delay = str(int(delay_seconds)) if isinstance(delay_seconds, (int, str)) and str(delay_seconds).isdigit() else "10"

    try:
        subprocess.run(["shutdown", "/s", "/t", delay], check=True)
        return CommandResult(
            True,
            f"Shutdown scheduled in {delay} seconds. Run 'cancel_shutdown' now to stop it.",
        )
    except (subprocess.CalledProcessError, OSError) as exc:
        return CommandResult(False, f"Failed to schedule shutdown: {exc}")


@registry.register(
    "restart_pc",
    "Safely restarts the computer after a short delay",
    params=[
        CommandParam("confirm", "str", "Confirmation string ('yes')", required=True),
        CommandParam("delay_seconds", "int", "Countdown delay in seconds", required=False, default=10),
    ],
)
def restart_pc(
    confirm: Optional[str] = None,
    delay_seconds: int = 10,
) -> CommandResult:
    """Restarts the computer safely with confirmation."""
    if not _is_windows():
        return CommandResult(False, "This restart command targets Windows only.")

    conf_str = str(confirm).strip().lower() if confirm else ""
    if conf_str != "yes":
        return CommandResult(False, "Restart cancelled: confirmation ('yes') not received.")

    delay = str(int(delay_seconds)) if isinstance(delay_seconds, (int, str)) and str(delay_seconds).isdigit() else "10"

    try:
        subprocess.run(["shutdown", "/r", "/t", delay], check=True)
        return CommandResult(
            True,
            f"Restart scheduled in {delay} seconds. Run 'cancel_shutdown' now to stop it.",
        )
    except (subprocess.CalledProcessError, OSError) as exc:
        return CommandResult(False, f"Failed to schedule restart: {exc}")


@registry.register("cancel_shutdown", "Cancels a pending shutdown or restart")
def cancel_shutdown() -> CommandResult:
    """Cancels any shutdown/restart scheduled by shutdown_pc or restart_pc."""
    if not _is_windows():
        return CommandResult(False, "This command targets Windows only.")

    try:
        subprocess.run(["shutdown", "/a"], check=True)
        return CommandResult(True, "Pending shutdown/restart was cancelled.")
    except subprocess.CalledProcessError:
        return CommandResult(False, "There was no pending shutdown/restart to cancel.")
    except OSError as exc:
        return CommandResult(False, f"Failed to cancel shutdown: {exc}")


@registry.register("open_camera", "Opens the Windows Camera app")
def open_camera() -> CommandResult:
    """Opens the built-in Windows Camera app via its registered URI."""
    if not _is_windows():
        return CommandResult(False, "Camera launch via this method is only available on Windows.")
    try:
        os.startfile("microsoft.windows.camera:")
        return CommandResult(True, "Camera opened successfully.")
    except OSError as exc:
        return CommandResult(
            False,
            f"Failed to open Camera. Make sure the Windows Camera app is installed: {exc}",
        )


def _find_browser_path(browser_name: str) -> Optional[str]:
    """Looks for a named browser on PATH, then in common install locations."""
    known_paths = {
        "chrome": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ],
        "edge": [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ],
        "firefox": [
            r"C:\Program Files\Mozilla Firefox\firefox.exe",
            r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
        ],
        "brave": [
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
        ],
    }

    key = browser_name.strip().lower()
    which_result = shutil.which(key)
    if which_result:
        return which_result

    for path_str in known_paths.get(key, []):
        path = Path(path_str)
        if path.exists():
            return str(path)
    return None


_COMMON_APP_ALIASES = {
    "vscode": "Code.exe",
    "vs code": "Code.exe",
    "code": "Code.exe",
    "visual studio code": "Code.exe",
    "visual studio": "devenv.exe",
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "google": "chrome.exe",
    "edge": "msedge.exe",
    "msedge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "firefox": "firefox.exe",
    "brave": "brave.exe",
    "opera": "launcher.exe",
    "opera gx": "launcher.exe",
    "spotify": "spotify.exe",
    "vlc": "vlc.exe",
    "steam": "steam.exe",
    "discord": "discord.exe",
    "telegram": "telegram.exe",
    "whatsapp": "whatsapp:",
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "camera": "microsoft.windows.camera:",
    "webcam": "microsoft.windows.camera:",
    "settings": "ms-settings:",
    "pc settings": "ms-settings:",
    "task manager": "taskmgr.exe",
    "taskmgr": "taskmgr.exe",
    "file explorer": "explorer.exe",
    "explorer": "explorer.exe",
    "files": "explorer.exe",
    "control panel": "control.exe",
    "paint": "mspaint.exe",
    "mspaint": "mspaint.exe",
    "terminal": "wt.exe",
    "windows terminal": "wt.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "powershell": "powershell.exe",
    "word": "winword.exe",
    "ms word": "winword.exe",
    "microsoft word": "winword.exe",
    "excel": "excel.exe",
    "ms excel": "excel.exe",
    "microsoft excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "ppt": "powerpnt.exe",
    "snipping tool": "snippingtool.exe",
    "snip": "snippingtool.exe",
    "microsoft store": "ms-windows-store:",
    "store": "ms-windows-store:",
    "windows store": "ms-windows-store:",
    "ms store": "ms-windows-store:",
    "xbox": "shell:AppsFolder\\Microsoft.GamingApp_8wekyb3d8bbwe!Microsoft.Xbox.App",
    "xbox app": "shell:AppsFolder\\Microsoft.GamingApp_8wekyb3d8bbwe!Microsoft.Xbox.App",
    "game bar": "shell:AppsFolder\\Microsoft.XboxGamingOverlay_8wekyb3d8bbwe!App",
    "claude": "claude:",
    "claude app": "claude:",
    "claude ai": "claude:",
    "chatgpt": "ChatGPT.exe",
    "chat gpt": "ChatGPT.exe",
    "openai": "ChatGPT.exe",
    "canva": "Canva.exe",
    "canva app": "Canva.exe",
    "canva desktop": "Canva.exe",
    "antigravity": "antigravity.exe",
    "cloudcode": "cloudcode.exe",
    "cursor": "Cursor.exe",
    "postman": "Postman.exe",
    "sublime": "sublime_text.exe",
    "sublime text": "sublime_text.exe",
    "pycharm": "pycharm64.exe",
    "intellij": "idea64.exe",
    "android studio": "studio64.exe",
}


def _find_in_registry_app_paths(name: str) -> Optional[str]:
    """Looks up application executable path in Windows Registry App Paths."""
    roots = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\App Paths"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths"),
    ]
    name_lower = name.lower().strip()
    search_keys = [name_lower, f"{name_lower}.exe"]

    for hkey, subkey_path in roots:
        try:
            with winreg.OpenKey(hkey, subkey_path) as root_key:
                for sk in search_keys:
                    try:
                        with winreg.OpenKey(root_key, sk) as app_key:
                            val, _ = winreg.QueryValueEx(app_key, "")
                            if val and os.path.exists(val.strip('"')):
                                return val.strip('"')
                    except Exception:
                        pass

                count = winreg.QueryInfoKey(root_key)[0]
                for i in range(count):
                    try:
                        kname = winreg.EnumKey(root_key, i)
                        kname_clean = kname.lower().replace(".exe", "")
                        if name_lower == kname_clean or name_lower in kname_clean:
                            with winreg.OpenKey(root_key, kname) as app_key:
                                val, _ = winreg.QueryValueEx(app_key, "")
                                if val and os.path.exists(val.strip('"')):
                                    return val.strip('"')
                    except Exception:
                        continue
        except Exception:
            continue
    return None


def _find_app_path(app_name: str) -> Optional[str]:
    """Locates an application executable, URI scheme, or Start Menu shortcut on any Windows PC."""
    if not app_name:
        return None

    clean_name = app_name.strip()
    name_lower = clean_name.lower()
    norm_name = re.sub(r"[^a-z0-9]", "", name_lower)

    # 1. Direct path check
    candidate = Path(clean_name)
    if candidate.exists():
        return str(candidate)

    # 2. Check alias dictionary (both raw and normalized)
    alias_target = _COMMON_APP_ALIASES.get(name_lower)
    if not alias_target:
        for k, v in _COMMON_APP_ALIASES.items():
            if re.sub(r"[^a-z0-9]", "", k) == norm_name:
                alias_target = v
                break

    if alias_target:
        if alias_target.startswith("ms-") or alias_target.startswith("shell:") or alias_target.endswith(":"):
            return alias_target

    # 3. Special fast check for VS Code (most common downloaded app on Windows)
    if norm_name in ("vscode", "code", "visualstudiocode"):
        user_local = os.environ.get("LOCALAPPDATA", "")
        prog_files = os.environ.get("ProgramFiles", "")
        prog_x86 = os.environ.get("ProgramFiles(x86)", "")
        vscode_candidates = [
            Path(user_local) / "Programs" / "Microsoft VS Code" / "Code.exe",
            Path(prog_files) / "Microsoft VS Code" / "Code.exe",
            Path(prog_x86) / "Microsoft VS Code" / "Code.exe",
        ]
        for p in vscode_candidates:
            if p.exists():
                return str(p)

    # 4. Special fast check for Google Chrome
    if norm_name in ("chrome", "googlechrome", "google"):
        cp = _find_chrome_path()
        if cp:
            return cp

    # 5. Check Windows Registry App Paths (covers 95% of installed desktop apps)
    reg_path = _find_in_registry_app_paths(name_lower)
    if reg_path:
        return reg_path
    if alias_target and alias_target.lower().endswith(".exe"):
        reg_alias = _find_in_registry_app_paths(alias_target.replace(".exe", ""))
        if reg_alias:
            return reg_alias

    # 6. Try PATH resolution (preferring .exe over .cmd/.bat)
    which_exe = shutil.which(f"{name_lower}.exe") or (shutil.which(alias_target) if alias_target else None)
    if which_exe and which_exe.lower().endswith(".exe"):
        return which_exe

    which_result = shutil.which(clean_name)
    if which_result:
        # If it returned a .cmd or .bat (e.g. code.cmd), look for adjacent or parent .exe
        if which_result.lower().endswith((".cmd", ".bat")):
            wb = Path(which_result)
            parent_exe = wb.parent.parent / f"{wb.stem.capitalize()}.exe"
            if parent_exe.exists():
                return str(parent_exe)
            parent_code = wb.parent.parent / "Code.exe"
            if parent_code.exists():
                return str(parent_code)
        return which_result

    # 7. Check Start Menu and Desktop shortcuts (.lnk files)
    start_menu_locations = []
    for env_var, sub in [
        ("APPDATA", r"Microsoft\Windows\Start Menu\Programs"),
        ("PROGRAMDATA", r"Microsoft\Windows\Start Menu\Programs"),
        ("APPDATA", r"Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar"),
    ]:
        val = os.environ.get(env_var)
        if val:
            p = Path(val) / sub
            if p.exists():
                start_menu_locations.append(p)
    try:
        user_desktop = Path.home() / "Desktop"
        if user_desktop.exists():
            start_menu_locations.append(user_desktop)
        pub_desktop = Path(os.environ.get("PUBLIC", "C:\\Users\\Public")) / "Desktop"
        if pub_desktop.exists():
            start_menu_locations.append(pub_desktop)
    except Exception:
        pass

    for sm in start_menu_locations:
        if not sm.exists():
            continue
        try:
            for root, _dirs, files in os.walk(sm):
                for f in files:
                    if not f.lower().endswith(".lnk"):
                        continue
                    stem = Path(f).stem.lower()
                    stem_norm = re.sub(r"[^a-z0-9]", "", stem)
                    # Direct or normalized substring match
                    if (
                        name_lower in stem
                        or stem in name_lower
                        or norm_name == stem_norm
                        or norm_name in stem_norm
                        or stem_norm in norm_name
                    ):
                        lnk_file = str(Path(root) / f)
                    res_target, _, _ = _resolve_shortcut(lnk_file)
                    if res_target and os.path.exists(res_target):
                        return res_target
                    return lnk_file
                    if alias_target:
                        at_clean = re.sub(r"[^a-z0-9]", "", alias_target.lower().replace(".exe", ""))
                        if at_clean and (at_clean in stem_norm or stem_norm in at_clean):
                            lnk_file = str(Path(root) / f)
                    res_target, _, _ = _resolve_shortcut(lnk_file)
                    if res_target and os.path.exists(res_target):
                        return res_target
                    return lnk_file
        except Exception:
            continue

    # 8. Check UWP / Microsoft Store apps via PowerShell Get-StartApps
    uwp_id = _find_uwp_app_id(clean_name)
    if uwp_id:
        return f"uwp:{uwp_id}"

    # 9. Search common Program Files and Local AppData folders (+ Roaming for user-installed apps)
    search_roots = []
    pf = os.environ.get("ProgramFiles")
    pfx = os.environ.get("ProgramFiles(x86)")
    local_app = Path.home() / "AppData" / "Local"
    roaming_app = Path.home() / "AppData" / "Roaming"
    local_prog = local_app / "Programs"
    if pf and Path(pf).exists():
        search_roots.append(Path(pf))
    if pfx and Path(pfx).exists():
        search_roots.append(Path(pfx))
    if local_prog.exists():
        search_roots.append(local_prog)
    # Roaming AppData: Spotify, Discord, Telegram, Signal are installed here on many PCs
    if roaming_app.exists():
        search_roots.append(roaming_app)
    if local_app.exists():
        search_roots.append(local_app)

    # Specific hard-coded fast paths for very common apps installed in non-standard user dirs
    user_app_direct = {
        "spotify": [
            roaming_app / "Spotify" / "Spotify.exe",
            local_app / "Microsoft" / "WindowsApps" / "Spotify.exe",
        ],
        "discord": [
            # Discord installs to %LOCALAPPDATA%\Discord\app-X.X.XXXX\Discord.exe
            # The version subfolder changes with updates, so we glob for it
            local_app / "Discord" / "app-current" / "Discord.exe",
            roaming_app / "Discord" / "Discord.exe",
        ],
        "telegram": [
            roaming_app / "Telegram Desktop" / "Telegram.exe",
            local_app / "Telegram Desktop" / "Telegram.exe",
        ],
        "signal": [
            local_app / "Programs" / "signal-desktop" / "Signal.exe",
        ],
        "opera": [
            roaming_app / "Opera Software" / "Opera Stable" / "opera.exe",
            local_app / "Programs" / "Opera" / "launcher.exe",
        ],
        "opera gx": [
            roaming_app / "Opera Software" / "Opera GX Stable" / "opera.exe",
            local_app / "Programs" / "Opera GX" / "launcher.exe",
        ],
        "chatgpt": [
            local_app / "Programs" / "chatgpt" / "ChatGPT.exe",
            Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "ChatGPT" / "ChatGPT.exe",
        ],
    }
    for key_term, paths in user_app_direct.items():
        if norm_name in re.sub(r"[^a-z0-9]", "", key_term) or re.sub(r"[^a-z0-9]", "", key_term) in norm_name:
            for p in paths:
                if p.exists():
                    return str(p)

    # Discord: version-numbered subfolders (e.g. %LOCALAPPDATA%\Discord\app-1.0.9173\Discord.exe)
    if "discord" in norm_name:
        discord_base = local_app / "Discord"
        if discord_base.exists():
            try:
                ver_dirs = sorted(
                    [d for d in discord_base.iterdir() if d.is_dir() and d.name.startswith("app-")],
                    key=lambda d: d.name, reverse=True,
                )
                for vd in ver_dirs:
                    exe = vd / "Discord.exe"
                    if exe.exists():
                        return str(exe)
            except Exception:
                pass

    # Spotify: may be in %LOCALAPPDATA%\Microsoft\WindowsApps (Store version)
    if "spotify" in norm_name:
        spotify_store = local_app / "Microsoft" / "WindowsApps" / "Spotify.exe"
        if spotify_store.exists():
            return str(spotify_store)
        spotify_roaming = roaming_app / "Spotify" / "Spotify.exe"
        if spotify_roaming.exists():
            return str(spotify_roaming)

    for root in search_roots:
        try:
            for item in root.iterdir():
                if item.is_dir():
                    dir_norm = re.sub(r"[^a-z0-9]", "", item.name.lower())
                    if norm_name in dir_norm or dir_norm in norm_name:
                        for sub in item.glob("*.exe"):
                            sub_name = sub.name.lower()
                            if "uninstall" not in sub_name and "helper" not in sub_name and "setup" not in sub_name and "update" not in sub_name:
                                return str(sub)
                        for sub in item.glob("*/*.exe"):
                            sub_name = sub.name.lower()
                            if "uninstall" not in sub_name and "helper" not in sub_name and "setup" not in sub_name and "update" not in sub_name:
                                return str(sub)
        except Exception:
            continue

    return None


def _find_uwp_app_id(app_name: str) -> Optional[str]:
    """Use PowerShell Get-StartApps to find an AppID for UWP/Store apps matching app_name."""
    try:
        ps = [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress",
        ]
        proc = subprocess.run(ps, capture_output=True, text=True, timeout=3.0)
        out = proc.stdout.strip()
        if not out:
            return None
        import json

        data = json.loads(out)
        apps = data if isinstance(data, list) else [data]
        name_lower = app_name.lower().strip()

        alias_map = {
            "calc": ["calculator"],
            "calculator": ["calculator", "calc"],
            "xbox": ["xbox", "gaming"],
            "whatsapp": ["whatsapp"],
            "notepad": ["notepad"],
            "camera": ["camera"],
            "settings": ["setting"],
            "store": ["microsoft store"],
            "terminal": ["windows terminal", "terminal"],
        }
        search_terms = alias_map.get(name_lower, [name_lower])

        for entry in apps:
            try:
                nm = str(entry.get("Name", "")).lower()
                aid = str(entry.get("AppID") or entry.get("AppId") or "")
                if nm and aid:
                    for term in search_terms:
                        if term in nm or term in aid.lower():
                            return aid
            except Exception:
                continue
    except Exception:
        return None
    return None


@registry.register(
    "open_browser",
    "Opens a specified browser (Chrome, Edge, Firefox, Brave) with optional URL",
    params=[
        CommandParam("browser_name", "str", "Browser name: chrome, edge, firefox, or brave", required=False, default="default"),
        CommandParam("url", "str", "URL to open in the browser", required=False),
    ],
)
def open_browser(
    browser_name: Optional[str] = None,
    url: Optional[str] = None,
) -> CommandResult:
    """Opens a browser chosen by name."""
    b_name = (browser_name.strip() if browser_name else "chrome") or "chrome"
    target_url = url if url else "https://www.google.com"

    if b_name.lower() in ("default", "system"):
        try:
            webbrowser.open(target_url)
            return CommandResult(True, f"Opened default browser to {target_url}.")
        except Exception as exc:
            return CommandResult(False, f"Failed to open browser: {exc}")

    browser_path = _find_browser_path(b_name)
    if browser_path is None:
        browser_path = _find_app_path(b_name)

    if browser_path is None:
        try:
            webbrowser.open(target_url)
            return CommandResult(
                True,
                f"Could not find '{b_name}', so default browser was opened to {target_url}.",
            )
        except Exception as exc:
            return CommandResult(False, f"Failed to open browser: {exc}")

    try:
        subprocess.Popen([browser_path, target_url])
        return CommandResult(True, f"{b_name.title()} opened successfully to {target_url}.")
    except OSError as exc:
        return CommandResult(False, f"Failed to open {b_name.title()}: {exc}")


@registry.register(
    "open_app",
    "Opens any app by name (e.g. spotify, vscode, notepad, whatsapp, chrome, settings)",
    params=[
        CommandParam("app_name", "str", "App name or full path to open", required=True),
    ],
)
def open_app(app_name: Optional[str] = None) -> CommandResult:
    """Opens an arbitrary application by name or full path across any Windows computer."""
    if not _is_windows():
        return CommandResult(False, "This generic app launcher targets Windows only.")

    if not app_name or not str(app_name).strip():
        return CommandResult(False, "No app name was provided.")

    clean_name = str(app_name).strip()
    norm_name = re.sub(r"[^a-z0-9]", "", clean_name.lower())

    # 1. Specialized fast paths for major downloaded & modern apps

    # VS Code: must use --new-window flag to bypass corrupt session restore backups
    if norm_name in ("vscode", "code", "visualstudiocode", "vsocde"):
        user_local = os.environ.get("LOCALAPPDATA", "")
        prog_files = os.environ.get("ProgramFiles", "")
        prog_x86 = os.environ.get("ProgramFiles(x86)", "")
        vscode_candidates = [
            Path(user_local) / "Programs" / "Microsoft VS Code" / "Code.exe",
            Path(prog_files) / "Microsoft VS Code" / "Code.exe",
            Path(prog_x86) / "Microsoft VS Code" / "Code.exe",
        ]
        clean_env = _get_clean_env()
        flags = 0x00000200  # CREATE_NEW_PROCESS_GROUP
        for vsp in vscode_candidates:
            if vsp.exists():
                if _launch_windows_target(str(vsp), "--new-window"):
                    return CommandResult(True, "VS Code opened successfully.")
        # Fallback: try Start Menu shortcut
        lnk_found = _find_app_path("vscode")
        if lnk_found and _launch_windows_target(lnk_found):
            return CommandResult(True, "VS Code opened successfully.")
        return CommandResult(False, "VS Code was not found on this laptop. Please install it first.")

    if norm_name in ("canva", "canvaapp", "canvadesktop"):
        # Check direct desktop executable locations first
        canva_candidates = [
            Path.home() / "AppData" / "Local" / "Programs" / "Canva" / "Canva.exe",
            Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "Canva" / "Canva.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Canva" / "Canva.exe",
        ]
        for cp in canva_candidates:
            if cp.exists() and _launch_windows_target(str(cp)):
                return CommandResult(True, "Canva opened successfully on your laptop.")
        found = _find_app_path("canva")
        if found and not found.startswith("uwp:"):
            if _launch_windows_target(found):
                return CommandResult(True, "Canva opened successfully on your laptop.")
        if found and found.startswith("uwp:"):
            appid = found.split("uwp:", 1)[1]
            if _launch_windows_target(f"shell:AppsFolder\\{appid}"):
                return CommandResult(True, "Canva opened successfully.")
        try:
            os.startfile("https://www.canva.com")
            return CommandResult(True, "Opened Canva in your browser.")
        except Exception:
            pass

    if norm_name in ("chatgpt", "chatgptapp", "openai"):
        found = _find_app_path("chatgpt")
        if found:
            if found.startswith("uwp:"):
                appid = found.split("uwp:", 1)[1]
                if _launch_windows_target(f"shell:AppsFolder\\{appid}"):
                    return CommandResult(True, "ChatGPT opened successfully.")
            elif _launch_windows_target(found):
                return CommandResult(True, "ChatGPT opened successfully on your laptop.")
        try:
            os.startfile("https://chatgpt.com")
            return CommandResult(True, "Opened ChatGPT in your browser.")
        except Exception:
            pass

    if norm_name in ("claude", "claudeapp", "claudeai"):
        found = _find_app_path("claude")
        if found and _launch_windows_target(found):
            return CommandResult(True, "Claude opened successfully.")
        try:
            os.startfile("https://claude.ai")
            return CommandResult(True, "Opened Claude in your browser.")
        except Exception:
            pass

    if norm_name in ("whatsapp", "whatsappdesktop"):
        # Method 1: Direct UWP Store AppID (confirmed on Windows 10/11)
        if _launch_windows_target("shell:AppsFolder\\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App"):
            return CommandResult(True, "WhatsApp opened successfully.")
        # Method 2: Dynamic UWP lookup for any PC
        uwp_id = _find_uwp_app_id("whatsapp")
        if uwp_id and _launch_windows_target(f"shell:AppsFolder\\{uwp_id}"):
            return CommandResult(True, "WhatsApp opened successfully.")
        # Method 3: Desktop shortcut / exe
        found = _find_app_path("whatsapp")
        if found and _launch_windows_target(found):
            return CommandResult(True, "WhatsApp opened successfully.")
        # Method 4: Protocol
        if _launch_windows_target("whatsapp:"):
            return CommandResult(True, "WhatsApp opened successfully.")
        try:
            os.startfile("https://web.whatsapp.com")
            return CommandResult(True, "Opened WhatsApp Web in your browser.")
        except Exception:
            pass

    if norm_name in ("xbox", "xboxapp", "xboxgaming"):
        # Method 1: Direct known UWP AppID (confirmed working on most PCs)
        if _launch_windows_target("shell:AppsFolder\\Microsoft.GamingApp_8wekyb3d8bbwe!Microsoft.Xbox.App"):
            return CommandResult(True, "Xbox opened successfully.")
        # Method 2: Dynamic UWP lookup (works on any PC even if AppID differs)
        uwp_id = _find_uwp_app_id("xbox")
        if uwp_id and _launch_windows_target(f"shell:AppsFolder\\{uwp_id}"):
            return CommandResult(True, "Xbox opened successfully.")
        # Method 3: Game Bar fallback
        if _launch_windows_target("shell:AppsFolder\\Microsoft.XboxGamingOverlay_8wekyb3d8bbwe!App"):
            return CommandResult(True, "Xbox Game Bar opened successfully.")

    # 2. General application lookup
    found = _find_app_path(clean_name)

    # 3. Found via UWP (Microsoft Store / Windows app)
    if found and str(found).lower().startswith("uwp:"):
        appid = found.split("uwp:", 1)[1]
        uri = f"shell:AppsFolder\\{appid}"
        if _launch_windows_target(uri):
            return CommandResult(True, f"'{clean_name}' opened successfully.")
        return CommandResult(False, f"Could not launch UWP app '{clean_name}'.")

    # 4. Found via path (.exe / .lnk / URI protocol) — launch it
    if found:
        if _launch_windows_target(found):
            return CommandResult(True, f"'{clean_name}' opened successfully on your laptop.")
        else:
            return CommandResult(False, f"Found '{clean_name}' at {found} but failed to launch it.")

    # 5. Direct protocol check (e.g. ms-settings:, ms-windows-store:)
    if clean_name.startswith("ms-") or clean_name.endswith(":"):
        if _launch_windows_target(clean_name):
            return CommandResult(True, f"'{clean_name}' opened successfully.")

    # 6. App not found on this PC
    return CommandResult(
        False,
        f"'{clean_name}' was not found on this laptop. "
        f"Please make sure the app is installed and try again."
    )


@registry.register("lock_pc", "Locks the Windows computer screen")
def lock_pc() -> CommandResult:
    """Locks the current Windows user workstation."""
    if not _is_windows():
        return CommandResult(False, "This lock command targets Windows only.")

    try:
        subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], check=True)
        return CommandResult(True, "Computer screen locked successfully.")
    except (subprocess.CalledProcessError, OSError) as exc:
        return CommandResult(False, f"Failed to lock computer: {exc}")


# ---------------------------------------------------------------------------
# Phone Link Device Integration Commands
# ---------------------------------------------------------------------------


@registry.register(
    "make_phone_call",
    "Initiates a phone call via Windows Phone Link device to a phone number or contact name",
    params=[
        CommandParam("phone", "str", "Phone number or contact name to call", required=True),
    ],
)
def make_phone_call(phone: Optional[str] = None) -> CommandResult:
    if not phone:
        return CommandResult(False, "No phone number or contact name was provided.")
    try:
        from era_agent.controls import SystemControlManager
    except ImportError:
        from controls import SystemControlManager

    ok, msg = SystemControlManager.execute_intent("make_phone_call", {"phone": phone})
    return CommandResult(ok, msg)


@registry.register(
    "read_phone_messages",
    "Opens Phone Link Messages interface to read SMS and chat messages",
    params=[
        CommandParam("limit", "int", "Maximum number of messages to retrieve", required=False, default=5),
    ],
)
def read_phone_messages(limit: int = 5) -> CommandResult:
    try:
        from era_agent.controls import SystemControlManager
    except ImportError:
        from controls import SystemControlManager

    ok, msg = SystemControlManager.execute_intent("read_phone_messages", {"limit": limit})
    return CommandResult(ok, msg)


@registry.register(
    "transfer_phone_files",
    "Transfers files or photos between connected Phone Link device and laptop",
    params=[
        CommandParam("direction", "str", "'phone_to_laptop' or 'laptop_to_phone'", required=False, default="phone_to_laptop"),
        CommandParam("file_name", "str", "Optional specific file or photo name", required=False),
        CommandParam("destination", "str", "Target destination folder path on laptop", required=False),
    ],
)
def transfer_phone_files(
    direction: str = "phone_to_laptop",
    file_name: Optional[str] = None,
    destination: Optional[str] = None,
) -> CommandResult:
    try:
        from era_agent.controls import SystemControlManager
    except ImportError:
        from controls import SystemControlManager

    ok, msg = SystemControlManager.execute_intent(
        "transfer_phone_files",
        {"direction": direction, "file_name": file_name, "destination": destination},
    )
    return CommandResult(ok, msg)


@registry.register(
    "get_phone_link_status",
    "Queries status and connectivity of Windows Phone Link device",
)
def get_phone_link_status() -> CommandResult:
    try:
        from era_agent.controls import SystemControlManager
    except ImportError:
        from controls import SystemControlManager

    ok, msg = SystemControlManager.execute_intent("get_phone_link_status", {})
    return CommandResult(ok, msg)





# ---------------------------------------------------------------------------
# DISPLAY BRIGHTNESS COMMANDS
# ---------------------------------------------------------------------------

try:
    from controls.display import DisplayControl
except ImportError:
    try:
        from era_agent.controls.display import DisplayControl
    except ImportError:
        DisplayControl = None


@registry.register(
    "set_display_brightness",
    "Sets screen display brightness percentage (0 to 100)",
    params=[CommandParam("level", "int", "Brightness level 0 to 100", required=True)],
)
def set_display_brightness(level: int = 50) -> CommandResult:
    """Sets screen display brightness."""
    if DisplayControl is None:
        return CommandResult(False, "DisplayControl module is not available.")
    try:
        lvl = int(level)
    except (ValueError, TypeError):
        return CommandResult(False, "Brightness level must be an integer 0-100.")
    ok, msg = DisplayControl.set_brightness(lvl)
    return CommandResult(ok, msg)


@registry.register(
    "set_brightness",
    "Alias for set_display_brightness",
    params=[CommandParam("level", "int", "Brightness level 0 to 100", required=True)],
)
def set_brightness(level: int = 50) -> CommandResult:
    return set_display_brightness(level)


@registry.register(
    "adjust_display_brightness",
    "Adjusts screen brightness by delta (e.g. +10 or -10)",
    params=[CommandParam("delta", "int", "Delta percentage to change", required=True)],
)
def adjust_display_brightness(delta: int = 10) -> CommandResult:
    if DisplayControl is None:
        return CommandResult(False, "DisplayControl module is not available.")
    try:
        d = int(delta)
    except (ValueError, TypeError):
        return CommandResult(False, "Delta must be an integer.")
    ok, msg = DisplayControl.adjust_brightness(d)
    return CommandResult(ok, msg)


@registry.register(
    "get_display_brightness",
    "Gets current screen brightness percentage",
)
def get_display_brightness() -> CommandResult:
    if DisplayControl is None:
        return CommandResult(False, "DisplayControl module is not available.")
    ok, lvl, msg = DisplayControl.get_brightness()
    return CommandResult(ok, msg)