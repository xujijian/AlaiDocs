#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查知识库历史记录"""

import sqlite3
from pathlib import Path
from collections import Counter

kb_path = Path(r"D:\E-BOOK\axis-SQLite\kb.sqlite")
if not kb_path.exists():
    print(f"❌ 知识库不存在: {kb_path}")
    exit(1)

conn = sqlite3.connect(str(kb_path))
cursor = conn.cursor()

# 获取表结构
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]
print(f"数据库表: {', '.join(tables)}")
print()

# 统计文档数
cursor.execute('SELECT COUNT(DISTINCT doc_id) FROM documents')
doc_count = cursor.fetchone()[0]
print(f"📚 知识库文档总数: {doc_count}")

# 统计 chunks 数
cursor.execute('SELECT COUNT(*) FROM chunks')
chunk_count = cursor.fetchone()[0]
print(f"📄 知识库 chunks 总数: {chunk_count}")

# 统计向量数
cursor.execute('SELECT COUNT(*) FROM embeddings')
vector_count = cursor.fetchone()[0]
print(f"🧮 向量总数: {vector_count}")
print()

# 统计厂商分布
cursor.execute('SELECT vendor, COUNT(*) as cnt FROM documents GROUP BY vendor ORDER BY cnt DESC')
print("厂商分布:")
total_by_vendor = 0
for vendor, count in cursor.fetchall():
    print(f"  {vendor}: {count}")
    total_by_vendor += count

print()

# 统计文档类型分布
cursor.execute('SELECT doc_type, COUNT(*) as cnt FROM documents GROUP BY doc_type ORDER BY cnt DESC')
print("文档类型分布:")
for doc_type, count in cursor.fetchall():
    print(f"  {doc_type}: {count}")

print()

# 检查路径是否存在
cursor.execute('SELECT path FROM documents LIMIT 5')
print("前5个文档路径:")
for row in cursor.fetchall():
    path = Path(row[0])
    exists = "✅" if path.exists() else "❌"
    print(f"  {exists} {row[0]}")

print()

# 统计实际存在的文件
base_dir = Path(r"D:\E-BOOK\axis-dcdc-pdf")
cursor.execute('SELECT path FROM documents')
all_paths = [row[0] for row in cursor.fetchall()]
existing_count = sum(1 for p in all_paths if (base_dir / p).exists())
missing_count = len(all_paths) - existing_count

print(f"文件状态:")
print(f"  ✅ 实际存在: {existing_count}")
print(f"  ❌ 已消失: {missing_count}")
print(f"  📊 消失比例: {missing_count/len(all_paths)*100:.1f}%")

conn.close()
