import os
import re
from pathlib import Path

file_path = r"d:\era_agent\commands\system_commands.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add _resolve_shortcut if not present
if "_resolve_shortcut" not in content:
    resolver_code = '''def _resolve_shortcut(lnk_path: str):
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


def _launch_windows_target(target: str, args: Optional[str] = None) -> bool:'''
    content = content.replace("def _launch_windows_target(target: str, args: Optional[str] = None) -> bool:", resolver_code, 1)

# 2. Update _launch_windows_target implementation to resolve .lnk and direct launch with cwd
old_launch_pattern = re.compile(
    r'def _launch_windows_target\(target: str, args: Optional\[str\] = None\) -> bool:.*?(?=\n@registry\.register\()',
    re.DOTALL
)

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
    flags = 0x00000200 | 0x08000000  # CREATE_NEW_PROCESS_GROUP + CREATE_NO_WINDOW
    working_dir = None

    # RESOLVE SHORTCUTS (.lnk)
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
            subprocess.Popen(
                cmd_args,
                cwd=cwd,
                env=clean_env,
                creationflags=flags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
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
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
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
        if args_str:
            a = args_str.replace("'", "''")
            ps_cmd = f"Start-Process -FilePath '{t}' -ArgumentList '{a}' -WorkingDirectory '{working_dir or str(Path(clean_target).parent)}' -ErrorAction SilentlyContinue"
        else:
            ps_cmd = f"Start-Process -FilePath '{t}' -WorkingDirectory '{working_dir or str(Path(clean_target).parent)}' -ErrorAction SilentlyContinue"

        subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", ps_cmd],
            creationflags=flags,
            env=clean_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
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
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
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
'''

content = old_launch_pattern.sub(new_launch_func + "\n\n", content)

# 3. Enhance _find_app_path to resolve shortcuts before returning
old_lnk_return = 'return str(Path(root) / f)'
new_lnk_return = '''lnk_file = str(Path(root) / f)
                    res_target, _, _ = _resolve_shortcut(lnk_file)
                    if res_target and os.path.exists(res_target):
                        return res_target
                    return lnk_file'''

content = content.replace(old_lnk_return, new_lnk_return)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Successfully updated system_commands.py")
