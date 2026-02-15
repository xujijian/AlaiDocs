@echo off
chcp 65001 >nul
echo ========================================
echo 检查知识库文档来源
echo ========================================
echo.

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

python check_kb_sources.py

pause
