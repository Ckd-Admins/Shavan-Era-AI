@echo off
title ERA AI — Auto-Start Setup (Two Methods)
echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║      ERA AI — WINDOWS STARTUP REGISTRATION          ║
echo  ╚══════════════════════════════════════════════════════╝
echo.
echo  Do tarike available hain:
echo.
echo  [1] STARTUP FOLDER (Admin nahi chahiye — Recommended)
echo      Windows login par ERA automatically start hoga.
echo.
echo  [2] TASK SCHEDULER (Admin rights chahiye)
echo      Zyada powerful — delays set kar sakte hain.
echo.
set /p CHOICE="Method chunein (1 ya 2): "

if "%CHOICE%"=="1" goto STARTUP_FOLDER
if "%CHOICE%"=="2" goto TASK_SCHEDULER
echo Invalid choice. Phir chalayein.
pause
exit /b 1

:: ─── METHOD 1: Windows Startup Folder ──────────────────────────────────────
:STARTUP_FOLDER
echo.
echo  [METHOD 1] Startup Folder mein ERA shortcut bana rahe hain...

set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "LAUNCHER=d:\era-voice-assistant\start_unified_system.bat"
set "SHORTCUT=%STARTUP%\ERA AI Assistant.bat"

:: Copy launcher bat to Startup folder
copy /Y "%LAUNCHER%" "%SHORTCUT%" >nul

if exist "%SHORTCUT%" (
    echo.
    echo  ✅ SUCCESS! ERA AI startup shortcut bana diya gaya:
    echo     %SHORTCUT%
    echo.
    echo  Ab se har baar Windows login ke baad ERA automatically
    echo  start ho jaayega.
    echo.
    echo  Agar band karna ho:
    echo    "%~dp0remove_era_autostart.bat" chalayein
) else (
    echo  [ERROR] Shortcut banana failed. Manually copy karein:
    echo  From: %LAUNCHER%
    echo  To:   %STARTUP%\
)
goto END

:: ─── METHOD 2: Task Scheduler ───────────────────────────────────────────────
:TASK_SCHEDULER
echo.
echo  [METHOD 2] Task Scheduler registration...
echo  (Admin prompt aa sakta hai — Allow karein)
echo.

set "TASK_NAME=ERA AI Assistant Auto-Start"
set "LAUNCHER=d:\era-voice-assistant\start_unified_system.bat"

schtasks /delete /tn "%TASK_NAME%" /f >nul 2>&1

schtasks /create ^
  /tn "%TASK_NAME%" ^
  /tr "cmd.exe /c \"%LAUNCHER%\"" ^
  /sc ONLOGON ^
  /rl HIGHEST ^
  /f ^
  /delay 0000:30

if %errorLevel% EQU 0 (
    echo.
    echo  ✅ SUCCESS! Task Scheduler mein ERA register ho gaya.
    echo     Trigger: Windows Login
    echo     Delay:   30 seconds
    echo.
    echo  Manual controls:
    echo    Run now : schtasks /run /tn "%TASK_NAME%"
    echo    Remove  : schtasks /delete /tn "%TASK_NAME%" /f
) else (
    echo.
    echo  [ERROR] Task Scheduler registration fail hua.
    echo  Method 1 (Startup Folder) use karein — admin nahi chahiye.
)
goto END

:END
echo.
pause
