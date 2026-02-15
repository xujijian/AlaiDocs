#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成重新下载清单"""

import json
import sqlite3
from pathlib import Path
from collections import defaultdict

print("="*70)
print("生成丢失文件重新下载清单")
print("="*70)

# 1. 获取所有下载记录
results_file = Path("downloads_continuous/results.jsonl")
downloaded_files = {}

if results_file.exists():
    with open(results_file, 'r', encoding='utf-8') as f:
        for line in f:
            record = json.loads(line)
            if record.get('status') == 'success':
                filename = record.get('filename')
                url = record.get('url')
                vendor = record.get('vendor')
                if filename:
                    downloaded_files[filename] = {
                        'url': url,
                        'vendor': vendor,
                        'record': record
                    }

print(f"✅ 成功下载记录: {len(downloaded_files)} 个")

# 2. 获取知识库中的文件列表
kb_path = Path(r"D:\E-BOOK\axis-SQLite\kb.sqlite")
kb_files = set()
if kb_path.exists():
    conn = sqlite3.connect(str(kb_path))
    cursor = conn.cursor()
    cursor.execute('SELECT path FROM documents')
    for row in cursor.fetchall():
        filename = Path(row[0]).name
        kb_files.add(filename)
    conn.close()

print(f"📚 知识库记录: {len(kb_files)} 个")

# 3. 检查当前存在的文件
base_dir = Path(r"D:\E-BOOK\axis-dcdc-pdf")
downloads_dir = Path("downloads_continuous")

existing_files = set()
if base_dir.exists():
    for pdf in base_dir.rglob("*.pdf"):
        existing_files.add(pdf.name)
if downloads_dir.exists():
    for pdf in downloads_dir.rglob("*.pdf"):
        existing_files.add(pdf.name)

print(f"📁 当前存在: {len(existing_files)} 个")

# 4. 找出丢失的文件
missing_in_kb = kb_files - existing_files
missing_downloaded = set(downloaded_files.keys()) - existing_files

print(f"\n❌ 知识库中丢失: {len(missing_in_kb)} 个")
print(f"❌ 已下载但丢失: {len(missing_downloaded)} 个")

# 5. 生成重新下载清单
redownload_list = []
for filename in missing_downloaded:
    if filename in downloaded_files:
        info = downloaded_files[filename]
        redownload_list.append({
            'filename': filename,
            'url': info['url'],
            'vendor': info['vendor']
        })

# 按厂商分组
by_vendor = defaultdict(list)
for item in redownload_list:
    by_vendor[item['vendor']].append(item)

# 保存清单
output_file = Path("redownload_list.json")
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(redownload_list, f, ensure_ascii=False, indent=2)

print(f"\n✅ 已生成重新下载清单: {output_file}")
print(f"   总计需重新下载: {len(redownload_list)} 个文件")

print("\n按厂商统计:")
for vendor, items in sorted(by_vendor.items(), key=lambda x: len(x[1]), reverse=True):
    print(f"  {vendor}: {len(items)}")

print("\n" + "="*70)
print("下一步操作建议:")
print("="*70)
print("1. 查看 redownload_list.json 确认需要重新下载的文件")
print("2. 运行重新下载脚本（需要创建）")
print("3. 或者让下载器继续运行，自然会重新下载这些文件")
