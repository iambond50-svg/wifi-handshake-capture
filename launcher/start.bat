@echo off
chcp 65001 >nul
title WiFi Capture Launcher

echo.
echo  WiFi Capture Launcher
echo  ======================
echo.

:: 检查 Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3
    pause
    exit /b 1
)

:: 运行启动器
cd /d "%~dp0"
python launcher.py start

pause
