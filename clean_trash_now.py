#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速清理脚本 - 删除 Trash 目录下的无效 PDF
"""

import shutil
from pathlib import Path

def main():
    trash_dir = Path(r"D:\E-BOOK\axis-dcdc-pdf\Trash")
    
    if not trash_dir.exists():
        print("✅ Trash 目录不存在，无需清理")
        return
    
    # 统计文件
    pdf_files = list(trash_dir.rglob("*.pdf"))
    
    if not pdf_files:
        print("✅ Trash 目录为空")
        return
    
    print(f"发现 {len(pdf_files)} 个 Trash 文件")
    print(f"位置: {trash_dir}")
    print("")
    print("这些文件将被永久删除:")
    for pdf in pdf_files[:10]:
        print(f"  - {pdf.relative_to(trash_dir.parent)}")
    if len(pdf_files) > 10:
        print(f"  ... 还有 {len(pdf_files) - 10} 个文件")
    print("")
    
    confirm = input("确认删除 Trash 目录? (输入 DELETE 确认): ").strip()
    
    if confirm == "DELETE":
        print("删除中...")
        shutil.rmtree(trash_dir)
        print(f"✅ 已删除 {len(pdf_files)} 个文件")
    else:
        print("❌ 取消操作")

if __name__ == "__main__":
    main()
