@echo off
title VPN / Proxy Manager
color 0B
cd /d "%~dp0"
python main.py %*
pause
