#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理无效的 PDF 文件
"""

import sys
from pathlib import Path
import pypdf
from tqdm import tqdm

def is_valid_pdf(filepath: Path) -> bool:
    """检查是否是有效的 PDF 文件"""
    try:
        # 检查文件头
        with open(filepath, 'rb') as f:
            header = f.read(10)
            if not header.startswith(b'%PDF'):
                return False
        
        # 尝试打开 PDF
        with open(filepath, 'rb') as f:
            reader = pypdf.PdfReader(f)
            _ = len(reader.pages)
        return True
    except Exception:
        return False


def main():
    root = Path("D:/E-BOOK/axis-dcdc-pdf")
    
    print("🔍 扫描无效 PDF 文件...")
    pdf_files = list(root.rglob("*.pdf"))
    print(f"找到 {len(pdf_files)} 个 PDF 文件\n")
    
    invalid_files = []
    for pdf in tqdm(pdf_files, desc="检查"):
        if not is_valid_pdf(pdf):
            invalid_files.append(pdf)
    
    if not invalid_files:
        print("\n✅ 所有文件都有效！")
        return
    
    print(f"\n⚠️  发现 {len(invalid_files)} 个无效文件：\n")
    for f in invalid_files[:20]:  # 只显示前20个
        print(f"  - {f.relative_to(root)}")
    
    if len(invalid_files) > 20:
        print(f"  ... 还有 {len(invalid_files) - 20} 个")
    
    print(f"\n总大小: {sum(f.stat().st_size for f in invalid_files) / 1024 / 1024:.2f} MB")
    
    # 询问是否删除
    choice = input("\n是否删除这些无效文件? (y/N): ").strip().lower()
    if choice == 'y':
        for f in tqdm(invalid_files, desc="删除"):
            try:
                f.unlink()
            except Exception as e:
                print(f"删除失败 {f.name}: {e}")
        print(f"\n✅ 已删除 {len(invalid_files)} 个无效文件")
    else:
        print("取消删除")


if __name__ == "__main__":
    main()
