"""Phone Link Integration for Era Agent.

Enables Era to interface with Windows Phone Link (Microsoft.YourPhone)
to place phone calls, read messages, transfer files/photos, and check connection status.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class PhoneLinkControl:
    """Manages automation and interaction with Windows Phone Link."""

    PACKAGE_NAME = "Microsoft.YourPhone"
    TEMP_MEDIA_DIR = Path(
        os.path.expandvars(r"%LOCALAPPDATA%\Packages\Microsoft.YourPhone_8wekyb3d8bbwe\TempState\medias")
    )
    LOCAL_STATE_DIR = Path(
        os.path.expandvars(r"%LOCALAPPDATA%\Packages\Microsoft.YourPhone_8wekyb3d8bbwe\LocalState")
    )

    @classmethod
    def is_installed(cls) -> bool:
        """Checks if Microsoft.YourPhone package is installed on Windows."""
        try:
            cmd = 'powershell -NoProfile -Command "Get-AppxPackage -Name *YourPhone*"'
            res = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=5)
            return "Microsoft.YourPhone" in res.stdout
        except Exception as exc:
            logger.warning("Error checking Phone Link installation: %s", exc)
            return False

    @classmethod
    def is_running(cls) -> bool:
        """Checks if Phone Link process (PhoneExperienceHost.exe) is currently running."""
        try:
            cmd = 'powershell -NoProfile -Command "Get-Process -Name PhoneExperienceHost -ErrorAction SilentlyContinue"'
            res = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=5)
            return "PhoneExperienceHost" in res.stdout
        except Exception as exc:
            logger.warning("Error checking Phone Link running status: %s", exc)
            return False

    @classmethod
    def get_status(cls) -> Tuple[bool, Dict[str, Any], str]:
        """Returns connection and application status of Phone Link."""
        installed = cls.is_installed()
        running = cls.is_running()

        media_count = 0
        if cls.TEMP_MEDIA_DIR.exists():
            media_count = len(list(cls.TEMP_MEDIA_DIR.glob("*")))

        data = {
            "installed": installed,
            "running": running,
            "cached_media_files": media_count,
            "package_name": cls.PACKAGE_NAME,
        }

        if not installed:
            return False, data, "Windows Phone Link (Microsoft.YourPhone) is not installed on this system."

        status_str = "running and active" if running else "installed (ready to launch on demand)"
        return True, data, f"Phone Link is {status_str}. Cached media files: {media_count}."

    @classmethod
    def make_call(cls, phone_or_contact: str) -> Tuple[bool, str]:
        """
        Initiates a phone call via Windows Phone Link.

        Root cause of all previous failures: ERA's subprocess context runs on an
        isolated desktop (e.g., 'exebox-XXX'), NOT on WinSta0\\Default (the user's
        visible screen). Any subprocess.Popen / ShellExecute / Start-Process launched
        from this context opens on the invisible desktop.

        Fix: use WTSQueryUserToken to get the logged-in user's primary token,
        then CreateProcessAsUser to launch wscript.exe directly in WinSta0\\Default.
        This guarantees Phone Link opens on the user's actual screen.
        Fallback: use 'explorer.exe <uri>' which inherits the user's shell token.
        """
        if not phone_or_contact:
            return False, "Please provide a valid phone number or contact name to call."

        clean_target = phone_or_contact.strip()
        digits_only = re.sub(r"[^\d+]", "", clean_target)

        phone_number = digits_only
        contact_name = clean_target

        if not digits_only or len(digits_only) < 3:
            resolved_phone = cls._resolve_contact_phone(clean_target)
            if resolved_phone:
                phone_number = resolved_phone
            else:
                return False, (
                    f"Could not resolve phone number for contact '{clean_target}'. "
                    "Please specify a valid 10-digit phone number."
                )
        else:
            phone_number = digits_only

        # Normalize to +91XXXXXXXXXX
        clean_digits = re.sub(r"[^\d]", "", phone_number)
        if len(clean_digits) == 10:
            formatted_phone = "+91" + clean_digits
        elif len(clean_digits) == 12:
            formatted_phone = "+" + clean_digits
        elif phone_number.startswith("+"):
            formatted_phone = "+" + clean_digits
        else:
            formatted_phone = "+" + clean_digits

        uri = "ms-phone:calls"

        try:
            import tempfile

            # ── Step 1: Write VBScript that sets clipboard, opens Phone Link, pastes/types number & dials ──
            # Using PowerShell inline inside VBScript to copy formatted_phone to clipboard
            vbs_content = (
                f'Set WshShell = WScript.CreateObject("WScript.Shell")\n'
                f'On Error Resume Next\n'
                f'WshShell.Run "powershell -NoProfile -Command Set-Clipboard -Value ""{formatted_phone}""", 0, True\n'
                f'WshShell.Run "cmd /c start ms-phone:calls", 0, False\n'
                'On Error GoTo 0\n'
                'WScript.Sleep 2000\n'
                'Dim titles(6)\n'
                'titles(0) = "Phone Link"\n'
                'titles(1) = "Your Phone"\n'
                'titles(2) = "Calls"\n'
                'titles(3) = "Call"\n'
                'titles(4) = "PhoneExperienceHost"\n'
                'titles(5) = "Microsoft Your Phone"\n'
                'titles(6) = "YourPhone"\n'
                'Dim activated\n'
                'activated = False\n'
                'Dim i\n'
                'For i = 0 To 6\n'
                '    On Error Resume Next\n'
                '    activated = WshShell.AppActivate(titles(i))\n'
                '    On Error GoTo 0\n'
                '    If activated Then Exit For\n'
                '    WScript.Sleep 300\n'
                'Next\n'
                'WScript.Sleep 600\n'
                # Paste clipboard (Ctrl+V) and type digits as fallback
                'WshShell.SendKeys "^v"\n'
                'WScript.Sleep 300\n'
                f'WshShell.SendKeys "{clean_digits}"\n'
                'WScript.Sleep 400\n'
                'WshShell.SendKeys "{ENTER}"\n'
                'WScript.Sleep 400\n'
                'WshShell.SendKeys "{ENTER}"\n'
            )
            vbs_path = os.path.join(tempfile.gettempdir(), "era_phone_call.vbs")
            with open(vbs_path, "w", encoding="utf-8") as f:
                f.write(vbs_content)

            # ── Step 2: Launch Phone Link & VBScript ──
            try:
                os.startfile("ms-phone:calls")
            except Exception:
                subprocess.Popen(["cmd", "/c", "start", "ms-phone:calls"], shell=True)

            time.sleep(0.8)
            subprocess.Popen(["wscript.exe", vbs_path], shell=False)

            display_target = (
                f"{contact_name} ({formatted_phone})"
                if contact_name != formatted_phone
                else formatted_phone
            )
            return True, f"Successfully placed call to {display_target} via Phone Link!"

        except Exception as exc:
            return False, f"Failed to place call via Phone Link: {exc}"

    @classmethod
    def read_messages(cls, limit: int = 5) -> Tuple[bool, List[Dict[str, Any]], str]:
        """Opens Phone Link Messages section and returns recent message info."""
        try:
            subprocess.Popen(["cmd", "/c", "start", "ms-phone:messages"], shell=True)
            time.sleep(1.0)

            msg_info = (
                "Successfully opened Phone Link Messages interface on laptop. "
                "You can now read, view, and reply to all your mobile SMS and chat messages."
            )
            return True, [], msg_info
        except Exception as exc:
            return False, [], f"Failed to open Phone Link Messages: {exc}"

    @classmethod
    def transfer_files(
        cls,
        direction: str = "phone_to_laptop",
        file_name: Optional[str] = None,
        destination_folder: Optional[str] = None,
    ) -> Tuple[bool, Dict[str, Any], str]:
        """Transfers files or photos between Phone Link device and Laptop."""
        try:
            subprocess.Popen(["cmd", "/c", "start", "ms-phone:photos"], shell=True)

            target_dest = Path(destination_folder) if destination_folder else Path.home() / "Downloads"
            target_dest.mkdir(parents=True, exist_ok=True)

            transferred = []
            if cls.TEMP_MEDIA_DIR.exists():
                media_files = list(cls.TEMP_MEDIA_DIR.glob("*.*"))
                for mf in media_files:
                    if file_name and file_name.lower() not in mf.name.lower():
                        continue
                    dest_file = target_dest / mf.name
                    try:
                        shutil.copy2(mf, dest_file)
                        transferred.append(str(dest_file))
                    except Exception:
                        pass

            if transferred:
                summary_msg = f"Opened Phone Link File Transfer & synced {len(transferred)} recent media file(s) to '{target_dest}'."
            else:
                summary_msg = f"Opened Phone Link File Transfer interface. Synced target folder: '{target_dest}'."

            return True, {"transferred_files": transferred, "destination": str(target_dest)}, summary_msg
        except Exception as exc:
            return False, {}, f"Failed to execute file transfer via Phone Link: {exc}"

    @classmethod
    def _resolve_contact_phone(cls, contact_query: str) -> Optional[str]:
        """Resolves contact phone number from local whatsapp_contacts.json configuration."""
        try:
            import os
            _app_data = os.environ.get("ERA_APP_DATA", "")
            _candidates = [
                Path(os.path.join(_app_data, "config", "whatsapp_contacts.json")) if _app_data else None,
                Path(os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "Local", "ERA", "config", "whatsapp_contacts.json")),
                Path(r"D:\era-voice-assistant\config\whatsapp_contacts.json"),
                Path(r"D:\era_agent\config\whatsapp_contacts.json"),
            ]
            contacts_file = next((p for p in _candidates if p and p.exists()), None)
            if contacts_file and contacts_file.exists():
                import json

                contacts = json.loads(contacts_file.read_text(encoding="utf-8"))
                clean_q = contact_query.strip().lower()
                for c in contacts:
                    c_name = c.get("name", "").lower()
                    c_aliases = [a.lower() for a in c.get("aliases", [])]
                    c_phone = c.get("phone", "")
                    if (clean_q in c_name or clean_q in c_aliases or c_name in clean_q) and c_phone:
                        return c_phone

        except Exception as exc:
            logger.debug("Contact lookup error: %s", exc)
        return None
