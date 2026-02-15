#!/bin/bash
# DC-DC 持续搜索下载系统 - Unix/Linux/macOS 启动脚本
#
# 使用方法:
#   ./start_continuous.sh              - 使用默认配置启动
#   ./start_continuous.sh --rounds 10  - 运行 10 轮后停止
#   ./start_continuous.sh --debug      - 启用调试模式

echo "========================================"
echo "DC-DC 持续搜索下载系统"
echo "========================================"
echo ""

# 检查 Python 环境
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到 Python3，请先安装 Python 3.10+"
    exit 1
fi

# 检查虚拟环境
if [ -f ".venv/bin/activate" ]; then
    echo "[信息] 激活虚拟环境..."
    source .venv/bin/activate
else
    echo "[警告] 未找到虚拟环境，使用系统 Python"
fi

# 检查依赖
echo "[信息] 检查依赖..."
python3 -c "import selenium" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "[警告] 缺少 selenium，正在安装..."
    pip install selenium webdriver-manager
fi

python3 -c "from duckduckgo_search import DDGS" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "[警告] 缺少 duckduckgo-search，正在安装..."
    pip install duckduckgo-search
fi

# 检查配置文件
if [ ! -f "continuous_search_config.json" ]; then
    echo "[警告] 未找到配置文件，将使用默认配置"
fi

# 创建输出目录
if [ ! -d "downloads_continuous" ]; then
    mkdir -p downloads_continuous
fi

echo ""
echo "[信息] 启动持续搜索系统..."
echo "[信息] 输出目录: downloads_continuous/"
echo "[信息] 关键词数据库: keywords.json"
echo "[信息] 按 Ctrl+C 可随时停止"
echo ""
echo "========================================"
echo ""

# 运行主程序（使用集成版本）
python3 integrated_searcher.py \
    --output downloads_continuous \
    --keywords-db keywords.json \
    --config continuous_search_config.json \
    "$@"

echo ""
echo "========================================"
echo "程序已退出"
echo "========================================"
