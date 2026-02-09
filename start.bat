@echo off
REM start.bat - Windows启动脚本
chcp 65001 >nul
title 飞书 Agent Bridge 服务

echo ============================================
echo   飞书 Agent Bridge 服务启动器
echo ============================================
echo.

REM 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python，请先安装Python 3.10+
    pause
    exit /b 1
)

REM 检查虚拟环境
if not exist "venv" (
    echo [INFO] 创建虚拟环境...
    python -m venv venv
)

REM 激活虚拟环境
call venv\Scripts\activate.bat

REM 安装依赖
if exist "requirements.txt" (
    echo [INFO] 检查依赖...
    pip install -r requirements.txt -q
)

REM 检查配置文件
if not exist "config\config.yaml" (
    echo [错误] 配置文件不存在: config\config.yaml
    echo 请复制 config\config.yaml.example 并填写配置
    pause
    exit /b 1
)

REM 检查Claude Code或OpenCode是否可用
claude --version >nul 2>&1
if errorlevel 1 (
    echo [警告] Claude Code CLI 未找到
) else (
    echo [OK] Claude Code CLI 可用
)

opencode --version >nul 2>&1
if errorlevel 1 (
    echo [警告] OpenCode CLI 未找到
) else (
    echo [OK] OpenCode CLI 可用
)

echo.
echo [INFO] 启动服务...
echo.

python src\main.py %*

pause
