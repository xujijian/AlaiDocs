@echo off
chcp 65001 >nul
echo ========================================
echo 知识库统计信息
echo ========================================
echo.

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

python check_kb_stats.py

pause
