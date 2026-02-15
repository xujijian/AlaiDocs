@echo off
chcp 65001 >nul
echo ========================================
echo 知识库监控进程 (KB Watcher)
echo ========================================
echo 监控目录: D:\E-BOOK\axis-dcdc-pdf\
echo 知识库: D:\E-BOOK\axis-SQLite\
echo.

cd D:\E-BOOK\axis-SQLite

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

echo 每 60 秒检查一次新文件...
echo.

REM 检查是否传入参数
set EXTRA_ARGS=
if "%1"=="--rebuild" (
    echo ⚠️  重建模式：将清空并重建知识库
    set EXTRA_ARGS=--rebuild
    pause
)

:loop
REM 只清理 Trash 目录（完全无效的文件）
REM ⚠️ 不再删除 Unknown 目录，避免误删低置信度文件
if exist "D:\E-BOOK\axis-dcdc-pdf\Trash" (
    echo 清理 Trash 目录...
    rd /s /q "D:\E-BOOK\axis-dcdc-pdf\Trash"
)
echo.

REM 运行知识库入库
python ingest.py --root "D:\E-BOOK\axis-dcdc-pdf" --only-new --workers 4 %EXTRA_ARGS%
echo.
echo 等待 60 秒...
timeout /t 60 /nobreak >nul
goto loop
