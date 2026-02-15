@echo off
chcp 65001 >nul
echo ========================================
echo 分类监控进程 (Classify Watcher)
echo ========================================
echo 监控目录: downloads_continuous/
echo 分类目录: D:\E-BOOK\axis-dcdc-pdf\
echo.

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

echo 检查依赖...
python -c "import watchdog" 2>nul || (
    echo 安装 watchdog...
    pip install watchdog
)

python classify_watcher.py

pause
