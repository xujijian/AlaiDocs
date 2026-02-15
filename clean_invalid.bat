@echo off
chcp 65001 >nul
echo ========================================
echo 清理无效 PDF 文件
echo ========================================
echo.

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

python clean_invalid_pdfs.py

pause
