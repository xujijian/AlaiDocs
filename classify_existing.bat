@echo off
chcp 65001 >nul
REM Classify Existing PDFs

echo ========================================
echo Batch Classify Existing PDFs
echo ========================================
echo.
echo Source:      downloads_continuous
echo Destination: downloads_classified
echo.

REM Activate virtual environment
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

python integrated_downloader_classifier.py ^
    --download-dir "./downloads_continuous" ^
    --classified-dir "./downloads_classified" ^
    --mode classify-only

echo.
echo ========================================
echo Classification Complete
echo ========================================
pause
