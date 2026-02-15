#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析文件重复情况和知识库覆盖率
"""

import sqlite3
import hashlib
from pathlib import Path
from collections import Counter, defaultdict
from tqdm import tqdm

def calculate_sha256(filepath: Path) -> str:
    """计算文件SHA256"""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def main():
    axis_dcdc = Path("D:/E-BOOK/axis-dcdc-pdf")
    kb_db = Path("D:/E-BOOK/axis-SQLite/kb.sqlite")
    
    print("=" * 70)
    print("🔍 文件重复分析")
    print("=" * 70)
    
    # 1. 读取知识库中的所有SHA256
    print("\n📚 读取知识库...")
    conn = sqlite3.connect(str(kb_db))
    cursor = conn.cursor()
    
    # 获取所有文档的 SHA256 和路径
    cursor.execute("SELECT doc_id, path FROM documents")
    kb_docs = {row[0]: row[1] for row in cursor.fetchall()}
    print(f"   知识库文档数: {len(kb_docs):,}")
    
    # 检查是否有其他表存储了更多SHA256
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"   数据库表: {', '.join(tables)}")
    
    conn.close()
    
    # 2. 扫描所有PDF并计算SHA256
    print(f"\n📁 扫描 axis-dcdc-pdf...")
    all_pdfs = list(axis_dcdc.rglob("*.pdf"))
    print(f"   找到 {len(all_pdfs):,} 个PDF文件")
    
    print("\n🔢 计算SHA256...")
    sha256_to_files = defaultdict(list)
    
    for pdf in tqdm(all_pdfs, desc="计算"):
        try:
            sha256 = calculate_sha256(pdf)
            sha256_to_files[sha256].append(pdf)
        except Exception as e:
            print(f"   错误: {pdf.name} - {e}")
    
    # 3. 分析重复情况
    unique_sha256 = len(sha256_to_files)
    total_files = len(all_pdfs)
    duplicates = total_files - unique_sha256
    
    print(f"\n{'='*70}")
    print("📊 重复文件分析")
    print(f"{'='*70}")
    print(f"📄 文件总数: {total_files:,}")
    print(f"🔑 唯一SHA256: {unique_sha256:,}")
    print(f"📋 重复文件: {duplicates:,} ({duplicates/total_files*100:.1f}%)")
    print(f"📚 知识库文档: {len(kb_docs):,}")
    print(f"❓ 差异: {unique_sha256 - len(kb_docs):,} 个SHA256不在知识库中")
    
    # 4. 找出重复最多的文件
    print(f"\n🔝 重复最多的文件 (前10个):")
    sorted_dups = sorted(sha256_to_files.items(), key=lambda x: len(x[1]), reverse=True)
    
    for sha256, files in sorted_dups[:10]:
        if len(files) > 1:
            print(f"\n   {files[0].name}")
            print(f"   重复 {len(files)} 次:")
            for f in files[:3]:
                print(f"      → {f.relative_to(axis_dcdc)}")
            if len(files) > 3:
                print(f"      ... 还有 {len(files)-3} 个")
            
            # 检查是否在知识库中
            in_kb = "✅" if sha256 in kb_docs else "❌"
            print(f"   知识库: {in_kb}")
    
    # 5. 检查不在知识库的唯一文件
    missing_sha256s = set(sha256_to_files.keys()) - set(kb_docs.keys())
    if missing_sha256s:
        print(f"\n⚠️  {len(missing_sha256s):,} 个唯一文件不在知识库中:")
        for sha256 in list(missing_sha256s)[:10]:
            files = sha256_to_files[sha256]
            print(f"\n   {files[0].name}")
            print(f"      路径: {files[0].relative_to(axis_dcdc)}")
            print(f"      SHA256: {sha256[:16]}...")
    
    print(f"\n{'='*70}")
    print("💡 结论:")
    print(f"   1. 实际唯一文档: {unique_sha256:,}")
    print(f"   2. 重复文件: {duplicates:,} 可以删除")
    print(f"   3. 知识库覆盖: {len(kb_docs)}/{unique_sha256} = {len(kb_docs)/unique_sha256*100:.1f}%")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
