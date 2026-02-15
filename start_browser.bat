@echo off
REM DC-DC Datasheet 自动下载工具（浏览器版）启动脚本
REM Windows 批处理文件

echo ============================================
echo DC-DC Datasheet 下载工具（浏览器版）
echo ============================================
echo.

REM 检查虚拟环境
if not exist ".venv\Scripts\activate.bat" (
    echo [错误] 未找到虚拟环境！
    echo 请先运行: python -m venv .venv
    pause
    exit /b 1
)

REM 激活虚拟环境
call .venv\Scripts\activate.bat

REM 检查依赖
echo [1/2] 检查依赖...
python -c "import selenium" 2>nul
if %errorlevel% neq 0 (
    echo [提示] 安装浏览器版依赖...
    pip install -r requirements_browser.txt
)

REM 运行程序
echo [2/2] 启动程序...
echo.
python ddg_fetcher_browser.py %*

pause
