@echo off
chcp 65001 >nul
echo ========================================
echo 关键词和厂商探索器
echo 使用 Gemini 自动生成搜索策略
echo ========================================
echo.

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

python keyword_explorer.py

echo.
echo ========================================
echo 探索完成！
echo.
echo 接下来请运行以下命令开始批量下载:
echo   终端1: .\start_vendor_batch1.bat
echo   终端2: .\start_vendor_batch2.bat  
echo   终端3: .\start_vendor_batch3.bat
echo ========================================
pause
