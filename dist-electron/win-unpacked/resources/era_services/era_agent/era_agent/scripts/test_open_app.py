import sys
from pathlib import Path

# Ensure the project root (parent of this scripts/ folder) is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from commands import registry

apps = ['notepad', 'calc', 'code', 'chrome', 'spotify', 'vscode', 'definitely_not_installed_app_xyz']

for a in apps:
    try:
        r = registry.execute('open_app', a)
        print(f"APP:{a} | success={r.success} | message={r.message}")
    except Exception as exc:
        print(f"APP:{a} | ERROR: {exc}")
