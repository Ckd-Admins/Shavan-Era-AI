# Era AI Assistant - Standalone Desktop Application Guide

Welcome to **Era AI Assistant Desktop**, a standalone desktop application for Windows laptops. Era brings together multimodal AI voice conversation, desktop vision & screen sharing, local Windows OS automation, code execution workspace, WhatsApp Web integration, YouTube summaries, and Bluetooth music management into one native application.

---

## 🎨 Branding & Icons

Era features a unique futuristic application logo icon integrated across:
- Desktop window title bar
- Windows system tray icon
- Installer setup wizard (`Era-AI-Assistant-Setup-1.0.0.exe`)
- Start menu and Desktop shortcuts

Icon locations:
- `assets/icon.png` (High-resolution transparent app logo)
- `assets/icon.ico` (Windows native icon format)

---

## 🚀 How to Launch Era Desktop Application

### Option 1: Quick Batch Launcher (1-Click Startup)
Double-click `start_era_desktop.bat` in the `era-voice-assistant` folder. This automatically:
1. Starts the Era Python Companion Agent on `http://127.0.0.1:8000`.
2. Launches the native Era Desktop Application window.

### Option 2: Command Line Startup
Open a terminal in `d:\era-voice-assistant` and run:

```powershell
npm run electron:start
```

To run in development mode with live server output:

```powershell
npm run electron:dev
```

---

## 📦 How to Package & Share Era Desktop App

To build a standalone installer setup file (`.exe`) that can be shared and directly installed on any Windows laptop without needing terminal or developer setup:

1. Open a terminal in `d:\era-voice-assistant`.
2. Run the packaging command:

```powershell
npm run dist
```

3. Locate the output installer in the `dist-electron/` folder:
   - `dist-electron/Era-AI-Assistant-Setup-1.0.0.exe` (Standalone Windows Installer)
   - `dist-electron/Era-AI-Assistant-1.0.0.exe` (Portable executable)

---

## 🌟 Key Features Integrated in Era Desktop

| Feature | Description | Status |
| :--- | :--- | :---: |
| 🎙️ **Multimodal Voice Assistant** | Gemini Live WebSocket stream for real-time voice & audio interaction | ✅ Integrated |
| 🖥️ **Windows OS Automation** | 13 local OS commands: Open Notepad, Calc, Chrome, App launcher, Lock PC, File Search, Snap Windows | ✅ Integrated |
| 👁️ **Screen Vision & Capture** | Real-time physical desktop capture and screen context analysis | ✅ Integrated |
| 💻 **Code Sandbox Workspace** | Interactive code writing, debugging, and live script execution | ✅ Integrated |
| 💬 **WhatsApp Web & Messaging** | Contact management and automated WhatsApp message dispatching | ✅ Integrated |
| 📺 **YouTube Video Summaries** | Video metadata extraction, transcript analysis, and content breakdown | ✅ Integrated |
| 🎵 **Bluetooth Music Manager** | Audio playback control and Bluetooth device manager | ✅ Integrated |

---

## ⚙️ Companion Architecture

```
Era Desktop App (Electron)
    ├── Express Server (localhost:3000)
    └── Python Local Agent (127.0.0.1:8000)
```

The Electron main process manages both child services automatically. Closing the app safely terminates background helper processes.
