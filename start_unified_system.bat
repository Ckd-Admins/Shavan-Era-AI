@echo off
setlocal EnableDelayedExpansion
set PATH=C:\Program Files\nodejs;%PATH%
title ERA AI — Full System Launcher

:: ─── INSTANCE LOCK: Sirf ek bar chalao ──────────────────────────────────────
:: Check karein agar ERA pehle se chal rahi hai (port 3000 already in use)
netstat -ano 2>nul | findstr ":3000 " >nul 2>&1
if %errorLevel% EQU 0 (
    echo.
    echo  [ERA] Already running on port 3000. Skipping duplicate launch.
    echo  Browser mein khol rahe hain...
    ping 127.0.0.1 -n 3 >nul
    start http://127.0.0.1:3000
    exit /b 0
)

echo.
echo  ██████████████████████████████████████████████████████████
echo        ERA AI ASSISTANT — UNIFIED AUTO LAUNCHER v2.1
echo  ██████████████████████████████████████████████████████████
echo.
echo  Starting all ERA services automatically...
echo.

:: ─── Kill any stale ERA instances on these ports ───────────────────────────
echo [CLEANUP] Stopping old instances on ports 8000, 8100, 8200, 3000...
for %%P in (8000 8100 8200 3000) do (
    for /f "tokens=5" %%A in ('netstat -ano 2^>nul ^| findstr ":%%P "') do (
        taskkill /PID %%A /F >nul 2>&1
    )
)
ping 127.0.0.1 -n 3 >nul

:: ─── SERVICE 1: ERA Local Agent (Port 8000) ────────────────────────────────
echo [1/4] Launching ERA Local Agent (Port 8000)...
start "ERA Local Agent" cmd /k "title ERA Agent (8000) && cd /d d:\era_agent && d:\era_agent\.venv\Scripts\python.exe -m uvicorn api_server:app --host 127.0.0.1 --port 8000"
ping 127.0.0.1 -n 3 >nul

:: ─── SERVICE 2: ERA Bridge Gateway (Port 8100) ─────────────────────────────
echo [2/4] Launching ERA Bridge Gateway (Port 8100)...
start "ERA Bridge Gateway" cmd /k "title ERA Bridge (8100) && cd /d d:\era_bridge\era_bridge && d:\era_agent\.venv\Scripts\python.exe main.py"
ping 127.0.0.1 -n 3 >nul

:: ─── SERVICE 3: ERA Vision Agent (Port 8200) ───────────────────────────────
echo [3/4] Launching ERA Vision Agent (Port 8200)...
start "ERA Vision Agent" cmd /k "title ERA Vision (8200) && cd /d d:\era_vision\era_vision_agent_phase2\era_vision_agent && d:\era_agent\.venv\Scripts\python.exe main.py"
ping 127.0.0.1 -n 3 >nul

:: ─── SERVICE 4: ERA Voice Assistant UI (Port 3000) ─────────────────────────
echo [4/4] Launching ERA Voice Assistant UI (Port 3000)...
start "ERA Voice Assistant UI" cmd /k "title ERA UI (3000) && cd /d d:\era-voice-assistant && npm run dev"
ping 127.0.0.1 -n 5 >nul

:: ─── Open ERA in browser ────────────────────────────────────────────────────
echo.
echo  ██████████████████████████████████████████████████████████
echo   ALL 4 ERA SERVICES LAUNCHED SUCCESSFULLY!
echo.
echo   ERA Local Agent API  :  http://127.0.0.1:8000
echo   ERA Agent API Docs   :  http://127.0.0.1:8000/docs
echo   ERA Bridge Gateway   :  http://127.0.0.1:8100
echo   ERA Vision Agent     :  http://127.0.0.1:8200
echo   ERA Voice Assistant  :  http://127.0.0.1:3000
echo  ██████████████████████████████████████████████████████████
echo.
start http://127.0.0.1:3000
