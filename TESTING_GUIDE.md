# ERA AI Assistant — Testing Guide

## Test Environment Requirements

**Test PC must NOT have:**
- Python installed
- Node.js installed
- The ERA source code
- VS Code / Antigravity
- Any development tools
- The D:\era_agent, D:\era_bridge, D:\era_vision directories

**Test PC must have:**
- Windows 10 or Windows 11 (64-bit)
- At least 4 GB RAM
- At least 2 GB free disk space
- Internet connection (for Gemini API calls)
- Microphone (optional, for voice)
- Screen (required for Vision Agent)

---

## Test 1: Clean Build from Source

Run on your development PC:

```powershell
cd D:\era-voice-assistant

# Clean previous build artifacts
Remove-Item -Recurse -Force dist-electron\win-unpacked -ErrorAction SilentlyContinue
Remove-Item -Force dist-electron\*.exe -ErrorAction SilentlyContinue

# Build
npm run build
npx electron-builder --win --x64
```

✅ **Pass:** `dist-electron\ERA AI Assistant Setup 1.0.0.exe` created  
✅ **Pass:** `dist-electron\ERA_Portable_1.0.0.exe` created

---

## Test 2: Installer on Fresh PC

1. Copy `ERA AI Assistant Setup 1.0.0.exe` to USB drive or network share
2. On clean Windows PC: double-click the installer
3. Accept defaults, click Install

✅ **Pass:** Installs without errors  
✅ **Pass:** Desktop shortcut created  
✅ **Pass:** Start Menu entry created

---

## Test 3: Launch via Desktop Shortcut

1. Double-click "ERA AI Assistant" on desktop

✅ **Pass:** ERA splash screen appears  
✅ **Pass:** ERA main UI loads within ~30 seconds  
✅ **Pass:** No CMD/PowerShell windows visible

---

## Test 4: No Terminal Required

1. Open Task Manager
2. Launch ERA
3. Confirm no CMD/PowerShell windows appear

✅ **Pass:** Only hidden processes (no visible terminals)

---

## Test 5: Services Auto-Start

1. After ERA loads, check Task Manager → Details tab
2. Should see: `python.exe` processes (×3) and `node.exe` processes

Open in browser to verify:
- http://127.0.0.1:8000/status → `{"status": "online"}`
- http://127.0.0.1:8100/health → `{"status": "ok"}`
- http://127.0.0.1:8200/v1/vision/status → vision status JSON
- http://127.0.0.1:3000/api/health → `{"status": "ok"}`

✅ **Pass:** All 4 ports respond

---

## Test 6: Voice / Text Interaction

1. Type a message in the ERA chat interface
2. ERA should respond via Gemini AI

> **Note:** GEMINI_API_KEY must be configured. Enter it in ERA Settings on first run.

✅ **Pass:** ERA responds to text input  
✅ **Pass:** ERA responds to voice (if microphone available)

---

## Test 7: PC Control Commands

Say or type:
- "Open Notepad"
- "Open Chrome"
- "Take a screenshot"

✅ **Pass:** Commands execute on the Windows PC

---

## Test 8: File / Application Interaction

Say or type:
- "Open the workspace folder"
- "Create a Python file called test.py"

✅ **Pass:** File is created in ERA workspace

---

## Test 9: Vision Functionality

1. Open any application on screen
2. Ask ERA: "What do you see on my screen?"

✅ **Pass:** ERA Vision describes screen content  
*(Requires GEMINI_API_KEY and VISION_AGENT_API_KEY configured)*

---

## Test 10: Close ERA

1. Click the X button or use File → Quit
2. Check Task Manager

✅ **Pass:** All ERA python.exe processes terminate  
✅ **Pass:** Ports 8000, 8100, 8200, 3000 are freed

---

## Test 11: Relaunch ERA

1. Double-click ERA again
2. ERA should restart all services fresh

✅ **Pass:** ERA restarts without error

---

## Test 12: Reboot and Relaunch

1. Reboot Windows
2. Launch ERA from Desktop shortcut

✅ **Pass:** ERA starts normally after reboot

---

## Test 13: Single Instance Prevention

1. ERA is already running
2. Double-click ERA shortcut again

✅ **Pass:** Existing ERA window comes to foreground  
✅ **Pass:** No second ERA instance starts

---

## Test 14: Portable Build Test

1. Copy `ERA_Portable_1.0.0.exe` to USB drive
2. On a different Windows PC (no ERA installed): run `ERA_Portable_1.0.0.exe`

✅ **Pass:** ERA runs from USB/portable location

---

## Test 15: Second PC Test

1. Install on a completely different Windows PC
2. Run through Tests 3–12

✅ **Pass:** ERA functions identically on both PCs

---

## Log Locations

If any test fails, check logs at:

```
%LOCALAPPDATA%\ERA\logs\
  launcher.log   ← Main startup sequence log
  agent.log      ← ERA Local Agent (port 8000) output
  bridge.log     ← ERA Bridge (port 8100) output
  vision.log     ← ERA Vision Agent (port 8200) output
  server.log     ← Express server (port 3000) output
  error.log      ← Any uncaught errors
```

---

## Known Limitations

1. **Tesseract OCR**: Optional. The Vision Agent's OCR feature requires Tesseract to be separately installed on the target PC and added to PATH. ERA starts without it; only OCR-based screen reading degrades gracefully.

2. **Gmail OAuth**: First-time Gmail authorization requires a browser popup. After auth, the token is saved to `%LOCALAPPDATA%\ERA\config\token.json`.

3. **WhatsApp**: Uses WhatsApp Business Cloud API. Requires WHATSAPP_API_TOKEN and WHATSAPP_PHONE_NUMBER_ID configured in ERA settings.

4. **GEMINI_API_KEY**: Must be entered in ERA Settings on first run. ERA will not have AI responses without it.

5. **Windows Defender**: May flag the portable .exe initially. This is normal for self-extracting Electron apps. Add an exception or run the full installer instead.
