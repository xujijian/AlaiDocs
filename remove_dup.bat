@echo off
chcp 65001 >nul
echo ========================================
echo 删除重复PDF文件
echo ========================================
echo 这是一个危险操作，请确认！
echo.

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

python remove_duplicates.py

pause
