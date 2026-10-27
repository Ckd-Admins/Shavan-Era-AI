# ERA AI Assistant — Build Instructions

## Overview

ERA is packaged as a full Windows desktop application using **Electron + electron-builder**.  
It bundles:
- The Electron shell (UI host)
- The Node.js Express/WebSocket server (`dist/server.cjs`)
- The React frontend (`dist/index.html` + assets)
- A bundled Python 3.14 runtime (`resources/python_runtime/`)
- ERA Local Agent (Python FastAPI, port 8000)
- ERA Bridge Gateway (Python FastAPI, port 8100)
- ERA Vision Agent (Python FastAPI, port 8200)

---

## Prerequisites (Development Machine Only)

| Tool | Version | Purpose |
|------|---------|---------|
| Node.js | ≥ 20.x | Build tooling |
| Python | 3.14 (Windows) | Service runtime (bundled) |
| npm | ≥ 10.x | Package manager |

No Python or Node.js is required on **target PCs**.

---

## Directory Structure

```
D:\era-voice-assistant\          ← Main project (Electron + React UI)
│  electron/main.cjs             ← Electron main process (service launcher)
│  electron/preload.cjs          ← Electron preload script
│  server.ts                     ← Node.js Express + WebSocket server
│  dist/                         ← Built frontend + server bundle
│  assets/icon.ico / icon.png    ← App icons
│  resources/
│    python_runtime/             ← Bundled Python 3.14 interpreter + packages
│    era_services/
│      era_agent/                ← ERA Local Agent source (port 8000)
│      era_bridge/               ← ERA Bridge source (port 8100)
│      era_vision/               ← ERA Vision Agent source (port 8200)

D:\era_agent\                    ← Development source (original)
D:\era_bridge\era_bridge\        ← Development source (original)
D:\era_vision\era_vision_agent_phase2\era_vision_agent\  ← Dev source
```

---

## Step 1: Prepare Resources

These only need re-running when service source code changes.

```powershell
# 1. Sync ERA Agent
robocopy D:\era_agent D:\era-voice-assistant\resources\era_services\era_agent /E /XD .venv __pycache__ .pytest_cache

# 2. Sync ERA Bridge
robocopy D:\era_bridge\era_bridge D:\era-voice-assistant\resources\era_services\era_bridge /E /XD .venv __pycache__ .pytest_cache

# 3. Sync ERA Vision
robocopy D:\era_vision\era_vision_agent_phase2\era_vision_agent D:\era-voice-assistant\resources\era_services\era_vision /E /XD .venv __pycache__ .pytest_cache

# 4. Sync Python Runtime (only when Python packages change)
robocopy C:\Users\MSI\AppData\Local\Python\pythoncore-3.14-64 D:\era-voice-assistant\resources\python_runtime /E /XD __pycache__ .git
```

---

## Step 2: Build Frontend + Server Bundle

```powershell
cd D:\era-voice-assistant
npm run build
```

This produces:
- `dist/index.html` + `dist/assets/` — React frontend
- `dist/server.cjs` — Bundled Express/WebSocket server

---

## Step 3: Build Windows Installer + Portable

```powershell
cd D:\era-voice-assistant
npx electron-builder --win --x64
```

**If EPERM error occurs** (Windows Defender scanning extracted Electron):
```powershell
# Pre-extract Electron manually
$cache = "$env:LOCALAPPDATA\electron\Cache"
$zip = Get-ChildItem $cache -Recurse -Filter "electron-v44*.zip" | Select-Object -First 1
New-Item -Force -ItemType Directory "dist-electron\win-unpacked"
Expand-Archive -Path $zip.FullName -DestinationPath "dist-electron\win-unpacked" -Force

# Then run with --prepackaged
npx electron-builder --win --x64 --prepackaged "dist-electron\win-unpacked"
```

---

## Build Output

| File | Description |
|------|-------------|
| `dist-electron/ERA AI Assistant Setup 1.0.0.exe` | Windows NSIS Installer |
| `dist-electron/ERA_Portable_1.0.0.exe` | Portable single-file executable |
| `dist-electron/win-unpacked/` | Unpacked app (for testing) |

---

## Service Ports

| Service | Port | Entry Point |
|---------|------|------------|
| ERA Local Agent | 8000 | `era_services/era_agent/api_server.py` |
| ERA Bridge Gateway | 8100 | `era_services/era_bridge/main.py` |
| ERA Vision Agent | 8200 | `era_services/era_vision/main.py` |
| ERA Voice Assistant UI | 3000 | `dist/server.cjs` |

---

## User Data Location

On end-user PCs, ERA stores all mutable data here:

```
%LOCALAPPDATA%\ERA\
  logs\           ← launcher.log, agent.log, bridge.log, vision.log, error.log
  config\         ← whatsapp_contacts.json, whatsapp_chats.json, keys.enc
  workspace\      ← ERA code workspace, screen captures
  .first_run_complete
```

**Application binaries** are stored in the Electron app directory (read-only after install).

---

## Environment Variables Set by Launcher

| Variable | Value |
|----------|-------|
| `ERA_APP_DATA` | `%LOCALAPPDATA%\ERA` |
| `ERA_CONFIG_DIR` | `%LOCALAPPDATA%\ERA\config` |
| `ERA_WORKSPACE_DIR` | `%LOCALAPPDATA%\ERA\workspace` |

All Python services read these to find user data instead of hardcoded paths.

---

## Versioning

Current version: **1.0.0**

To release a new version:
1. Bump `"version"` in `package.json`
2. Re-run steps 1–3 above
3. Distribute the new `.exe` files

---

## Updating Python Services

When ERA Agent/Bridge/Vision code changes:
1. Make changes in the original `D:\era_agent`, `D:\era_bridge`, `D:\era_vision` directories
2. Re-run the robocopy sync commands (Step 1)
3. Re-run electron-builder (Step 3) — no need to rebuild frontend

When Python packages change:
1. Install packages into `resources/python_runtime/` Python
2. Re-run electron-builder
