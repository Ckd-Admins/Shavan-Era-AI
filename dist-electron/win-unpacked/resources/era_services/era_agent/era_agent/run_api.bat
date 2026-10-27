@echo off
title Era Agent API Server
echo ===================================================
echo Starting Era Agent API Server...
echo API URL: http://127.0.0.1:8000
echo Swagger Docs: http://127.0.0.1:8000/docs
echo ===================================================
echo.

cd /d "%~dp0"

if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
)

python api_server.py

pause
