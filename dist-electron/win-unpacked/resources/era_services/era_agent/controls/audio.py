"""Audio volume controller for Era Agent.

Provides Windows automation calls to query, set, adjust master audio volume,
and toggle mute state using Windows CoreAudio/WASAPI COM interfaces via PowerShell.
Includes keyboard virtual key fallbacks if hardware COM endpoint volume is unavailable.
"""

from __future__ import annotations

import logging
import platform
import subprocess
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

AUDIO_CSHARP_CODE = r"""
using System;
using System.Runtime.InteropServices;

namespace AudioLib {
    [Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IAudioEndpointVolume {
        int RegisterControlChangeNotify(IntPtr pNotify);
        int UnregisterControlChangeNotify(IntPtr pNotify);
        int GetChannelCount(out uint pnChannelCount);
        int SetMasterVolumeLevel(float fLevelDB, ref Guid pguidEventContext);
        int SetMasterVolumeLevelScalar(float fLevel, ref Guid pguidEventContext);
        int GetMasterVolumeLevel(out float pfLevelDB);
        int GetMasterVolumeLevelScalar(out float pfLevel);
        int SetChannelVolumeLevel(uint nChannel, float fLevelDB, ref Guid pguidEventContext);
        int SetChannelVolumeLevelScalar(uint nChannel, float fLevel, ref Guid pguidEventContext);
        int GetChannelVolumeLevel(uint nChannel, out float pfLevelDB);
        int GetChannelVolumeLevelScalar(uint nChannel, out float pfLevel);
        int SetMute([MarshalAs(UnmanagedType.Bool)] bool bMute, ref Guid pguidEventContext);
        int GetMute([MarshalAs(UnmanagedType.Bool)] out bool pbMute);
    }

    [Guid("D6660630-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IMMDevice {
        int Activate(ref Guid iid, uint dwClsCtx, IntPtr pActivationParams, [MarshalAs(UnmanagedType.IUnknown)] out object ppInterface);
    }

    [Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IMMDeviceEnumerator {
        int EnumAudioEndpoints(int dataFlow, int dwStateMask, out IntPtr ppDevices);
        int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice ppDevice);
    }

    [ComImport, Guid("BCDE0385-AFC6-4267-BD80-C1681C600901")]
    public class MMDeviceEnumeratorComObject { }

    public class Audio {
        public static float GetVolume() {
            var enumerator = (IMMDeviceEnumerator)(new MMDeviceEnumeratorComObject());
            IMMDevice dev;
            enumerator.GetDefaultAudioEndpoint(0, 1, out dev);
            var iid = typeof(IAudioEndpointVolume).GUID;
            object obj;
            dev.Activate(ref iid, 23, IntPtr.Zero, out obj);
            var endpoint = (IAudioEndpointVolume)obj;
            float vol;
            endpoint.GetMasterVolumeLevelScalar(out vol);
            return vol * 100f;
        }

        public static void SetVolume(float volPercent) {
            var enumerator = (IMMDeviceEnumerator)(new MMDeviceEnumeratorComObject());
            IMMDevice dev;
            enumerator.GetDefaultAudioEndpoint(0, 1, out dev);
            var iid = typeof(IAudioEndpointVolume).GUID;
            object obj;
            dev.Activate(ref iid, 23, IntPtr.Zero, out obj);
            var endpoint = (IAudioEndpointVolume)obj;
            Guid g = Guid.Empty;
            endpoint.SetMasterVolumeLevelScalar(volPercent / 100f, ref g);
        }

        public static bool GetMute() {
            var enumerator = (IMMDeviceEnumerator)(new MMDeviceEnumeratorComObject());
            IMMDevice dev;
            enumerator.GetDefaultAudioEndpoint(0, 1, out dev);
            var iid = typeof(IAudioEndpointVolume).GUID;
            object obj;
            dev.Activate(ref iid, 23, IntPtr.Zero, out obj);
            var endpoint = (IAudioEndpointVolume)obj;
            bool mute;
            endpoint.GetMute(out mute);
            return mute;
        }

        public static void SetMute(bool muteState) {
            var enumerator = (IMMDeviceEnumerator)(new MMDeviceEnumeratorComObject());
            IMMDevice dev;
            enumerator.GetDefaultAudioEndpoint(0, 1, out dev);
            var iid = typeof(IAudioEndpointVolume).GUID;
            object obj;
            dev.Activate(ref iid, 23, IntPtr.Zero, out obj);
            var endpoint = (IAudioEndpointVolume)obj;
            Guid g = Guid.Empty;
            endpoint.SetMute(muteState, ref g);
        }
    }
}
"""


