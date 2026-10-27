@echo off
REM ERA Voice Assistant - Auto Start Script
REM Ye script Windows login par automatically ERA start kar deta hai

title ERA Voice Assistant - Launching...
cd /d "d:\era-voice-assistant"

REM System settle hone ke liye 5 second wait
timeout /t 5 /nobreak >nul

REM ERA Electron app start karo (npm run electron:start)
echo [ERA] Launching ERA Voice Assistant...
call "d:\era-voice-assistant\node_modules\.bin\electron.cmd" "d:\era-voice-assistant\electron\main.cjs"
