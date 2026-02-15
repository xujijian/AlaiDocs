@echo off
chcp 65001 >nul
echo ===================================================
echo  AlaiDocs - 全流程并行启动
echo  采集 + 分类 + 建库 (三批次并行)
echo ===================================================
echo.

set QUERY=%~1
if "%QUERY%"=="" (
    set /p QUERY="请输入搜索主题 (如 buck converter): "
)

echo  主题: %QUERY%
echo.
echo  正在启动三个并行窗口...
echo  - 批次1: TI, ADI, ST, Infineon, onsemi
echo  - 批次2: NXP, Microchip, Renesas, MPS, ROHM
echo  - 批次3: Vishay, Diodes, PI, Navitas, Richtek, AOS, Vicor
echo.

start "AlaiDocs Batch 1" cmd /c "start_batch1.bat "%QUERY%""
timeout /t 3 /nobreak >nul
start "AlaiDocs Batch 2" cmd /c "start_batch2.bat "%QUERY%""
timeout /t 3 /nobreak >nul
start "AlaiDocs Batch 3" cmd /c "start_batch3.bat "%QUERY%""

echo  三个批次已启动！
echo.
echo  全部完成后，运行以下命令完成后续处理:
echo    python alaidocs.py classify
echo    python alaidocs.py build-kb
echo    python alaidocs.py pack "你的查询"
echo.
pause
