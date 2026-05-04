@echo off
title SnapPocket Web Server

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
cloudflared tunnel --url http://localhost:5000/main_page