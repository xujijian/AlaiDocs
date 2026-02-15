#!/bin/bash
# DC-DC Datasheet 下载工具 - Linux/macOS 启动脚本
# 使用方法: chmod +x start_unix.sh && ./start_unix.sh

set -e

echo "========================================"
echo "  DC-DC Datasheet 下载工具"
echo "========================================"
echo

# 检查 Python 是否安装
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到 Python3！请先安装 Python 3.10+"
    exit 1
fi

echo "[信息] Python 版本: $(python3 --version)"

# 检查虚拟环境是否存在
if [ ! -f ".venv/bin/activate" ]; then
    echo "[警告] 虚拟环境不存在，正在创建..."
    python3 -m venv .venv
    echo "[成功] 虚拟环境已创建"
fi

# 激活虚拟环境
echo "[信息] 激活虚拟环境..."
source .venv/bin/activate

# 检查依赖是否安装
if ! python -c "import requests, duckduckgo_search" &> /dev/null; then
    echo "[警告] 依赖未安装，正在安装..."
    pip install -r requirements.txt
    echo "[成功] 依赖已安装"
fi

echo
echo "========================================"
echo "  选择操作模式"
echo "========================================"
echo "1. 快速测试（下载 5 个结果）"
echo "2. 使用示例查询文件"
echo "3. 自定义查询"
echo "4. 查看帮助"
echo "5. 运行快速测试脚本"
echo "6. 退出"
echo

read -p "请选择 (1-6): " choice

case $choice in
    1)
        echo
        echo "[模式] 快速测试"
        python ddg_fetcher.py --query "TI buck converter datasheet" --max-results 5 --debug --out test_downloads
        ;;
    2)
        echo
        if [ ! -f "queries_example.txt" ]; then
            echo "[错误] queries_example.txt 不存在！"
            exit 1
        fi
        echo "[模式] 使用示例查询文件"
        python ddg_fetcher.py --queries queries_example.txt --max-results 10 --out downloads
        ;;
    3)
        echo
        echo "[模式] 自定义查询"
        read -p "请输入查询内容: " custom_query
        python ddg_fetcher.py --query "$custom_query" --max-results 20 --out downloads
        ;;
    4)
        echo
        python ddg_fetcher.py --help
        ;;
    5)
        echo
        python test_quick.py
        ;;
    6)
        echo "再见！"
        exit 0
        ;;
    *)
        echo "[错误] 无效的选择！"
        exit 1
        ;;
esac

echo
echo "========================================"
echo "  操作完成"
echo "========================================"
echo
echo "查看下载结果:"
echo "  - 文件: downloads/ 或 test_downloads/"
echo "  - 日志: downloads/results.jsonl"
echo "  - 汇总: downloads/summary.csv"
echo
