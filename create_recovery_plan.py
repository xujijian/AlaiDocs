#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
紧急恢复下载器 - 根据知识库丢失文件重新下载
"""

import sqlite3
from pathlib import Path
from collections import Counter
import json

# 分析丢失文件的关键词
kb_path = Path(r"D:\E-BOOK\axis-SQLite\kb.sqlite")
base_dir = Path(r"D:\E-BOOK\axis-dcdc-pdf")

conn = sqlite3.connect(str(kb_path))
cursor = conn.cursor()

# 获取所有丢失的文件信息
cursor.execute('''
    SELECT vendor, doc_type, path 
    FROM documents
''')

missing_files = []
for row in cursor.fetchall():
    vendor, doc_type, path = row
    full_path = base_dir / path
    if not full_path.exists():
        missing_files.append({
            'vendor': vendor,
            'doc_type': doc_type,
            'path': path,
            'filename': Path(path).name
        })

conn.close()

print(f"丢失文件总数: {len(missing_files)}")

# 统计需要的搜索关键词
vendors = Counter(f['vendor'] for f in missing_files)
doc_types = Counter(f['doc_type'] for f in missing_files)

print("\n需要重点下载的类型:")
print("\n厂商分布:")
for vendor, count in vendors.most_common(10):
    print(f"  {vendor}: {count}")

print("\n文档类型:")
for dtype, count in doc_types.most_common(10):
    print(f"  {dtype}: {count}")

# 生成恢复搜索关键词
recovery_queries = []

# 按厂商和类型组合
for vendor, v_count in vendors.most_common():
    if vendor != 'Unknown':
        for dtype, d_count in doc_types.most_common(5):
            if dtype not in ['LowConfidence', 'unknown']:
                query = f"{vendor} {dtype} dc-dc filetype:pdf"
                recovery_queries.append({
                    'query': query,
                    'vendor': vendor,
                    'doc_type': dtype,
                    'priority': v_count + d_count
                })

# 按优先级排序
recovery_queries.sort(key=lambda x: x['priority'], reverse=True)

# 保存恢复搜索清单
output = Path("recovery_searches.json")
with open(output, 'w', encoding='utf-8') as f:
    json.dump(recovery_queries[:100], f, ensure_ascii=False, indent=2)  # 只保存前100个

print(f"\n✅ 已生成恢复搜索清单: {output}")
print(f"   共 {min(len(recovery_queries), 100)} 个搜索查询")
print("\n建议：")
print("1. 让 continuous_searcher.py 继续运行（会自然恢复大部分文件）")
print("2. 或使用 recovery_searches.json 创建专门的恢复下载任务")
