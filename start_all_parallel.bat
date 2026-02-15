@echo off
chcp 65001 >nul
echo ========================================
echo 并行启动三个进程
echo ========================================
echo.
echo 将启动三个独立窗口:
echo   1. 下载进程 (持续搜索下载)
echo   2. 分类监控 (实时分类新文件)
echo   3. 知识库监控 (定期更新知识库)
echo.
echo 按任意键开始...
pause >nul

echo.
echo [1/3] 启动下载进程...
start "下载器" cmd /k "cd /d %~dp0 && start_download_only.bat"
timeout /t 2 /nobreak >nul

echo [2/3] 启动分类监控...
start "分类器" cmd /k "cd /d %~dp0 && start_classify_watch.bat"
timeout /t 2 /nobreak >nul

echo [3/3] 启动知识库监控...
start "知识库" cmd /k "cd /d %~dp0 && start_kb_watch.bat"

echo.
echo ========================================
echo ✅ 所有进程已启动！
echo ========================================
echo.
echo 提示:
echo   - 三个独立窗口同时运行
echo   - 关闭任一窗口即停止该进程
echo   - 建议: 先运行一段时间观察效果
echo.

pause
