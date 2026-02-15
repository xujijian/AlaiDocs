#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
详细检查未入库的PDF文件
"""

import sqlite3
import hashlib
from pathlib import Path
from tqdm import tqdm
import pypdf

def calculate_sha256(filepath: Path) -> str:
    """计算文件SHA256"""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def check_pdf_validity(filepath: Path) -> tuple[bool, str]:
    """检查PDF是否有效
    Returns: (是否有效, 错误信息)
    """
    try:
        # 检查文件头
        with open(filepath, 'rb') as f:
            header = f.read(10)
            if not header.startswith(b'%PDF'):
                return False, f"非PDF文件 (头部: {header[:20]})"
        
        # 尝试打开PDF
        with open(filepath, 'rb') as f:
            reader = pypdf.PdfReader(f)
            page_count = len(reader.pages)
            
            # 尝试读取第一页
            if page_count > 0:
                text = reader.pages[0].extract_text()
                if len(text.strip()) < 10:
                    return True, f"警告: 文本内容很少 ({len(text)} chars)"
            
            return True, f"有效PDF ({page_count} 页)"
    
    except Exception as e:
        return False, f"PDF错误: {str(e)[:100]}"

def main():
    axis_dcdc = Path("D:/E-BOOK/axis-dcdc-pdf")
    kb_db = Path("D:/E-BOOK/axis-SQLite/kb.sqlite")
    
    print("=" * 70)
    print("🔍 检查未入库的PDF文件")
    print("=" * 70)
    
    # 1. 获取知识库中所有文档的SHA256
    print("\n📚 读取知识库...")
    conn = sqlite3.connect(str(kb_db))
    cursor = conn.cursor()
    cursor.execute("SELECT doc_id FROM documents")
    kb_sha256s = set(row[0] for row in cursor.fetchall())
    conn.close()
    print(f"   知识库中有 {len(kb_sha256s):,} 个文档")
    
    # 2. 扫描所有PDF文件
    print("\n📁 扫描 axis-dcdc-pdf...")
    all_pdfs = list(axis_dcdc.rglob("*.pdf"))
    print(f"   找到 {len(all_pdfs):,} 个PDF文件")
    
    # 3. 检查每个文件是否在知识库中
    print("\n🔍 检查未入库文件...")
    missing_files = []
    
    for pdf in tqdm(all_pdfs[:500], desc="检查"):  # 先检查前500个
        try:
            sha256 = calculate_sha256(pdf)
            if sha256 not in kb_sha256s:
                is_valid, msg = check_pdf_validity(pdf)
                missing_files.append({
                    'path': pdf,
                    'sha256': sha256,
                    'valid': is_valid,
                    'message': msg
                })
        except Exception as e:
            missing_files.append({
                'path': pdf,
                'sha256': 'error',
                'valid': False,
                'message': f"无法处理: {e}"
            })
    
    # 4. 分类统计
    valid_but_missing = [f for f in missing_files if f['valid']]
    invalid_files = [f for f in missing_files if not f['valid']]
    
    print(f"\n{'='*70}")
    print("📊 检查结果 (前500个文件)")
    print(f"{'='*70}")
    print(f"✅ 有效但未入库: {len(valid_but_missing)}")
    print(f"❌ 无效文件: {len(invalid_files)}")
    print(f"📚 已在库中: {500 - len(missing_files)}")
    
    # 5. 显示无效文件示例
    if invalid_files:
        print(f"\n❌ 无效文件示例 (前10个):")
        for f in invalid_files[:10]:
            print(f"\n  {f['path'].name}")
            print(f"    位置: {f['path'].parent.relative_to(axis_dcdc)}")
            print(f"    原因: {f['message']}")
    
    # 6. 显示有效但未入库的文件
    if valid_but_missing:
        print(f"\n✅ 有效但未入库的文件 (前10个):")
        for f in valid_but_missing[:10]:
            print(f"\n  {f['path'].name}")
            print(f"    位置: {f['path'].parent.relative_to(axis_dcdc)}")
            print(f"    状态: {f['message']}")
        
        print(f"\n⚠️  这些文件有效但未入库，可能原因:")
        print("    1. 知识库监控刚添加，还没来得及处理")
        print("    2. 处理时出错但文件本身有效")
        print("    3. 文本内容太少被跳过")
    
    # 7. 估算总数
    estimated_invalid = int(len(invalid_files) * len(all_pdfs) / 500)
    estimated_valid_missing = int(len(valid_but_missing) * len(all_pdfs) / 500)
    
    print(f"\n{'='*70}")
    print("📈 全量估算 (基于500个样本)")
    print(f"{'='*70}")
    print(f"❌ 预估无效文件: ~{estimated_invalid:,}")
    print(f"✅ 预估有效但未入库: ~{estimated_valid_missing:,}")
    print(f"📚 预估已入库: ~{len(all_pdfs) - estimated_invalid - estimated_valid_missing:,}")
    
    if estimated_invalid > 100:
        print(f"\n💡 建议: 运行 .\\clean_invalid.bat 清理 ~{estimated_invalid:,} 个无效文件")


if __name__ == "__main__":
    main()
