#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识库入库包装脚本 - 临时方案：等待 ingest.py 支持排除参数前使用
直接调用 ingest.py，但提醒用户可以手动排除 Trash 目录
"""

import sys
import subprocess
from pathlib import Path

# 配置
AXIS_SQLITE_DIR = Path(r"D:\E-BOOK\axis-SQLite")
INGEST_SCRIPT = AXIS_SQLITE_DIR / "ingest.py"
ROOT_DIR = Path(r"D:\E-BOOK\axis-dcdc-pdf")

def main():
    print("="*60)
    print("知识库入库脚本")
    print("="*60)
    print(f"监控目录: {ROOT_DIR}")
    print(f"知识库: {AXIS_SQLITE_DIR}")
    
    # 检查并统计 Trash 目录
    trash_dir = ROOT_DIR / "Trash"
    if trash_dir.exists():
        trash_pdfs = list(trash_dir.rglob("*.pdf"))
        if trash_pdfs:
            print(f"⚠️  注意: Trash 目录有 {len(trash_pdfs)} 个文件将被跳过")
    
    print("")
    
    # 检查 ingest.py 是否存在
    if not INGEST_SCRIPT.exists():
        print(f"❌ 找不到 {INGEST_SCRIPT}")
        sys.exit(1)
    
    # 构建命令 - 尝试使用 --exclude-pattern 参数
    cmd = [
        sys.executable,
        str(INGEST_SCRIPT),
        "--root", str(ROOT_DIR),
        "--only-new",
        "--workers", "4"
    ]
    
    # 尝试排除 Trash 和 Unknown（如果 ingest.py 支持）
    cmd.extend(["--exclude-pattern", "Trash/**", "Unknown/**"])
    
    # 传递额外参数（如 --rebuild）
    if len(sys.argv) > 1:
        cmd.extend(sys.argv[1:])
    
    print(f"执行: python ingest.py (排除 Trash/Unknown)")
    print("")
    
    # 调用 ingest.py
    result = subprocess.run(cmd, cwd=AXIS_SQLITE_DIR)
    
    # 如果失败，可能是不支持 --exclude-pattern，尝试不带该参数
    if result.returncode != 0:
        print("")
        print("⚠️  带排除参数失败，尝试不带排除参数...")
        cmd_no_exclude = [
            sys.executable,
            str(INGEST_SCRIPT),
            "--root", str(ROOT_DIR),
            "--only-new",
            "--workers", "4"
        ]
        if len(sys.argv) > 1:
            cmd_no_exclude.extend(sys.argv[1:])
        result = subprocess.run(cmd_no_exclude, cwd=AXIS_SQLITE_DIR)
    
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()

