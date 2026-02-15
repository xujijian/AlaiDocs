#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析PDF文件差异
"""

import sqlite3
from pathlib import Path
from collections import defaultdict

def main():
    # 统计各目录的PDF数量
    axis_dcdc = Path("D:/E-BOOK/axis-dcdc-pdf")
    downloads_cont = Path("D:/E-BOOK/axdcdcpdf/downloads_continuous")
    kb_db = Path("D:/E-BOOK/axis-SQLite/kb.sqlite")
    
    print("=" * 70)
    print("📊 PDF文件统计分析")
    print("=" * 70)
    
    # 1. axis-dcdc-pdf 中的文件
    axis_pdfs = list(axis_dcdc.rglob("*.pdf"))
    print(f"\n📁 axis-dcdc-pdf 目录: {len(axis_pdfs):,} 个PDF")
    
    # 按子目录统计
    by_vendor = defaultdict(int)
    for pdf in axis_pdfs:
        parts = pdf.relative_to(axis_dcdc).parts
        vendor = parts[0] if parts else "root"
        by_vendor[vendor] += 1
    
    print("\n   按厂商分类:")
    for vendor in sorted(by_vendor.keys()):
        print(f"   - {vendor}: {by_vendor[vendor]:,}")
    
    # 2. downloads_continuous 中的文件
    downloads_pdfs = list(downloads_cont.rglob("*.pdf"))
    print(f"\n📁 downloads_continuous 目录: {len(downloads_pdfs):,} 个PDF")
    print("   (这些文件还在等待分类)")
    
    # 3. 知识库中的文件
    if kb_db.exists():
        conn = sqlite3.connect(str(kb_db))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(DISTINCT doc_id) FROM documents")
        kb_count = cursor.fetchone()[0]
        conn.close()
        print(f"\n📚 知识库: {kb_count:,} 个文档")
    
    # 4. 总计
    total_files = len(axis_pdfs) + len(downloads_pdfs)
    print(f"\n{'='*70}")
    print(f"📊 总计: {total_files:,} 个PDF文件")
    print(f"   - 已分类: {len(axis_pdfs):,}")
    print(f"   - 待分类: {len(downloads_pdfs):,}")
    print(f"   - 已入库: {kb_count:,}")
    print(f"   - 未入库: {len(axis_pdfs) - kb_count:,} (可能是无效文件)")
    print(f"{'='*70}")
    
    # 5. 检查无效文件
    print("\n🔍 检查无效文件类型...")
    invalid_count = 0
    invalid_examples = []
    
    for pdf in axis_pdfs[:500]:  # 抽样检查500个
        try:
            with open(pdf, 'rb') as f:
                header = f.read(10)
                if not header.startswith(b'%PDF'):
                    invalid_count += 1
                    if len(invalid_examples) < 5:
                        invalid_examples.append(pdf.name)
        except Exception:
            invalid_count += 1
    
    if invalid_count > 0:
        estimated = int(invalid_count * len(axis_pdfs) / 500)
        print(f"\n⚠️  预估无效文件: ~{estimated:,} 个")
        print("   示例:")
        for name in invalid_examples:
            print(f"   - {name}")
        print("\n   建议运行: .\\clean_invalid.bat 清理无效文件")


if __name__ == "__main__":
    main()
