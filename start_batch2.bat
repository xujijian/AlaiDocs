@echo off
chcp 65001 >nul
echo ===================================================
echo  AlaiDocs - 厂商批次2: NXP, Microchip, Renesas, MPS, ROHM
echo ===================================================

cd /d "%~dp0"
.venv\Scripts\python.exe alaidocs.py collect "%~1" --vendors NXP,Microchip,Renesas,MPS,ROHM

echo.
echo  批次2 完成
pause
