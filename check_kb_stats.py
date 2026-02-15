#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查询知识库统计信息
"""

import sqlite3
from pathlib import Path

def main():
    kb_path = Path("D:/E-BOOK/axis-SQLite/kb.sqlite")
    
    if not kb_path.exists():
        print("❌ 知识库文件不存在")
        return
    
    conn = sqlite3.connect(str(kb_path))
    cursor = conn.cursor()
    
    # 统计文档数量
    cursor.execute("SELECT COUNT(DISTINCT doc_id) FROM documents")
    doc_count = cursor.fetchone()[0]
    
    # 统计文本块数量
    cursor.execute("SELECT COUNT(*) FROM chunks")
    chunk_count = cursor.fetchone()[0]
    
    # 统计最近添加的文档
    cursor.execute("""
        SELECT COUNT(*) 
        FROM documents 
        WHERE created_at > datetime('now', '-1 day')
    """)
    recent_count = cursor.fetchone()[0]
    
    # 获取最新的文档
    cursor.execute("""
        SELECT title, path, created_at
        FROM documents
        ORDER BY created_at DESC
        LIMIT 5
    """)
    recent_docs = cursor.fetchall()
    
    conn.close()
    
    print("=" * 60)
    print("📊 知识库统计信息")
    print("=" * 60)
    print(f"📚 总文档数量: {doc_count:,}")
    print(f"📄 总文本块数量: {chunk_count:,}")
    print(f"🆕 最近24小时新增: {recent_count:,}")
    print(f"📈 平均每文档: {chunk_count/doc_count:.1f} 个文本块" if doc_count > 0 else "")
    print()
    
    if recent_docs:
        print("🕒 最近添加的文档:")
        for title, path, created_at in recent_docs:
            print(f"  - {Path(path).name}")
            print(f"    {created_at}")
    
    print("=" * 60)
    
    # 检查 FAISS 索引
    faiss_path = Path("D:/E-BOOK/axis-SQLite/kb.faiss")
    if faiss_path.exists():
        try:
            import faiss
            index = faiss.read_index(str(faiss_path))
            print(f"🔍 FAISS 向量数量: {index.ntotal:,}")
        except ImportError:
            size_mb = faiss_path.stat().st_size / 1024 / 1024
            print(f"🔍 FAISS 索引文件: {size_mb:.1f} MB")
    else:
        print("⚠️  FAISS 索引不存在")


if __name__ == "__main__":
    main()
