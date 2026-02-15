@echo off
chcp 65001 >nul
echo ========================================
echo 检查未入库PDF文件
echo ========================================
echo.

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

python check_missing_pdfs.py

pause
