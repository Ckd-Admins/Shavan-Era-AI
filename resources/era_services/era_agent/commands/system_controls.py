"""System Control commands for Era Agent.

Registers Windows hardware control functions (display brightness, audio volume,
Bluetooth, Wi-Fi, keyboard backlight, and natural language intent parsing)
with the Era Agent command registry.
"""

from __future__ import annotations

from typing import Optional

try:
    from era_agent.controls import SystemControlManager
except ImportError:
    from controls import SystemControlManager

from .registry import CommandParam, CommandResult, registry


@registry.register(
    "set_display_brightness",
    "Sets display brightness level percentage (0 to 100)",
    params=[
        CommandParam("level", "int", "Target brightness level (0-100)", required=True, default=50),
    ],
)
def set_display_brightness(level: int = 50) -> CommandResult:
    ok, msg = SystemControlManager.execute_intent("set_display_brightness", {"level": level})
    return CommandResult(ok, msg)


@registry.register(
    "adjust_display_brightness",
    "Adjusts display brightness by a relative delta percentage (e.g. +10 or -10)",
    params=[
        CommandParam("delta", "int", "Relative change (+10 or -10)", required=False, default=10),
    ],
)
def adjust_display_brightness(delta: int = 10) -> CommandResult:
    ok, msg = SystemControlManager.execute_intent("adjust_display_brightness", {"delta": delta})
    return CommandResult(ok, msg)


@registry.register("get_display_brightness", "Queries the current display brightness level")
def get_display_brightness() -> CommandResult:
    ok, msg = SystemControlManager.execute_intent("get_display_brightness", {})
    return CommandResult(ok, msg)


@registry.register(
    "set_audio_volume",
    "Sets master audio volume percentage (0 to 100)",
    params=[
        CommandParam("level", "int", "Target volume level (0-100)", required=True, default=50),
    ],
)
def set_audio_volume(level: int = 50) -> CommandResult:
    ok, msg = SystemControlManager.execute_intent("set_audio_volume", {"level": level})
    return CommandResult(ok, msg)


@registry.register(
    "adjust_audio_volume",
    "Adjusts master audio volume by a relative delta percentage (e.g. +10 or -10)",
    params=[
        CommandParam("delta", "int", "Relative change (+10 or -10)", required=False, default=10),
    ],
)
def adjust_audio_volume(delta: int = 10) -> CommandResult:
    ok, msg = SystemControlManager.execute_intent("adjust_audio_volume", {"delta": delta})
    return CommandResult(ok, msg)


@registry.register(
    "toggle_audio_mute",
    "Mutes or unmutes master audio",
    params=[
        CommandParam("mute", "bool", "True to mute, False to unmute, None to toggle", required=False),
    ],
)
def toggle_audio_mute(mute: Optional[bool] = None) -> CommandResult:
    ok, msg = SystemControlManager.execute_intent("toggle_audio_mute", {"mute": mute})
    return CommandResult(ok, msg)


@registry.register("get_audio_volume", "Queries the current master audio volume")
def get_audio_volume() -> CommandResult:
    ok, msg = SystemControlManager.execute_intent("get_audio_volume", {})
    return CommandResult(ok, msg)


@registry.register(
    "set_bluetooth_state",
    "Enables or disables Bluetooth radio and services",
    params=[
        CommandParam("enable", "bool", "True to enable Bluetooth, False to disable", required=True, default=True),
    ],
)
def set_bluetooth_state(enable: bool = True) -> CommandResult:
    ok, msg = SystemControlManager.execute_intent("set_bluetooth_state", {"enable": enable})
    return CommandResult(ok, msg)


@registry.register(
    "set_wifi_state",
    "Enables or disables Wi-Fi interface",
    params=[
        CommandParam("enable", "bool", "True to enable Wi-Fi, False to disable", required=True, default=True),
    ],
)
def set_wifi_state(enable: bool = True) -> CommandResult:
    ok, msg = SystemControlManager.execute_intent("set_wifi_state", {"enable": enable})
    return CommandResult(ok, msg)


@registry.register("get_peripheral_status", "Queries current Bluetooth and Wi-Fi status")
def get_peripheral_status() -> CommandResult:
    ok, msg = SystemControlManager.execute_intent("get_peripheral_status", {})
    return CommandResult(ok, msg)


@registry.register(
    "set_keyboard_backlight",
    "Sets keyboard backlight brightness percentage (0 to 100)",
    params=[
        CommandParam("level", "int", "Target brightness level (0-100)", required=True, default=50),
    ],
)
def set_keyboard_backlight(level: int = 50) -> CommandResult:
    ok, msg = SystemControlManager.execute_intent("set_keyboard_backlight", {"level": level})
    return CommandResult(ok, msg)


@registry.register(
    "adjust_keyboard_backlight",
    "Adjusts keyboard backlight brightness by relative delta (reads actual hardware level first so manual Dragon Center changes are respected)",
    params=[
        CommandParam("delta", "int", "Relative change (+25 or -25)", required=False, default=25),
    ],
)
def adjust_keyboard_backlight(delta: int = 25) -> CommandResult:
    ok, msg = SystemControlManager.execute_intent("adjust_keyboard_backlight", {"delta": delta})
    return CommandResult(ok, msg)


@registry.register(
    "get_keyboard_backlight",
    "Returns the current keyboard backlight brightness as read from hardware (respects manual Dragon Center changes)",
)
def get_keyboard_backlight() -> CommandResult:
    ok, msg = SystemControlManager.execute_intent("get_keyboard_backlight", {})
    return CommandResult(ok, msg)


@registry.register(
    "save_keyboard_backlight",
    "Saves the current ERA keyboard backlight setting to MCU flash so it persists after reboot",
)
def save_keyboard_backlight() -> CommandResult:
    ok, msg = SystemControlManager.execute_intent("save_keyboard_backlight", {})
    return CommandResult(ok, msg)


@registry.register(
    "process_natural_language_control",
    "Interprets natural language commands like 'increase brightness' or 'adjust volume' into system controls",
    params=[
        CommandParam("query", "str", "Natural language request string", required=True),
    ],
)
def process_natural_language_control(query: Optional[str] = None) -> CommandResult:
    if not query:
        return CommandResult(False, "No natural language request string provided.")
    ok, msg = SystemControlManager.execute_natural_language(query)
    return CommandResult(ok, msg)
