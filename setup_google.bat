@echo off
chcp 65001 >nul
REM Google Search Engine Setup Script

echo ========================================
echo Google Search Engine Setup Wizard
echo ========================================
echo.

REM Check virtual environment
if exist ".venv\Scripts\activate.bat" (
    echo [1/4] Activating virtual environment...
    call .venv\Scripts\activate.bat
) else (
    echo [WARNING] Virtual environment not found, using system Python
)

echo.
echo [2/4] Installing Google Search dependencies...
pip install googlesearch-python
if %errorlevel% neq 0 (
    echo [ERROR] Installation failed, please check network connection
    pause
    exit /b 1
)

echo.
echo [3/4] Verifying installation...
python -c "import googlesearch; print('[OK] googlesearch-python installed')"
if %errorlevel% neq 0 (
    echo [ERROR] Import failed
    pause
    exit /b 1
)

echo.
echo [4/4] Running tests...
echo.
python test_google_fetcher.py
if %errorlevel% neq 0 (
    echo.
    echo [WARNING] Tests did not fully pass, but this may be normal
    echo           (e.g., cannot access Google, network issues, etc.)
)

echo.
echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo You can now use Google Search:
echo   1. Run continuous search: start_continuous.bat
echo   2. Manual test: python google_fetcher.py "query"
echo.
echo Detailed guide: GOOGLE_SEARCH_GUIDE.md
echo.
pause
