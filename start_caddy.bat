@echo off
setlocal

cd /d C:\caddy
caddy.exe run --config Caddyfile

pause