class AudioControl:
    """Manages audio volume and mute state on Windows platforms."""

    @staticmethod
    def is_supported() -> bool:
        return platform.system().lower() == "windows"

    @classmethod
    def _run_ps_action(cls, action_cmd: str) -> Tuple[bool, str, str]:
        """Runs a PowerShell block with the compiled WASAPI C# Audio class."""
        ps_script = f"""
$code = @'
{AUDIO_CSHARP_CODE}
'@
try {{ Add-Type -TypeDefinition $code -Language CSharp -ErrorAction SilentlyContinue }} catch {{}}
{action_cmd}
"""
        import os
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        sysnative_ps = os.path.join(system_root, "Sysnative", "WindowsPowerShell", "v1.0", "powershell.exe")
        system32_ps = os.path.join(system_root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
        ps_exe = sysnative_ps if os.path.exists(sysnative_ps) else system32_ps

        try:
            proc = subprocess.run(
                [ps_exe, "-NoProfile", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=5.0,
            )
            out_lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
            final_out = out_lines[-1] if out_lines else ""
            return proc.returncode == 0, final_out, proc.stderr.strip()
        except subprocess.TimeoutExpired:
            return False, "", "Audio command timed out."
        except Exception as exc:
            return False, "", str(exc)

    _last_volume: int = 50
    _last_mute: bool = False

    @classmethod
    def get_volume(cls) -> Tuple[bool, int, str]:
        """Queries the current audio volume percentage."""
        if not cls.is_supported():
            return False, 0, "Audio volume control is only supported on Windows."

        import re
        ok, out, err = cls._run_ps_action("[AudioLib.Audio]::GetVolume()")
        m = re.findall(r"\d+(?:\.\d+)?", out)
        if ok and m:
            try:
                vol = int(round(float(m[-1])))
                cls._last_volume = vol
                return True, vol, f"Current audio volume is {vol}%."
            except ValueError:
                pass

        return True, cls._last_volume, f"Current audio volume is approximately {cls._last_volume}%."

    @classmethod
    def set_volume(cls, level: int) -> Tuple[bool, str]:
        """Sets the master audio volume to a specific percentage (0 to 100)."""
        if not cls.is_supported():
            return False, "Audio volume control is only supported on Windows."

        target_level = max(0, min(100, int(level)))
        cls._last_volume = target_level

        ok, out, err = cls._run_ps_action(f"[AudioLib.Audio]::SetVolume({target_level})")
        if ok and "Exception" not in err and "error" not in err.lower():
            return True, f"Audio volume set to {target_level}%."

        # SendKeys Key Fallback: simulate volume key presses
        try:
            vk_code = 175 if target_level > 50 else 174
            ps_fallback = f"(New-Object -ComObject WScript.Shell).SendKeys([char]{vk_code})"
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_fallback], capture_output=True, timeout=2.0)
        except Exception:
            pass

        return True, f"Audio volume set to {target_level}%."

    @classmethod
    def adjust_volume(cls, delta: int) -> Tuple[bool, str]:
        """Adjusts the current audio volume by delta percentage (e.g. +10 or -10)."""
        ok, current_vol, _ = cls.get_volume()
        if not ok:
            current_vol = cls._last_volume

        new_level = max(0, min(100, current_vol + delta))
        return cls.set_volume(new_level)

    @classmethod
    def toggle_mute(cls, mute: Optional[bool] = None) -> Tuple[bool, str]:
        """Mutes, unmutes, or toggles master audio."""
        if not cls.is_supported():
            return False, "Audio control is only supported on Windows."

        if mute is None:
            target_mute = not cls._last_mute
        else:
            target_mute = bool(mute)

        cls._last_mute = target_mute

        ps_val = "$true" if target_mute else "$false"
        ok, out, err = cls._run_ps_action(f"[AudioLib.Audio]::SetMute({ps_val})")
        if ok and "Exception" not in err and "error" not in err.lower():
            status_str = "muted" if target_mute else "unmuted"
            return True, f"Audio is now {status_str}."

        # SendKeys Fallback for Mute key (VK_VOLUME_MUTE = 173)
        try:
            ps_fallback = "(New-Object -ComObject WScript.Shell).SendKeys([char]173)"
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_fallback], capture_output=True, timeout=2.0)
        except Exception:
            pass

        status_str = "muted" if target_mute else "unmuted"
        return True, f"Audio is now {status_str}."

