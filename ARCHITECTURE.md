# ERA AI Assistant — Architecture

## System Overview

ERA (Evolving Responsive Assistant) is a multi-service AI assistant packaged as a Windows desktop application using Electron.

```
┌─────────────────────────────────────────────────────────┐
│                  ERA AI Assistant (Electron)             │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │          electron/main.cjs (Launcher)            │   │
│  │  - Single instance lock                          │   │
│  │  - Service orchestration                         │   │
│  │  - Health checks                                 │   │
│  │  - Graceful shutdown                             │   │
│  │  - System tray                                   │   │
│  └────────────────┬────────────────────────────────┘   │
│                   │ manages                              │
│     ┌─────────────┼─────────────────────────┐           │
│     ▼             ▼             ▼            ▼           │
│  ┌──────┐    ┌────────┐   ┌────────┐   ┌────────┐      │
│  │Agent │    │Bridge  │   │Vision  │   │Express │      │
│  │:8000 │    │:8100   │   │:8200   │   │:3000   │      │
│  │Python│    │Python  │   │Python  │   │Node.js │      │
│  └──────┘    └────────┘   └────────┘   └────────┘      │
│       ▲            ▲           ▲             │           │
│       │            │           │             │           │
│       └────────────┴───────────┘             │           │
│                    calls                     │           │
│  ┌───────────────────────────────────────────▼──────┐   │
│  │           React Frontend (BrowserWindow)          │   │
│  │  - Voice/Text chat (Gemini Multimodal Live API)  │   │
│  │  - Settings / API key management                 │   │
│  │  - Mission Engine dashboard                      │   │
│  │  - Vision status panel                           │   │
│  │  - Outcome Engine panel                          │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## Service Descriptions

### ERA Local Agent (Port 8000)
- **Language:** Python 3.14 + FastAPI + uvicorn
- **Entry:** `era_services/era_agent/api_server.py`
- **Role:** Windows PC control engine
  - Opens apps, files, windows
  - Controls keyboard, mouse, display, audio
  - Gmail OAuth integration (read/send email)
  - WhatsApp Business Cloud API
  - Mission Engine (multi-step autonomous tasks)
  - Outcome Engine Orchestrator
  - Natural language command parsing

### ERA Bridge Gateway (Port 8100)
- **Language:** Python 3.14 + FastAPI + uvicorn
- **Entry:** `era_services/era_bridge/main.py`
- **Role:** Middleware / API gateway
  - Routes commands between UI and Agent
  - Vision Agent passthrough endpoints
  - Authenticated with `BRIDGE_API_KEY`

### ERA Vision Agent (Port 8200)
- **Language:** Python 3.14 + FastAPI + uvicorn
- **Entry:** `era_services/era_vision/main.py`
- **Role:** Screen perception system
  - Continuous screen capture (mss, ImageGrab, GDI fallbacks)
  - Change detection (grid-based pixel diff)
  - Gemini Vision analysis of screen content
  - Active window tracking
  - Trading chart analysis
  - Autonomous action engine (via Bridge)
  - Authenticated with `VISION_AGENT_API_KEY`

### ERA Voice Assistant UI (Port 3000)
- **Language:** Node.js + Express + WebSocket
- **Entry:** `dist/server.cjs` (bundled from `server.ts`)
- **Role:** Main user interface server
  - Serves React frontend
  - Gemini Multimodal Live API (voice + vision)
  - WebSocket for real-time AI streaming
  - API key management (encrypted at rest)
  - Tool execution (writeCode, runCode, openFile, captureScreen)
  - WhatsApp chat reading/sending via Agent
  - Phone Link integration
  - YouTube analysis

---

## Startup Sequence

```
1. Electron app.whenReady()
2. Show splash screen
3. cleanupStalePorts() — kill any zombie ERA processes
4. startAgentService() — spawn python api_server.py on :8000
5. waitForUrl(8000/status, 30s)
6. startBridgeService() — spawn python main.py on :8100
7. startVisionService() — spawn python main.py on :8200
8. startExpressServer() — require(dist/server.cjs) in-process
9. createMainWindow() — polls :3000/api/health until ready
10. Health check all 4 services
11. Show main window (splash closes)
```

---

## Shutdown Sequence

```
1. User closes window / clicks Quit
2. isShuttingDown = true (stops auto-restart)
3. SIGTERM / taskkill Vision Agent
4. SIGTERM / taskkill Bridge Gateway
5. SIGTERM / taskkill Local Agent
6. SIGTERM / taskkill Express Server (if subprocess)
7. taskkill all remaining ERA port processes
8. app.quit() after 2s grace period
```

---

## Data Flow: User Voice Command

```
User speaks
    ↓ WebRTC microphone
Gemini Multimodal Live API (cloud)
    ↓ tool_call response
server.ts executeAgentCommand()
    ↓ HTTP POST /execute
ERA Local Agent :8000
    ↓ registry.execute()
Windows system command (e.g. subprocess.run)
    ↓ CommandResult
server.ts → Gemini → TTS audio
    ↓ WebSocket
React Frontend → speaker output
```

---

## User Data Architecture

```
%LOCALAPPDATA%\ERA\          (C:\Users\<username>\AppData\Local\ERA\)
│
├── logs\
│   ├── launcher.log         ← Electron main process log
│   ├── agent.log            ← ERA Agent stdout/stderr
│   ├── bridge.log           ← ERA Bridge stdout/stderr
│   ├── vision.log           ← ERA Vision Agent stdout/stderr
│   ├── server.log           ← Express server log (dev mode)
│   └── error.log            ← Uncaught exceptions
│
├── config\
│   ├── keys.enc             ← AES-256 encrypted API keys
│   ├── whatsapp_contacts.json
│   ├── whatsapp_chats.json
│   └── vision.env           ← Copied from vision .env on first run
│
├── workspace\               ← ERA's code workspace
│   ├── current_screen.png   ← Screen capture (temporary)
│   └── *.py, *.js, etc.    ← Files created by ERA
│
└── .first_run_complete      ← Marker written after successful first run
```

---

## Security Architecture

| Concern | Implementation |
|---------|---------------|
| Internal APIs | Bound to 127.0.0.1 only (no external exposure) |
| API keys storage | AES-256-CBC encrypted in `keys.enc` |
| Vision auth | `VISION_AGENT_API_KEY` header required |
| Bridge auth | `X-Era-Bridge-Key` header required |
| No hardcoded secrets | Keys loaded from env vars / encrypted file |
| UAC | Runs as invoker (no elevation required) |
| Screen privacy | Privacy exclusions for password managers etc. |

---

## Bundled Python Runtime

The packaged app includes a complete Python 3.14.7 (64-bit) runtime at:
```
<install>\resources\python_runtime\
```

This runtime includes all required packages pre-installed:
- fastapi, uvicorn, pydantic, starlette
- httpx, requests, python-dotenv
- google-auth, google-api-python-client, google-auth-oauthlib
- mss, Pillow, numpy, psutil, pytesseract, keyring
- pywin32, pyautogui, keyboard, opencv-python
- All other ERA dependencies

Target PCs **do not need Python installed**.

---

## Version Information

| Component | Version |
|-----------|---------|
| ERA Application | 1.0.0 |
| Electron | 44.2.0 |
| Python Runtime | 3.14.7 (64-bit) |
| Node.js | 24.x |
| React | 19.x |
| FastAPI | 0.141.x |
| Gemini SDK | @google/genai 2.x |
