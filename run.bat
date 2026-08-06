@echo off
setlocal EnableExtensions EnableDelayedExpansion
title SnapPocket Web Server
cd /d "%~dp0"

if not defined SNAP_POCKET_ADMIN_PASSWORD (
    for /f "delims=" %%P in ('python -c "import secrets; print(secrets.token_urlsafe(12))"') do set "SNAP_POCKET_ADMIN_PASSWORD=%%P"
    if not defined SNAP_POCKET_ADMIN_PASSWORD (
        echo Failed to generate a temporary admin password.
        pause
        exit /b 1
    )
    echo Temporary admin password: !SNAP_POCKET_ADMIN_PASSWORD!
) else (
    echo Using the admin password from SNAP_POCKET_ADMIN_PASSWORD.
)

if not defined SNAP_POCKET_SECRET_KEY (
    for /f "delims=" %%S in ('python -c "import secrets; print(secrets.token_hex(32))"') do set "SNAP_POCKET_SECRET_KEY=%%S"
)

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
