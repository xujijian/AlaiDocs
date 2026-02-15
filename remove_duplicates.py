#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
删除重复的PDF文件
"""

import hashlib
from pathlib import Path
from collections import defaultdict
from tqdm import tqdm

def calculate_sha256(filepath: Path) -> str:
    """计算文件SHA256"""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def choose_file_to_keep(files: list[Path]) -> Path:
    """选择要保留的文件（其他的删除）
    
    优先级：
    1. 不在 Unknown 目录的
    2. 路径最短的
    3. 文件名最短的
    """
    # 优先保留非 Unknown 目录的文件
    non_unknown = [f for f in files if 'Unknown' not in str(f)]
    if non_unknown:
        candidates = non_unknown
    else:
        candidates = files
    
    # 选择路径最短的
    return min(candidates, key=lambda f: (len(str(f)), len(f.name), str(f)))

def main():
    axis_dcdc = Path("D:/E-BOOK/axis-dcdc-pdf")
    
    print("=" * 70)
    print("🗑️  删除重复PDF文件")
    print("=" * 70)
    
    # 1. 扫描所有PDF
    print(f"\n📁 扫描 axis-dcdc-pdf...")
    all_pdfs = list(axis_dcdc.rglob("*.pdf"))
    print(f"   找到 {len(all_pdfs):,} 个PDF文件")
    
    # 2. 按SHA256分组
    print("\n🔢 计算SHA256并查找重复...")
    sha256_to_files = defaultdict(list)
    
    for pdf in tqdm(all_pdfs, desc="计算"):
        try:
            sha256 = calculate_sha256(pdf)
            sha256_to_files[sha256].append(pdf)
        except Exception as e:
            print(f"   错误: {pdf.name} - {e}")
    
    # 3. 找出所有重复文件
    duplicates_to_delete = []
    files_to_keep = []
    
    for sha256, files in sha256_to_files.items():
        if len(files) > 1:
            keep = choose_file_to_keep(files)
            files_to_keep.append(keep)
            for f in files:
                if f != keep:
                    duplicates_to_delete.append((f, keep))
    
    print(f"\n{'='*70}")
    print("📊 重复文件统计")
    print(f"{'='*70}")
    print(f"📄 总文件数: {len(all_pdfs):,}")
    print(f"🔑 唯一文档: {len(sha256_to_files):,}")
    print(f"🗑️  待删除: {len(duplicates_to_delete):,}")
    print(f"💾 释放空间: {sum(f[0].stat().st_size for f in duplicates_to_delete) / 1024 / 1024:.1f} MB")
    
    if not duplicates_to_delete:
        print("\n✅ 没有重复文件！")
        return
    
    # 4. 显示示例
    print(f"\n📋 删除示例 (前5个):")
    for delete_file, keep_file in duplicates_to_delete[:5]:
        print(f"\n  ❌ 删除: {delete_file.name}")
        print(f"     路径: {delete_file.relative_to(axis_dcdc)}")
        print(f"  ✅ 保留: {keep_file.relative_to(axis_dcdc)}")
    
    if len(duplicates_to_delete) > 5:
        print(f"\n  ... 还有 {len(duplicates_to_delete) - 5} 个重复文件")
    
    # 5. 确认删除
    print(f"\n{'='*70}")
    print(f"⚠️  警告: 将删除 {len(duplicates_to_delete):,} 个重复文件")
    print(f"{'='*70}")
    
    choice = input("\n确认删除？(输入 'DELETE' 确认，其他取消): ").strip()
    
    if choice != 'DELETE':
        print("\n❌ 取消删除")
        return
    
    # 6. 执行删除
    print("\n🗑️  删除中...")
    deleted = 0
    failed = 0
    
    for delete_file, keep_file in tqdm(duplicates_to_delete, desc="删除"):
        try:
            delete_file.unlink()
            deleted += 1
        except Exception as e:
            print(f"\n   删除失败: {delete_file.name} - {e}")
            failed += 1
    
    print(f"\n{'='*70}")
    print("✅ 删除完成")
    print(f"{'='*70}")
    print(f"✅ 成功删除: {deleted:,}")
    print(f"❌ 失败: {failed:,}")
    print(f"💾 释放空间: {sum(f[0].stat().st_size for f in duplicates_to_delete[:deleted]) / 1024 / 1024:.1f} MB")
    
    # 清理空目录
    print("\n🧹 清理空目录...")
    empty_dirs = []
    for dir_path in axis_dcdc.rglob("*"):
        if dir_path.is_dir():
            try:
                if not any(dir_path.iterdir()):
                    empty_dirs.append(dir_path)
            except:
                pass
    
    if empty_dirs:
        print(f"   发现 {len(empty_dirs)} 个空目录")
        for d in empty_dirs:
            try:
                d.rmdir()
            except:
                pass
        print("   ✅ 清理完成")


if __name__ == "__main__":
    main()
