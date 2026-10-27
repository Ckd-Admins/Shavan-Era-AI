"""Era Bridge's catalog of Era Local Agent's commands.

This is Bridge's own description of what Local Agent can do -- it has
to be maintained here, by hand, because Local Agent's own GET
/commands endpoint only returns a name and a description, not
parameter or confirmation metadata (confirmed during the architecture
audit). If Local Agent's command set changes, this catalog needs a
matching update.

`enabled=True` marks the 5 commands that work end-to-end today
(Class 1, per the approved Era Bridge architecture) -- these take no
parameters and need no confirmation, so they execute immediately.
`enabled=False` marks the 7 commands that exist on Local Agent but
require an approved, additive change to its /execute contract before
Bridge can actually deliver their parameters (Class 2, deferred to
Phase 3). Their param/confirmation metadata is recorded here now so
the moment Phase 3 is approved, flipping `enabled=True` is the only
change needed -- the session engine already knows how to collect
their inputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ParamSpec:
    name: str
    prompt: str
    required: bool = True


@dataclass
class CommandSpec:
    name: str
    description: str
    enabled: bool
    params: List[ParamSpec] = field(default_factory=list)
    requires_confirmation: bool = False


CATALOG: Dict[str, CommandSpec] = {
    spec.name: spec
    for spec in [
        # --- Class 1: enabled, no params, execute immediately ---
        CommandSpec("open_notepad", "Opens Windows Notepad", enabled=True),
        CommandSpec("open_calculator", "Opens Windows Calculator", enabled=True),
        CommandSpec("open_file_explorer", "Opens Windows File Explorer", enabled=True),
        CommandSpec("open_chrome", "Opens Google Chrome, if installed", enabled=True),
        CommandSpec("open_camera", "Opens the Windows Camera app", enabled=True),
        
        # --- Class 1b: enabled, optional params, can execute with defaults ---
        CommandSpec(
            "open_browser",
            "Opens a specified browser (Chrome, Edge, Firefox, Brave) with optional URL",
            enabled=True,
            params=[
                ParamSpec("browser_name", "Which browser? (chrome, edge, firefox, brave)", required=False),
                ParamSpec("url", "What URL should I open?", required=False),
            ],
        ),
        CommandSpec(
            "open_app",
            "Opens any app by name (e.g. spotify, vscode, notepad)",
            enabled=True,
            params=[ParamSpec("app_name", "Which app should I open?")],
        ),

        # --- System Controls: display, audio, peripherals, keyboard backlight ---
        CommandSpec("get_display_brightness", "Queries the current display brightness level", enabled=True),
        CommandSpec(
            "set_display_brightness",
            "Sets display brightness percentage (0-100)",
            enabled=True,
            params=[ParamSpec("level", "What brightness level percentage (0-100)?", required=False)],
        ),
        CommandSpec(
            "adjust_display_brightness",
            "Adjusts display brightness by relative percentage delta",
            enabled=True,
            params=[ParamSpec("delta", "Relative adjustment delta (e.g. 10 or -10)?", required=False)],
        ),
        CommandSpec("get_audio_volume", "Queries current master audio volume level", enabled=True),
        CommandSpec(
            "set_audio_volume",
            "Sets master audio volume percentage (0-100)",
            enabled=True,
            params=[ParamSpec("level", "What volume level percentage (0-100)?", required=False)],
        ),
        CommandSpec(
            "adjust_audio_volume",
            "Adjusts master audio volume by relative percentage delta",
            enabled=True,
            params=[ParamSpec("delta", "Relative adjustment delta (e.g. 10 or -10)?", required=False)],
        ),
        CommandSpec(
            "toggle_audio_mute",
            "Mutes or unmutes master audio",
            enabled=True,
            params=[ParamSpec("mute", "Mute audio (true/false)?", required=False)],
        ),
        CommandSpec(
            "set_bluetooth_state",
            "Enables or disables Bluetooth radio",
            enabled=True,
            params=[ParamSpec("enable", "Enable Bluetooth (true/false)?", required=False)],
        ),
        CommandSpec(
            "set_wifi_state",
            "Enables or disables Wi-Fi network interface",
            enabled=True,
            params=[ParamSpec("enable", "Enable Wi-Fi (true/false)?", required=False)],
        ),
        CommandSpec("get_peripheral_status", "Queries current status of Bluetooth and Wi-Fi", enabled=True),
        CommandSpec(
            "set_keyboard_backlight",
            "Sets keyboard backlight brightness percentage (0-100)",
            enabled=True,
            params=[ParamSpec("level", "What keyboard brightness percentage (0-100)?", required=False)],
        ),
        CommandSpec(
            "adjust_keyboard_backlight",
            "Adjusts keyboard backlight brightness by relative percentage delta",
            enabled=True,
            params=[ParamSpec("delta", "Relative adjustment delta (e.g. 25 or -25)?", required=False)],
        ),
        CommandSpec(
            "process_natural_language_control",
            "Interprets natural language request into system control calls",
            enabled=True,
            params=[ParamSpec("query", "What would you like to control?")],
        ),

        
        # --- Class 2: Enabled parameterized commands ---
        CommandSpec(
            "search_file",
            "Searches for a file or folder across all drives and opens it",
            enabled=True,
            params=[
                ParamSpec("file_name", "What file are you looking for?"),
                ParamSpec("search_root", "Which folder should I search under?", required=False),
                ParamSpec("open_with", "Program to open with", required=False),
            ],
        ),
        CommandSpec(
            "open_file",
            "Finds and opens a specific file on the computer",
            enabled=True,
            params=[
                ParamSpec("file_name", "Name or path of the file to open"),
                ParamSpec("open_with", "Program to open with", required=False),
            ],
        ),
        CommandSpec(
            "open_whatsapp",
            "Opens WhatsApp with a message pre-filled for a contact",
            enabled=True,
            params=[
                ParamSpec("phone", "What's the recipient's phone number, with country code?"),
                ParamSpec("message", "What message should I pre-fill?", required=False),
            ],
        ),
        CommandSpec(
            "shutdown_pc",
            "Safely shuts down the computer after a short delay",
            enabled=False,
            requires_confirmation=True,
        ),
        CommandSpec(
            "restart_pc",
            "Safely restarts the computer after a short delay",
            enabled=False,
            requires_confirmation=True,
        ),
        CommandSpec(
            "cancel_shutdown",
            "Cancels a pending shutdown or restart",
            enabled=False,
        ),
    ]
}


def get_spec(name: str) -> CommandSpec | None:
    return CATALOG.get(name.strip().lower())
