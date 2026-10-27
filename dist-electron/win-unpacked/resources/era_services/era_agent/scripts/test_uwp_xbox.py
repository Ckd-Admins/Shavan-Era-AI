import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from commands import registry
from commands import system_commands

candidates = [
    'xbox',
    'x box',
    'xbox app',
    'xbox game bar',
    'xbox console companion',
    'microsoft.xboxgameoverlay',
]

for name in candidates:
    try:
        uwp = system_commands._find_uwp_app_id(name)
        found = system_commands._find_app_path(name)
        print(f"\nCANDIDATE: '{name}'")
        print(f"  _find_uwp_app_id -> {uwp}")
        print(f"  _find_app_path -> {found}")
        r = registry.execute('open_app', name)
        print(f"  execute -> success={r.success}, message={r.message}")
    except Exception as e:
        print(f"  ERROR for '{name}': {e}")
