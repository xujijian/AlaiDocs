@echo off
chcp 65001 >nul
echo ========================================
echo PDF文件差异分析
echo ========================================
echo.

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

python analyze_pdfs.py

pause
