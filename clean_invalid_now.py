#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理无效PDF文件 - 快速版
"""

from pathlib import Path

def main():
    axis_dir = Path(r"D:\E-BOOK\axis-dcdc-pdf")
    invalid_files = []
    
    print("🔍 扫描无效PDF文件...")
    for pdf in axis_dir.rglob("*.pdf"):
        try:
            with open(pdf, "rb") as f:
                header = f.read(10)
                # PDF必须以 %PDF 开头
                if not header.startswith(b"%PDF"):
                    invalid_files.append((pdf, header[:10]))
        except Exception as e:
            print(f"⚠️  读取失败 {pdf.name}: {e}")
    
    if not invalid_files:
        print("✅ 没有找到无效文件")
        return
    
    print(f"\n📊 找到 {len(invalid_files)} 个无效文件:\n")
    for path, header in invalid_files:
        rel_path = path.relative_to(axis_dir)
        print(f"❌ {rel_path}")
        print(f"   头部: {header}")
        print(f"   大小: {path.stat().st_size / 1024:.1f} KB")
    
    total_size = sum(p.stat().st_size for p, _ in invalid_files) / 1024
    print(f"\n💾 总大小: {total_size:.1f} KB")
    
    # 确认删除
    print("\n" + "="*60)
    confirm = input("⚠️  确认删除这些文件吗？输入 DELETE 确认: ").strip()
    
    if confirm == "DELETE":
        deleted = 0
        for path, _ in invalid_files:
            try:
                path.unlink()
                deleted += 1
                print(f"🗑️  已删除: {path.name}")
            except Exception as e:
                print(f"❌ 删除失败 {path.name}: {e}")
        
        print(f"\n✅ 成功删除 {deleted}/{len(invalid_files)} 个文件")
        print(f"💾 释放空间: {total_size:.1f} KB")
        
        # 清理空目录
        print("\n🧹 清理空目录...")
        empty_dirs = []
        for d in sorted(axis_dir.rglob("*"), key=lambda p: len(p.parts), reverse=True):
            if d.is_dir() and not any(d.iterdir()):
                empty_dirs.append(d)
                d.rmdir()
        
        if empty_dirs:
            print(f"✅ 删除了 {len(empty_dirs)} 个空目录")
    else:
        print("❌ 取消删除")

if __name__ == "__main__":
    main()
