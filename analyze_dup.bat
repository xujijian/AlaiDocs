@echo off
chcp 65001 >nul
echo ========================================
echo 文件重复分析
echo ========================================
echo 这可能需要几分钟...
echo.

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

python analyze_duplicates.py

pause
