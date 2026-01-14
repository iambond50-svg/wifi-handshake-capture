@echo off
chcp 65001 >nul
title WiFi Capture - Stop

cd /d "%~dp0"
python launcher.py stop

pause
