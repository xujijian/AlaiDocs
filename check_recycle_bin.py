#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从回收站恢复文件"""

import os
import shutil
from pathlib import Path

# Windows 回收站路径
recycle_bin = Path(r"C:\$Recycle.Bin")

print("检查回收站...")
print(f"回收站路径: {recycle_bin}")

if recycle_bin.exists():
    # 统计回收站中的 PDF
    pdf_count = 0
    for root, dirs, files in os.walk(recycle_bin):
        for file in files:
            if file.lower().endswith('.pdf'):
                pdf_count += 1
    
    print(f"\n找到 {pdf_count} 个 PDF 文件在回收站")
    
    if pdf_count > 0:
        print("\n⚠️  注意：Windows 回收站文件需要手动恢复")
        print("操作步骤：")
        print("1. 打开回收站")
        print("2. 按修改日期排序")
        print("3. 选择最近删除的 PDF 文件")
        print("4. 右键 -> 还原")
else:
    print("❌ 无法访问回收站")

# 检查是否使用了 rd /s /q 命令（这会绕过回收站）
print("\n⚠️  重要：使用 'rd /s /q' 命令删除的文件不会进入回收站")
print("这些文件需要通过其他方式恢复")
