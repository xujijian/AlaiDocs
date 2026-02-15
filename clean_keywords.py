#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理 explored_keywords.json 中的脏数据
使用修复后的 parse_keywords() 函数重新过滤
"""

import json
from pathlib import Path
from datetime import datetime

# 导入修复后的 parse_keywords 函数
from keyword_explorer import parse_keywords

def clean_explored_keywords():
    """清理探索关键词文件中的脏数据"""
    file_path = Path("downloads_continuous/explored_keywords.json")
    
    if not file_path.exists():
        print("❌ 文件不存在")
        return
    
    # 读取原始数据
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    original_keywords = data.get('keywords', [])
    print(f"📋 原始关键词数量: {len(original_keywords)}")
    
    # 显示前5个和后5个
    print(f"\n前5个: {original_keywords[:5]}")
    print(f"后5个: {original_keywords[-5:]}")
    
    # 使用 parse_keywords 清理每一个关键词
    # 因为 parse_keywords 接受整个响应文本，我们需要逐个验证
    clean_keywords = []
    dirty_keywords = []
    
    for keyword in original_keywords:
        # 直接检查长度 - 超过 100 字符的肯定有问题
        if len(keyword) > 100:
            dirty_keywords.append(keyword)
            continue
            
        # 将每个关键词当作单独的响应来验证
        result = parse_keywords(keyword)
        if result:  # 如果通过了过滤
            clean_keywords.append(keyword)
        else:
            dirty_keywords.append(keyword)
    
    print(f"\n✅ 清理后关键词数量: {len(clean_keywords)}")
    print(f"❌ 过滤掉的脏数据: {len(dirty_keywords)}")
    
    if dirty_keywords:
        print(f"\n被过滤的脏数据:")
        for i, kw in enumerate(dirty_keywords[:10], 1):  # 只显示前10个
            preview = kw[:100] + '...' if len(kw) > 100 else kw
            print(f"  {i}. {preview}")
        if len(dirty_keywords) > 10:
            print(f"  ... 还有 {len(dirty_keywords) - 10} 个")
    
    # 备份原文件
    backup_path = file_path.with_suffix('.json.backup')
    if backup_path.exists():
        print(f"\n⚠️  备份文件已存在，将覆盖: {backup_path}")
    
    with open(backup_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ 已备份到: {backup_path}")
    
    # 保存清理后的数据
    cleaned_data = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'keywords': clean_keywords,
        'count': len(clean_keywords),
        'cleaned_from': len(original_keywords),
        'removed': len(dirty_keywords)
    }
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ 清理完成!")
    print(f"   原始: {len(original_keywords)} 个")
    print(f"   清理后: {len(clean_keywords)} 个")
    print(f"   移除: {len(dirty_keywords)} 个")
    print(f"   保存到: {file_path}")

if __name__ == '__main__':
    clean_explored_keywords()
