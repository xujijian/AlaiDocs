@echo off
chcp 65001 >nul
REM Integrated Download and Classification System Launcher

echo ========================================
echo Integrated System
echo ========================================
echo.
echo Features:
echo   1. Auto generate keywords (Gemini)
echo   2. Search and download PDFs (Google/DuckDuckGo)
echo   3. Auto classify (4-dimension)
echo   4. Auto update knowledge base (axis-SQLite)
echo.
echo Directories:
echo   downloads_continuous/ - Download and classified folder
echo   (Compatible with axis-SQLite knowledge base)
echo.

REM Check virtual environment
if exist ".venv\Scripts\activate.bat" (
    echo [1/3] Activating virtual environment...
    call .venv\Scripts\activate.bat
) else (
    echo [WARNING] Virtual environment not found
)

echo.
echo [2/3] Checking dependencies...
python -c "import pypdf; print('[OK] pypdf installed')" 2>nul
if %errorlevel% neq 0 (
    echo [INSTALL] Installing classifier dependencies...
    pip install pypdf pdfminer.six
)

echo.
echo [3/3] Starting system...
echo.
echo ========================================
echo.

python integrated_downloader_classifier.py ^
    --config "./integrated_config.json" ^
    --mode integrated

echo.
echo ========================================
echo System stopped
echo ========================================
pause
