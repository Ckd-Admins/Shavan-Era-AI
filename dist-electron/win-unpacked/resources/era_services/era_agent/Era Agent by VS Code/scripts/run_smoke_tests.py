from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from commands import registry

tests = [
    ("open_calculator", {}),
    ("open_browser", {"url": "https://www.google.com"}),
    ("open_app", {"app_name": "notepad"}),
    ("open_whatsapp", {"phone": "+10000000000", "message": "Hello from test"}),
]

for cmd, params in tests:
    r = registry.execute(cmd, **params)
    print(f"CMD: {cmd} -> success={r.success} | message={r.message}")
