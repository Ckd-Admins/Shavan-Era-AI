# ERA AI Assistant — Troubleshooting Guide

## ERA Won't Launch (Blank Screen / Crash)

**Check logs first:**
```
%LOCALAPPDATA%\ERA\logs\launcher.log
%LOCALAPPDATA%\ERA\logs\error.log
```

### Common Issues

---

### ❌ "Python not found" / Agent won't start

**Symptom:** `launcher.log` shows `Python runtime not accessible`

**Cause:** The bundled Python runtime is missing or corrupted.

**Fix:**
1. Uninstall ERA and reinstall from `ERA AI Assistant Setup 1.0.0.exe`
2. Check that `<ERA Install>\resources\python_runtime\python.exe` exists
3. If using portable build, ensure the entire ERA folder was copied (not just the .exe)

---

### ❌ Port already in use

**Symptom:** ERA starts but some services fail  
**Log message:** `Address already in use` in `agent.log` / `bridge.log`

**Fix (PowerShell):**
```powershell
# Kill processes on ERA ports
foreach ($port in 8000, 8100, 8200, 3000) {
    $pids = (Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue).OwningProcess | Sort-Object -Unique
    foreach ($p in $pids) { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue }
}
# Wait, then relaunch ERA
```

---

### ❌ ERA UI shows but Agent is "offline"

**Symptom:** ERA UI loads but shows Agent as disconnected

**Check:** Open http://127.0.0.1:8000/status in browser

**If unreachable:**
1. Check `%LOCALAPPDATA%\ERA\logs\agent.log`
2. Look for `ModuleNotFoundError` → bundled Python runtime is missing packages
3. Look for `Permission denied` → run ERA as Administrator once to initialize

---

### ❌ Vision Agent fails to start

**Symptom:** `vision.log` shows error

**Most common cause:** Missing `GEMINI_API_KEY` or `VISION_AGENT_API_KEY`

**Fix:**
1. Open ERA → Settings → API Keys
2. Enter your Gemini API key
3. Restart ERA

**Alternative:** Check `%LOCALAPPDATA%\ERA\config\vision.env`

---

### ❌ Gmail / WhatsApp not working

**Gmail:**
- First use requires OAuth browser popup
- Token saved to `%LOCALAPPDATA%\ERA\config\token.json`
- If token expires: delete `token.json` and re-authenticate

**WhatsApp:**
- Requires WhatsApp Business Cloud API credentials
- Configure `WHATSAPP_API_TOKEN` and `WHATSAPP_PHONE_NUMBER_ID` in ERA Settings

---

### ❌ Windows Defender blocks ERA

**Symptom:** SmartScreen warning or antivirus blocks `.exe`

**Cause:** ERA is not code-signed with a paid certificate (SmartScreen flags unsigned apps from new publishers)

**Fix (safe):**
1. Click "More info" → "Run anyway" on SmartScreen warning
2. Or add ERA folder to Windows Defender exclusions
3. Or use the NSIS installer (usually trusted more than portable)

---

### ❌ Multiple ERA instances won't consolidate

**Symptom:** Second click opens new ERA window

**Cause:** Previous ERA instance crashed without releasing the single-instance lock

**Fix:**
```powershell
# Kill all ERA-related processes
Get-Process | Where-Object { $_.MainWindowTitle -like "*ERA*" -or $_.ProcessName -eq "era-ai-assistant" } | Stop-Process -Force
# Then relaunch ERA
```

---

### ❌ ERA works on dev PC but not on clean PC

**Check this list:**

| Item | How to verify |
|------|--------------|
| Python runtime bundled? | `<install>\resources\python_runtime\python.exe` exists |
| ERA services bundled? | `<install>\resources\era_services\era_agent\api_server.py` exists |
| Frontend built? | `<install>\resources\dist\index.html` exists |
| API keys configured? | ERA Settings → enter GEMINI_API_KEY |
| Firewall blocking? | Temporarily disable Windows Firewall and retry |

---

## Diagnostic Info to Collect

When reporting a bug, collect:

1. **ERA Version:** Shown in tray tooltip
2. **Windows Version:** `winver` command
3. **Log files:** Zip `%LOCALAPPDATA%\ERA\logs\` folder
4. **Health check results:**
   - http://127.0.0.1:8000/status
   - http://127.0.0.1:8100/health
   - http://127.0.0.1:8200/v1/vision/status
   - http://127.0.0.1:3000/api/health

---

## Reset ERA (Full Clean)

```powershell
# Stop ERA first, then:
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\ERA" -ErrorAction SilentlyContinue
# Relaunch ERA — first-run will re-initialize
```

> ⚠️ This deletes all ERA logs, config, and workspace files.
