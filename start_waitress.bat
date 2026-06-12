@echo off
setlocal

cd /d "%~dp0"
python -m waitress --listen=127.0.0.1:8000 run:app

pause
