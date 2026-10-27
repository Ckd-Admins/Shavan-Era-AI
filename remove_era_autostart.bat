@echo off
title ERA AI — Remove Auto-Start
echo.
echo  ========================================================
echo         ERA AI — STARTUP REMOVAL TOOL
echo  ========================================================
echo.

net session >nul 2>&1
if %errorLevel% NEQ 0 (
    echo  [ERROR] Admin rights required!
    echo  Right-click karein aur "Run as Administrator" select karein.
    pause
    exit /b 1
)

set "TASK_NAME=ERA AI Assistant Auto-Start"
schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

if %errorLevel% EQU 0 (
    echo  [SUCCESS] ERA AI auto-start successfully remove ho gaya.
) else (
    echo  [INFO] Koi registered task nahi mila (already removed tha).
)
echo.
pause
