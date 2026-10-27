@echo off
setlocal EnableDelayedExpansion
set PATH=C:\Program Files\nodejs;%PATH%
title ERA AI — Desktop App Launcher

echo.
echo  ========================================================
echo          ERA AI DESKTOP ASSISTANT LAUNCHER
echo  ========================================================
echo.

:: ─── Kill stale instances ───────────────────────────────────────────────────
for %%P in (8000 8100 8200 3000) do (
    for /f "tokens=5" %%A in ('netstat -ano 2^>nul ^| findstr ":%%P "') do (
        taskkill /PID %%A /F >nul 2>&1
    )
)
timeout /t 2 /nobreak >nul

:: ─── ERA Local Agent (background, no window) ────────────────────────────────
echo [1/4] Starting ERA Local Agent (Port 8000)...
start "ERA Local Agent" cmd /c "cd /d d:\era_agent && d:\era_agent\.venv\Scripts\python.exe -m uvicorn api_server:app --host 127.0.0.1 --port 8000"
ping 127.0.0.1 -n 3 >nul

:: ─── ERA Bridge (background) ─────────────────────────────────────────────────
echo [2/4] Starting ERA Bridge Gateway (Port 8100)...
start "ERA Bridge" cmd /c "cd /d d:\era_bridge\era_bridge && d:\era_agent\.venv\Scripts\python.exe main.py"
ping 127.0.0.1 -n 3 >nul

:: ─── ERA Vision (background) ─────────────────────────────────────────────────
echo [3/4] Starting ERA Vision Agent (Port 8200)...
start "ERA Vision" cmd /c "cd /d d:\era_vision\era_vision_agent_phase2\era_vision_agent && d:\era_agent\.venv\Scripts\python.exe main.py"
ping 127.0.0.1 -n 3 >nul

:: ─── ERA Desktop Electron App ────────────────────────────────────────────────
echo [4/4] Launching ERA Desktop Electron App...
cd /d d:\era-voice-assistant
npm run electron:start

echo.
echo ERA AI Desktop has closed.
pause
