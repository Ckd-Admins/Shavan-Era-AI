import requests

URL = "http://127.0.0.1:9000/forward"

tests = [
    {"command": "open_app", "params": {"app_name": "notepad"}},
    {"command": "open_app", "params": {"app_name": "definitely_not_installed_app_xyz"}},
]

for t in tests:
    try:
        r = requests.post(URL, json=t, timeout=5.0)
        print("REQUEST:", t)
        print("STATUS:", r.status_code)
        print("RESPONSE:", r.json())
    except Exception as e:
        print("ERROR sending request:", e)
