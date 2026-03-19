@echo off
REM Feishu Agent Bridge Startup Script
chcp 65001 >nul 2>&1
title Feishu Agent Bridge

REM Get the directory where the script is located
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo ============================================
echo   Feishu Agent Bridge Service
echo ============================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

REM Check virtual environment
if not exist "venv" (
    echo [INFO] Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install dependencies
if exist "requirements.txt" (
    echo [INFO] Checking dependencies...
    pip install -r requirements.txt -q
)

REM Check config file (support both .yaml and .yml)
set CONFIG_FOUND=0
if exist "config\config.yaml" (
    set CONFIG_FOUND=1
)
if exist "config\config.yml" (
    set CONFIG_FOUND=1
)

if "%CONFIG_FOUND%"=="0" (
    echo [ERROR] Config file not found: config\config.yaml or config\config.yml
    echo Please copy config\config.yaml.example to config\config.yaml
    pause
    exit /b 1
)

REM Check Claude Code
claude --version >nul 2>&1
if errorlevel 1 (
    echo [WARN] Claude Code CLI not found
) else (
    echo [OK] Claude Code CLI found
)

REM Check OpenCode
opencode --version >nul 2>&1
if errorlevel 1 (
    echo [WARN] OpenCode CLI not found
) else (
    echo [OK] OpenCode CLI found
)

echo.
echo [INFO] Starting service...
echo.

python src\main.py %*

pause
