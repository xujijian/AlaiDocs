#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""完整统计所有文件去向"""

import sqlite3
import json
from pathlib import Path
from collections import Counter

print("="*70)
print("完整文件追踪报告")
print("="*70)

# 1. 下载记录
results_file = Path("downloads_continuous/results.jsonl")
if results_file.exists():
    with open(results_file, 'r', encoding='utf-8') as f:
        download_records = [json.loads(line) for line in f]
    print(f"\n📥 下载记录总数: {len(download_records)}")
    
    # 统计成功/失败
    success = sum(1 for r in download_records if r.get('status') == 'success')
    failed = len(download_records) - success
    print(f"  ✅ 成功: {success}")
    print(f"  ❌ 失败: {failed}")

# 2. 分类数据库
classify_db = Path("classified_files.db")
if classify_db.exists():
    conn = sqlite3.connect(str(classify_db))
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM processed_files')
    classified_count = cursor.fetchone()[0]
    print(f"\n🗂️  分类器处理数: {classified_count}")
    
    # 检查存在情况
    cursor.execute('SELECT dst_path FROM processed_files')
    classified_paths = [row[0] for row in cursor.fetchall()]
    existing_classified = sum(1 for p in classified_paths if p and Path(p).exists())
    print(f"  ✅ 实际存在: {existing_classified}")
    print(f"  ❌ 已消失: {classified_count - existing_classified}")
    conn.close()

# 3. 知识库
kb_path = Path(r"D:\E-BOOK\axis-SQLite\kb.sqlite")
if kb_path.exists():
    conn = sqlite3.connect(str(kb_path))
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(DISTINCT doc_id) FROM documents')
    kb_doc_count = cursor.fetchone()[0]
    print(f"\n📚 知识库文档数: {kb_doc_count}")
    
    base_dir = Path(r"D:\E-BOOK\axis-dcdc-pdf")
    cursor.execute('SELECT path FROM documents')
    kb_paths = [row[0] for row in cursor.fetchall()]
    existing_kb = sum(1 for p in kb_paths if (base_dir / p).exists())
    print(f"  ✅ 实际存在: {existing_kb}")
    print(f"  ❌ 已消失: {kb_doc_count - existing_kb}")
    conn.close()

# 4. 当前文件系统
downloads_dir = Path("downloads_continuous")
axis_dcdc_dir = Path(r"D:\E-BOOK\axis-dcdc-pdf")

downloads_count = len(list(downloads_dir.rglob("*.pdf"))) if downloads_dir.exists() else 0
axis_dcdc_count = len(list(axis_dcdc_dir.rglob("*.pdf"))) if axis_dcdc_dir.exists() else 0

print(f"\n📁 当前文件系统:")
print(f"  downloads_continuous: {downloads_count}")
print(f"  axis-dcdc-pdf: {axis_dcdc_count}")
print(f"  总计: {downloads_count + axis_dcdc_count}")

print("\n" + "="*70)
print("文件流向分析:")
print("="*70)
if results_file.exists() and classify_db.exists():
    downloaded_success = success
    print(f"1. 成功下载: {downloaded_success}")
    print(f"2. 分类处理: {classified_count}")
    print(f"3. 进入知识库: {kb_doc_count}")
    print(f"4. 现存文件: {downloads_count + axis_dcdc_count}")
    print(f"\n⚠️  丢失文件: {downloaded_success - (downloads_count + axis_dcdc_count)}")
