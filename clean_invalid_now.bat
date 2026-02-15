@echo off
chcp 65001 > nul
echo ============================================================
echo 清理无效PDF文件
echo ============================================================
echo.

call .venv\Scripts\activate.bat
python clean_invalid_now.py

echo.
echo 按任意键退出...
pause > nul
