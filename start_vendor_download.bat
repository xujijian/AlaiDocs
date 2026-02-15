@echo off
chcp 65001 >nul
echo ========================================
echo 厂商官网电源资料下载器
echo ========================================
echo 目标: 17个知名电源芯片厂商官网
echo 策略: 直接从官网下载，质量最高
echo ========================================
echo.
echo 厂商列表:
echo   TI, ADI, ST, Infineon, onsemi, NXP
echo   Microchip, Renesas, MPS, ROHM, Vishay
echo   Diodes, PI, Navitas, Richtek, AOS, Vicor
echo.
echo 按任意键开始...
pause >nul

REM 激活虚拟环境
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

echo.
echo 开始下载...
echo 提示: 按 Ctrl+C 可随时停止
echo.

python vendor_downloader.py

echo.
echo ========================================
pause
