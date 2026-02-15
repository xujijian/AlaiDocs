@echo off
REM DC-DC Continuous Search System - Windows Startup Script
REM 
REM Usage:
REM   start_continuous.bat              - Start with default config
REM   start_continuous.bat --rounds 10  - Run 10 rounds then stop
REM   start_continuous.bat --debug      - Enable debug mode

chcp 65001 >nul 2>&1

echo ========================================
echo DC-DC Continuous Search System
echo ========================================
echo.

REM Check Python environment
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found, please install Python 3.10+
    pause
    exit /b 1
)

REM Check virtual environment
if exist ".venv\Scripts\activate.bat" (
    echo [INFO] Activating virtual environment...
    call .venv\Scripts\activate.bat
) else (
    echo [WARN] Virtual environment not found, using system Python
)

REM Check dependencies
echo [INFO] Checking dependencies...
python -c "import selenium" >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARN] selenium not found, installing...
    pip install selenium webdriver-manager
)

python -c "from duckduckgo_search import DDGS" >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARN] duckduckgo-search not found, installing...
    pip install duckduckgo-search
)

REM Check config file
if not exist "continuous_search_config.json" (
    echo [WARN] Config file not found, will use default config
)

REM Create output directory
if not exist "downloads_continuous" (
    mkdir downloads_continuous
)

echo.
echo [INFO] Starting continuous search system...
echo [INFO] Output directory: downloads_continuous\
echo [INFO] Keywords database: keywords.json
echo [INFO] Search method: Chrome browser (required to avoid request blocking)
echo.
echo ========================================
echo Important Notes:
echo ========================================
echo.
echo 1. If Google Gemini login is required:
echo    - Browser will open automatically
echo    - Program will AUTO-DETECT when you finish login
echo    - NO NEED to press Enter manually
echo    - Just complete the login process
echo.
echo 2. Press Ctrl+C to stop anytime
echo.
echo ========================================
echo.

REM 运行主程序（使用集成版本）
python integrated_searcher.py ^
    --output downloads_continuous ^
    --keywords-db keywords.json ^
    --config continuous_search_config.json ^
    %*

echo.
echo ========================================
echo Program exited
echo ========================================
pause
