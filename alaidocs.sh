#!/usr/bin/env bash
# AlaiDocs — DC-DC 知识库自动化系统
cd "$(dirname "$0")"

# 激活虚拟环境
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
elif [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

python3 alaidocs.py "$@"
