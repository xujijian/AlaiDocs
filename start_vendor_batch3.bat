@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ======================================
echo 厂商批次3: Vishay, Diodes, PI, Navitas, Richtek, AOS, Vicor
echo ======================================
echo.

call .venv\Scripts\activate.bat

:loop
python vendor_downloader.py "Vishay,Diodes,PI,Navitas,Richtek,AOS,Vicor"

echo.
echo ======================================
echo 3秒后自动开始下一轮...
echo 按 Ctrl+C 停止
echo ======================================
timeout /t 3 /nobreak >nul

goto loop

:end
echo.
echo 已退出
pause
