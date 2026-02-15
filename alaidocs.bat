@echo off
chcp 65001 >nul 2>&1
title AlaiDocs — DC-DC 知识库自动化系统
cd /d "%~dp0"

REM 尝试激活虚拟环境 (自动检测 .venv 或 venv)
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM 传入所有参数；无参数时进入交互模式
python alaidocs.py %*

pause
