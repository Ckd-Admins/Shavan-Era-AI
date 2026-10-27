@echo off
title ERA Browser Test Launcher
echo ============================================
echo  ERA Voice Assistant - Browser Test Mode
echo ============================================

echo [1/5] Killing old ERA processes on ports 3000, 8000, 8100, 8200...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":3000 :8000 :8100 :8200"') do (
    if not "%%a"=="0" taskkill /PID %%a /F >nul 2>&1
)
ping 127.0.0.1 -n 3 >nul

echo [2/5] Starting ERA Agent (port 8000)...
start "ERA Agent" /min cmd /c "cd /d d:\era_agent && d:\era_agent\.venv\Scripts\python.exe -m uvicorn api_server:app --host 127.0.0.1 --port 8000 --log-level warning"

echo [3/5] Starting ERA Bridge (port 8100)...
start "ERA Bridge" /min cmd /c "cd /d d:\era_bridge\era_bridge && d:\era_agent\.venv\Scripts\python.exe main.py"

echo [4/5] Starting ERA Vision (port 8200)...
start "ERA Vision" /min cmd /c "cd /d d:\era_vision\era_vision_agent_phase2\era_vision_agent && d:\era_agent\.venv\Scripts\python.exe main.py"

echo Waiting 12 seconds for agents to start...
ping 127.0.0.1 -n 13 >nul

echo [5/5] Starting ERA Web UI (port 3000)...
start "ERA Web Server" cmd /k "cd /d d:\era-voice-assistant && npx tsx server.ts"

echo Waiting 10 seconds for web server to start...
ping 127.0.0.1 -n 11 >nul

echo Opening browser at http://127.0.0.1:3000 ...
start "" "http://127.0.0.1:3000"

echo.
echo ============================================
echo  ERA is running! Browser should open now.
echo  If browser doesnt load, wait 5 more secs
echo  and manually go to: http://127.0.0.1:3000
echo ============================================
echo.
echo Press any key to close this launcher...
pause >nul
