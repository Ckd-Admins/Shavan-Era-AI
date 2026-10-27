import os

file_path = r"d:\era_agent\commands\system_commands.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

if "set_display_brightness" not in content:
    display_commands = '''

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
'''
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(display_commands)
    print("Added display brightness commands to system_commands.py")
else:
    print("set_display_brightness already in system_commands.py")
