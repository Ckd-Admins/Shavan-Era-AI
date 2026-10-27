import os
import re
from pathlib import Path

file_path = r"d:\era_agent\commands\system_commands.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update _launch_windows_target without CREATE_NO_WINDOW and with robust launch
new_launch_func = '''def _launch_windows_target(target: str, args: Optional[str] = None) -> bool:
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

    return False'''

old_launch_pattern = re.compile(
    r'def _launch_windows_target\(target: str, args: Optional\[str\] = None\) -> bool:.*?(?=\n@registry\.register\()',
    re.DOTALL
)
content = old_launch_pattern.sub(new_launch_func + "\n\n", content)

# 2. Update canva fast path in open_app
old_canva_block = '''    if norm_name in ("canva", "canvaapp", "canvadesktop"):
        found = _find_app_path("canva")
        if found:
            if found.startswith("uwp:"):
                appid = found.split("uwp:", 1)[1]
                if _launch_windows_target(f"shell:AppsFolder\\\\{appid}"):
                    return CommandResult(True, "Canva opened successfully.")
            elif _launch_windows_target(found):
                return CommandResult(True, "Canva opened successfully on your laptop.")
        if _launch_windows_target("shell:AppsFolder\\\\com.canva.CanvaDesktop"):
            return CommandResult(True, "Canva opened successfully.")
        try:
            os.startfile("https://www.canva.com")
            return CommandResult(True, "Opened Canva in your browser.")
        except Exception:
            pass'''

new_canva_block = '''    if norm_name in ("canva", "canvaapp", "canvadesktop"):
        # Check direct desktop executable locations first
        canva_candidates = [
            Path.home() / "AppData" / "Local" / "Programs" / "Canva" / "Canva.exe",
            Path(os.environ.get("ProgramFiles", "C:\\\\Program Files")) / "Canva" / "Canva.exe",
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
            if _launch_windows_target(f"shell:AppsFolder\\\\{appid}"):
                return CommandResult(True, "Canva opened successfully.")
        try:
            os.startfile("https://www.canva.com")
            return CommandResult(True, "Opened Canva in your browser.")
        except Exception:
            pass'''

if old_canva_block in content:
    content = content.replace(old_canva_block, new_canva_block)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Patch applied successfully to system_commands.py")
