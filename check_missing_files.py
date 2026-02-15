#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查文件去向"""

import sqlite3
from pathlib import Path
from collections import Counter

db_path = Path("classified_files.db")
if not db_path.exists():
    print("数据库不存在")
    exit(1)

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# 统计总记录数
cursor.execute('SELECT COUNT(*) FROM processed_files')
total = cursor.fetchone()[0]
print(f"数据库记录总数: {total}")
print()

# 统计目标路径分布
cursor.execute('SELECT dst_path FROM processed_files')
destinations = [row[0] for row in cursor.fetchall()]

# 按顶级目录分组
top_dirs = Counter()
for dst in destinations:
    if dst:
        parts = Path(dst).parts
        if len(parts) > 5:  # D:\E-BOOK\axis-dcdc-pdf\厂商\类型
            top_dir = parts[4] if len(parts) > 4 else "unknown"
            top_dirs[top_dir] += 1

print("文件分布:")
for dir_name, count in top_dirs.most_common():
    print(f"  {dir_name}: {count}")

print()

# 检查 Unknown 和 Trash
unknown_count = sum(1 for dst in destinations if dst and 'Unknown' in dst)
trash_count = sum(1 for dst in destinations if dst and 'Trash' in dst)

print(f"Unknown 目录: {unknown_count}")
print(f"Trash 目录: {trash_count}")
print()

# 检查实际存在的文件
existing = 0
for dst in destinations:
    if dst and Path(dst).exists():
        existing += 1

print(f"实际存在的文件: {existing}/{total}")
print(f"已消失的文件: {total - existing}")

conn.close()
