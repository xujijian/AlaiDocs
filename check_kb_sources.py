#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查知识库中文档的来源路径
"""

import sqlite3
from pathlib import Path
from collections import Counter

def main():
    kb_db = Path("D:/E-BOOK/axis-SQLite/kb.sqlite")
    
    conn = sqlite3.connect(str(kb_db))
    cursor = conn.cursor()
    
    # 获取所有文档的路径
    cursor.execute("SELECT path FROM documents")
    all_paths = [row[0] for row in cursor.fetchall()]
    
    print("=" * 70)
    print("📂 知识库文档来源分析")
    print("=" * 70)
    print(f"\n总文档数: {len(all_paths):,}\n")
    
    # 统计来源目录
    sources = Counter()
    for path in all_paths:
        p = Path(path)
        if 'downloads_continuous' in str(p):
            sources['downloads_continuous'] += 1
        elif 'axis-dcdc-pdf' in str(p):
            sources['axis-dcdc-pdf'] += 1
        else:
            sources['其他'] += 1
    
    print("📊 按来源目录统计:")
    for source, count in sources.most_common():
        print(f"   {source}: {count:,} ({count/len(all_paths)*100:.1f}%)")
    
    # 显示示例路径
    print("\n📁 路径示例 (前10个):")
    for path in all_paths[:10]:
        print(f"   {Path(path).name}")
        print(f"      → {path}")
    
    conn.close()
    
    print("\n" + "=" * 70)
    print("💡 说明:")
    print("   - SHA256 相同的文件不会重复入库")
    print("   - 知识库记录的是文件首次入库时的路径")
    print("   - 后续复制/移动文件不会改变知识库中的路径")
    print("   - 内容相同的文件，不管在哪个目录，都是同一个文档")
    print("=" * 70)


if __name__ == "__main__":
    main()
