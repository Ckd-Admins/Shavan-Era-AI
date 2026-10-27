"""Unified System Control Manager for Era Agent.

Orchestrates DisplayControl, AudioControl, PeripheralControl, KeyboardControl,
and IntentParser into a single clean system management interface.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Tuple

from .audio import AudioControl
from .display import DisplayControl
from .intent_parser import IntentParser, SystemIntent
from .keyboard import KeyboardControl
from .peripherals import PeripheralControl
from .phone_link import PhoneLinkControl

logger = logging.getLogger(__name__)


class SystemControlManager:
    """Central orchestrator for all system control functions and natural language processing."""

    @classmethod
    def execute_intent(cls, action: str, params: Dict[str, Any]) -> Tuple[bool, str]:
        """Executes a structured system action by name with given parameters.

        Returns:
            Tuple of (success: bool, message: str)
        """
        action_name = action.strip().lower()

        # Display Brightness
        if action_name == "set_display_brightness":
            level = params.get("level", 50)
            return DisplayControl.set_brightness(level)

        if action_name == "adjust_display_brightness":
            delta = params.get("delta", 10)
            return DisplayControl.adjust_brightness(delta)

        if action_name == "get_display_brightness":
            ok, val, msg = DisplayControl.get_brightness()
            return ok, msg

        # Audio Volume & Mute
        if action_name == "set_audio_volume":
            level = params.get("level", 50)
            return AudioControl.set_volume(level)

        if action_name == "adjust_audio_volume":
            delta = params.get("delta", 10)
            return AudioControl.adjust_volume(delta)

        if action_name == "toggle_audio_mute":
            mute = params.get("mute", None)
            return AudioControl.toggle_mute(mute)

        if action_name == "get_audio_volume":
            ok, val, msg = AudioControl.get_volume()
            return ok, msg

        # Peripheral Connections (Bluetooth / Wi-Fi)
        if action_name == "set_bluetooth_state":
            enable = params.get("enable", True)
            return PeripheralControl.set_bluetooth_state(enable)

        if action_name == "set_wifi_state":
            enable = params.get("enable", True)
            return PeripheralControl.set_wifi_state(enable)

        if action_name == "get_peripheral_status":
            ok, data, msg = PeripheralControl.get_peripheral_status()
            return ok, msg

        # Keyboard Backlight
        if action_name == "set_keyboard_backlight":
            level = params.get("level", 50)
            mode = params.get("mode", "rainbow")
            return KeyboardControl.set_keyboard_backlight(level, mode=mode)

        if action_name in ("enable_manual_keyboard_control", "reset_keyboard_control", "manual_keyboard"):
            return KeyboardControl.enable_manual_control()

        if action_name == "adjust_keyboard_backlight":
            delta = params.get("delta", 25)
            return KeyboardControl.adjust_keyboard_backlight(delta)

        if action_name == "get_keyboard_backlight":
            ok, val, msg = KeyboardControl.get_keyboard_backlight()
            return ok, msg

        if action_name == "save_keyboard_backlight":
            return KeyboardControl.save_keyboard_backlight()

        # Phone Link Device Integration
        if action_name in ("make_phone_call", "make_call", "call_phone", "dial"):
            target = params.get("phone") or params.get("number") or params.get("contact") or params.get("target")
            return PhoneLinkControl.make_call(target)

        if action_name in ("read_phone_messages", "read_messages", "get_phone_messages"):
            limit = params.get("limit", 5)
            ok, data, msg = PhoneLinkControl.read_messages(limit)
            return ok, msg

        if action_name in ("transfer_phone_files", "transfer_files", "sync_phone_files"):
            direction = params.get("direction", "phone_to_laptop")
            file_name = params.get("file_name") or params.get("filename")
            dest = params.get("destination") or params.get("dest")
            ok, data, msg = PhoneLinkControl.transfer_files(direction, file_name, dest)
            return ok, msg

        if action_name in ("get_phone_link_status", "phone_link_status", "check_phone_link"):
            ok, data, msg = PhoneLinkControl.get_status()
            return ok, msg

        # WhatsApp Messaging
        if action_name == "open_whatsapp":
            phone = params.get("phone") or params.get("contact") or params.get("recipient")
            msg = params.get("message") or params.get("text") or params.get("msg") or "Hello"
            try:
                from commands.system_commands import open_whatsapp
                res = open_whatsapp(phone=phone, message=msg)
                return res.success, res.message
            except Exception as exc:
                return False, f"Failed to execute open_whatsapp: {exc}"

        return False, f"Unknown system control action: '{action}'"

    @classmethod
    def execute_natural_language(cls, query: str) -> Tuple[bool, str]:
        """Parses and executes a natural language query for system functions.

        Example queries:
            - "increase brightness"
            - "set volume to 75%"
            - "turn on bluetooth"
            - "mute audio"

        Returns:
            Tuple of (success: bool, message: str)
        """
        intent: SystemIntent = IntentParser.parse(query)
        if not intent.matched or intent.action == "unknown":
            return False, f"Could not interpret system control request: '{query}'"

        logger.info("Natural language intent matched: action='%s', params=%s", intent.action, intent.params)
        return cls.execute_intent(intent.action, intent.params)
