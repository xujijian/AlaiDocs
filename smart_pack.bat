@echo off
chcp 65001 > nul
echo ============================================================
echo 智能文件打包器 - NotebookLM助手
echo ============================================================
echo 功能:
echo   1. 自动检测中文/英文查询
echo   2. 中文查询自动翻译成英文
echo   3. 混合检索: 关键词 + 语义相似
echo   4. 智能去重和多样性选择
echo   5. 一键打包供 NotebookLM 使用
echo.
echo 依赖:
echo   pip install deep-translator sentence-transformers faiss-cpu
echo.
echo ============================================================
echo.

cd D:\E-BOOK\axis-SQLite
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    cd D:\E-BOOK\axdcdcpdf
    call .venv\Scripts\activate.bat
)

python D:\E-BOOK\axdcdcpdf\smart_pack.py

echo.
echo 按任意键退出...
pause > nul
