@echo off
chcp 65001 >nul
echo ===================================================
echo  AlaiDocs - 厂商批次3: Vishay, Diodes, PI, Navitas, Richtek, AOS, Vicor
echo ===================================================

cd /d "%~dp0"
.venv\Scripts\python.exe alaidocs.py collect "%~1" --vendors Vishay,Diodes,PI,Navitas,Richtek,AOS,Vicor

echo.
echo  批次3 完成
pause
