@echo off
chcp 65001 >nul
echo ===================================================
echo  AlaiDocs - 厂商批次1: TI, ADI, ST, Infineon, onsemi
echo ===================================================

cd /d "%~dp0"
.venv\Scripts\python.exe alaidocs.py collect "%~1" --vendors TI,ADI,ST,Infineon,onsemi

echo.
echo  批次1 完成
pause
