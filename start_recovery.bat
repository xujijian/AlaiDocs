@echo off
chcp 65001 >nul
echo ========================================
echo 快速恢复下载器
echo ========================================
echo 目标: 快速恢复丢失的 2000+ 个文件
echo 策略: 36 个高优先级搜索查询
echo ========================================
echo.

REM 激活虚拟环境
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

echo 开始恢复下载...
echo 提示: 按 Ctrl+C 可随时停止
echo.

python recovery_downloader.py

echo.
echo ========================================
echo 恢复下载已完成/停止
echo ========================================
pause
