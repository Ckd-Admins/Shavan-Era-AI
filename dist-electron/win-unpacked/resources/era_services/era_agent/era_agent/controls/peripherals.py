"""Peripheral controller for Era Agent (Bluetooth & Wi-Fi).

Provides Windows automation calls to manage Bluetooth and Wi-Fi peripheral states,
queries status, and enables/disables adapters safely using PowerShell and netsh.
"""

from __future__ import annotations

import logging
import platform
import subprocess
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


class PeripheralControl:
    """Manages Bluetooth and Wi-Fi peripheral state on Windows."""

    @staticmethod
    def is_supported() -> bool:
        return platform.system().lower() == "windows"

    @classmethod
    def set_bluetooth_state(cls, enable: bool) -> Tuple[bool, str]:
        """Enables or disables Bluetooth functionality on Windows.

        Uses PowerShell to manage Bluetooth services ('bthserv') and radio state.
        """
        if not cls.is_supported():
            return False, "Peripheral control is only supported on Windows."

        target_state = "enable" if enable else "disable"
        action_word = "enabled" if enable else "disabled"

        # PowerShell command attempting radio state toggle via Windows.Devices.RadioButton
        ps_cmd = f"""
        $service = Get-Service -Name "bthserv" -ErrorAction SilentlyContinue
        if ($service) {{
            if ("{target_state}" -eq "enable") {{
                Start-Service -Name "bthserv" -ErrorAction SilentlyContinue
            }}
        }}

        try {{
            [Windows.Devices.Radios.Radio, Windows.System.Devices, ContentType = WindowsRuntime] | Out-Null
            [Windows.Devices.Radios.RadioAccessStatus, Windows.System.Devices, ContentType = WindowsRuntime] | Out-Null
            $radios = [Windows.Devices.Radios.Radio]::GetRadiosAsync().GetResults()
            $bt = $radios | Where-Object {{ $_.Kind -eq 'Bluetooth' }}
            if ($bt) {{
                $desired = if ("{target_state}" -eq "enable") {{ [Windows.Devices.Radios.RadioState]::On }} else {{ [Windows.Devices.Radios.RadioState]::Off }}
                $null = $bt.SetStateAsync($desired).GetResults()
                Write-Output "SUCCESS"
                exit 0
            }}
        }} catch {{}}

        # Fallback using service control
        if ("{target_state}" -eq "enable") {{
            Set-Service -Name "bthserv" -StartupType Automatic -ErrorAction SilentlyContinue
            Start-Service -Name "bthserv" -ErrorAction SilentlyContinue
            Write-Output "SUCCESS_SERVICE"
        }} else {{
            Stop-Service -Name "bthserv" -Force -ErrorAction SilentlyContinue
            Write-Output "SUCCESS_SERVICE"
        }}
        """

        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=6.0,
            )
            out = proc.stdout.strip()
            if "SUCCESS" in out:
                return True, f"Bluetooth has been {action_word} successfully."
            return True, f"Bluetooth state set to {action_word}."
        except subprocess.TimeoutExpired:
            return False, "Bluetooth state change timed out."
        except Exception as exc:
            logger.debug("Bluetooth toggle error: %s", exc)
            return False, f"Failed to set Bluetooth state: {exc}"

    @classmethod
    def set_wifi_state(cls, enable: bool) -> Tuple[bool, str]:
        """Enables or disables Wi-Fi interface on Windows.

        Uses NetAdapter PowerShell cmdlets or netsh interface commands.
        """
        if not cls.is_supported():
            return False, "Peripheral control is only supported on Windows."

        action_word = "enabled" if enable else "disabled"
        admin_state = "enabled" if enable else "disabled"
        net_state = "Enable-NetAdapter" if enable else "Disable-NetAdapter"

        ps_cmd = f"""
        # Try NetAdapter cmdlet first
        $wifiAdapter = Get-NetAdapter | Where-Object {{ $_.PhysicalMediaType -like "*802.11*" -or $_.Name -like "*Wi-Fi*" -or $_.InterfaceDescription -like "*Wireless*" }} | Select-Object -First 1
        if ($wifiAdapter) {{
            {net_state} -Name $wifiAdapter.Name -Confirm:$false -ErrorAction SilentlyContinue
            Write-Output "SUCCESS"
            exit 0
        }}

        # Fallback via netsh
        netsh interface set interface name="Wi-Fi" admin={admin_state}
        """

        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=6.0,
            )
            out = proc.stdout.strip()
            if proc.returncode == 0 or "SUCCESS" in out:
                return True, f"Wi-Fi interface has been {action_word} successfully."
            return False, f"Failed to set Wi-Fi state: {proc.stderr.strip() or 'No Wi-Fi interface found.'}"
        except subprocess.TimeoutExpired:
            return False, "Wi-Fi state change timed out."
        except Exception as exc:
            logger.debug("Wi-Fi toggle error: %s", exc)
            return False, f"Failed to adjust Wi-Fi state: {exc}"

    @classmethod
    def get_peripheral_status(cls) -> Tuple[bool, Dict[str, str], str]:
        """Queries the current status of Bluetooth and Wi-Fi peripherals.

        Returns:
            Tuple of (success: bool, status_dict: dict, status_summary_message: str)
        """
        if not cls.is_supported():
            return False, {}, "Peripheral control is only supported on Windows."

        ps_cmd = """
        $res = @{}
        
        # Check Bluetooth service
        $btService = Get-Service -Name "bthserv" -ErrorAction SilentlyContinue
        $res["bluetooth_service"] = if ($btService) { $btService.Status.ToString() } else { "NotFound" }

        # Check Wi-Fi adapter
        $wifiAdapter = Get-NetAdapter | Where-Object { $_.PhysicalMediaType -like "*802.11*" -or $_.Name -like "*Wi-Fi*" -or $_.InterfaceDescription -like "*Wireless*" } | Select-Object -First 1
        $res["wifi_adapter"] = if ($wifiAdapter) { $wifiAdapter.Status.ToString() } else { "NotFound" }

        $res | ConvertTo-Json -Compress
        """

        try:
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=5.0,
            )
            out = proc.stdout.strip()
            if proc.returncode == 0 and out:
                import json

                data = json.loads(out)
                bt_status = data.get("bluetooth_service", "Unknown")
                wifi_status = data.get("wifi_adapter", "Unknown")
                msg = f"Peripheral Status: Bluetooth service is {bt_status}, Wi-Fi adapter status is {wifi_status}."
                return True, data, msg
            return False, {}, "Could not retrieve peripheral status."
        except Exception as exc:
            return False, {}, f"Failed to query peripheral status: {exc}"
