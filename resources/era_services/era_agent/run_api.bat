@echo off
title ERA Agent v3.1.0 — Mission Engine + Gmail + WhatsApp
echo =====================================================
echo   ERA Local Agent API Server v3.1.0
echo   URL:  http://127.0.0.1:8000
echo   Docs: http://127.0.0.1:8000/docs
echo =====================================================
echo.

cd /d "%~dp0"

:: Use exact Python 3.14 executable that has all google-auth packages
set PYTHON=C:\Users\MSI\AppData\Local\Python\pythoncore-3.14-64\python.exe

if not exist "%PYTHON%" (
    echo [WARN] Exact Python not found at %PYTHON%, falling back to system python
    set PYTHON=python
)

echo [OK] Using Python: %PYTHON%
echo [START] Launching ERA Agent API v3.1.0...
echo.

%PYTHON% -m uvicorn api_server:app --host 127.0.0.1 --port 8000

pause
