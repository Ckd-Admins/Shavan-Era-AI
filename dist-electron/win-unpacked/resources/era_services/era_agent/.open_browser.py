import sys
from pathlib import Path
sys.path.insert(0, str(Path('.').resolve()))
from commands import registry

print('Available commands:', list(registry._commands.keys()))
for cmd in ('open_browser','open_chrome','open_edge','open_firefox','open_chrome','open_browser'):
    if cmd in registry._commands:
        print('Executing', cmd)
        try:
            res = registry.execute(cmd, url='https://www.bing.com')
            print('Result:', res.success, res.message)
        except Exception as e:
            print('Execution error:', e)
        break
else:
    print('No browser-related command found')
