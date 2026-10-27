# Era Voice Assistant + Python Local Agent Setup and Testing

This document explains how to run the two connected systems and verify that the voice assistant uses the Python local agent correctly.

## What is included

- `era-voice-assistant/` — your voice assistant frontend and backend server.
- `era_agent/era_agent/` — your Python local agent with a FastAPI HTTP server.
- `era-voice-assistant/start_unified_system.bat` — a batch file that starts both services together.

## Prerequisites

1. Windows machine.
2. Python 3.9+ installed and available as `python`.
3. Node.js and npm installed.
4. VS Code opened with the multi-root workspace containing both `era-voice-assistant` and `era_agent`.

## Recommended VS Code setup

1. Open the workspace in VS Code.
2. In the Explorer, confirm both folders are visible:
   - `era-voice-assistant`
   - `era_agent`
3. Select the Python interpreter for `era_agent/era_agent` if using Python features.
4. Open an integrated terminal in VS Code.

## Run both systems together

### Option 1: Use the unified startup batch file

1. Open a terminal in `era-voice-assistant`.
2. Run:

```powershell
.\start_unified_system.bat
```

This starts:
- Era Python Local Agent API on `http://127.0.0.1:8000`
- Era Voice Assistant server on `http://localhost:3000`

### Option 2: Start services separately

#### Start the Python local agent

1. Open a terminal in `era_agent\era_agent`.
2. Run:

```powershell
python api_server.py
```

or use:

```powershell
.\run_api.bat
```

3. Confirm the agent is online by visiting:

- `http://127.0.0.1:8000/status`
- `http://127.0.0.1:8000/docs`

#### Start the voice assistant

1. Open a terminal in `era-voice-assistant`.
2. Install dependencies if needed:

```powershell
npm install
```

3. Run the app:

```powershell
npm run dev
```

4. Open the web UI at:

- `http://localhost:3000`

## Verify the connection

### Step 1: Confirm the Python agent is reachable

In a browser or terminal, call:

```powershell
curl http://127.0.0.1:8000/status
```

Expected JSON result:

```json
{
  "status": "online",
  "agent": "Era Agent for Windows",
  "version": "1.1.0",
  "available_commands": 13
}
```

### Step 2: Confirm the voice assistant backend can call the agent

Run the voice assistant app, then use the UI and speak or type a command such as:

- "Open Notepad"
- "Open Camera"
- "Open Chrome"
- "Search for a file"
- "Lock PC"

### Step 3: Watch for backend logs

In the `era-voice-assistant` terminal, the backend should log calls like:

- `Executing tool on companion agent: open_notepad`
- `Executing tool on companion agent: open_camera`
- `Invoking command 'open_notepad' on Python Agent`

### Step 4: Test direct agent execution

To verify the Python agent commands independently, run:

```powershell
curl -X POST http://127.0.0.1:8000/execute -H "Content-Type: application/json" -d "{\"command\": \"open_notepad\"}"
```

If that works, the local agent is healthy and ready for the voice assistant.

## What to expect in VS Code

1. Open the integrated terminal in the `era-voice-assistant` folder.
2. Run `start_unified_system.bat` or the two commands above.
3. Watch both terminals:
   - Python agent terminal should say it is listening on `127.0.0.1:8000`.
   - Voice assistant terminal should say `Server running on http://localhost:3000`.
4. Open `http://localhost:3000` in your browser.
5. Speak a command and observe the web app response.

## How to know the integration is working

- The voice app responds and acknowledges your command.
- Windows applications open on your laptop (Notepad, Camera, Calculator, Chrome, etc.).
- The Python local agent API logs the command execution.
- The voice assistant backend confirms tool execution and returns success.

## If something fails

- Confirm `http://127.0.0.1:8000/status` returns `online`.
- Confirm `http://localhost:3000` loads successfully.
- Check VS Code terminal for error messages.
- If an app does not launch, verify the command name matches the Python agent registry.

## Summary

Use `era-voice-assistant/start_unified_system.bat` as the simplest startup method. If you want to test manually, start the Python agent with `python api_server.py` and the voice assistant with `npm run dev`. Then confirm the agent status and speak commands that trigger the local agent.
