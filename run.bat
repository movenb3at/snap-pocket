@echo off
title SnapPocket Web Server
cd /d "%~dp0"

echo Running nvidia-smi...
nvidia-smi

echo Before starting, make sure to run Memurai and Redis servers.
timeout /t 2 >nul
echo Running SnapPocket Web Server...
timeout /t 2 >nul

echo Starting Celery Worker...
start "Celery Worker" cmd /k "celery -A app.celery worker --pool=solo -l info"

timeout /t 3 >nul

echo Starting Flask server...
start "Flask Server" cmd /k "python app.py"

timeout /t 3 >nul

echo Starting Cloudflare Tunnel...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_tunnel.ps1"
if errorlevel 1 (
    echo Failed to start the Cloudflare Tunnel.
    pause
    exit /b 1
)
