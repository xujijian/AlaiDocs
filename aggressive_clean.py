#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
激进清理 - 只保留高质量关键词
删除所有分词碎片和生成失败的关键词
"""

import json
from pathlib import Path
from datetime import datetime

def aggressive_clean():
    """激进清理：只保留明显的高质量关键词"""
    file_path = Path("downloads_continuous/explored_keywords.json")
    
    if not file_path.exists():
        print("❌ 文件不存在")
        return
    
    # 读取原始数据
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    original_keywords = data.get('keywords', [])
    print(f"📋 原始关键词数量: {len(original_keywords)}")
    
    # 高质量关键词特征：
    # 1. 长度适中：10-80 字符
    # 2. 包含常见文档类型词或技术术语
    # 3. 不是纯碎的3词组合碎片
    
    quality_keywords = []
    removed = []
    
    # 必须包含的高质量指示词
    quality_indicators = [
        'datasheet', 'application note', 'design guide', 'reference design',
        'user guide', 'technical manual', 'evaluation board',
        'converter', 'regulator', 'controller', 'driver', 'pmic',
        'buck', 'boost', 'flyback', 'forward', 'llc', 'sepic', 'cuk'
    ]
    
    # 低质量指示词（通常是碎片）
    low_quality_patterns = [
        'stage automotive', 'charger industrial', 'regulator telecom',
        'management battery monitoring', 'ic synchronous boost',
        'switching gate driver', 'circuit integrated power',
        'protection current limit', 'thermal shutdown feature'
    ]
    
    for kw in original_keywords:
        # 长度检查
        if not (10 <= len(kw) <= 80):
            removed.append(('length', kw))
            continue
        
        # 检查是否是低质量碎片
        if any(pattern in kw.lower() for pattern in low_quality_patterns):
            removed.append(('fragment', kw))
            continue
        
        # 必须包含至少一个高质量指示词
        if not any(word in kw.lower() for word in quality_indicators):
            removed.append(('no_quality_indicator', kw))
            continue
        
        # 通过所有检查
        quality_keywords.append(kw)
    
    print(f"✅ 高质量关键词: {len(quality_keywords)} 个")
    print(f"❌ 移除关键词: {len(removed)} 个")
    
    # 统计移除原因
    reasons = {}
    for reason, _ in removed:
        reasons[reason] = reasons.get(reason, 0) + 1
    
    print(f"\n移除原因统计:")
    for reason, count in reasons.items():
        print(f"  {reason}: {count} 个")
    
    # 显示一些被移除的示例
    if removed:
        print(f"\n被移除示例 (前10个):")
        for i, (reason, kw) in enumerate(removed[:10], 1):
            preview = kw[:80] + '...' if len(kw) > 80 else kw
            print(f"  {i}. [{reason}] {preview}")
    
    # 显示保留的关键词示例
    print(f"\n保留的关键词示例 (前10个):")
    for i, kw in enumerate(quality_keywords[:10], 1):
        print(f"  {i}. {kw}")
    
    print(f"\n保留的关键词示例 (后10个):")
    for i, kw in enumerate(quality_keywords[-10:], len(quality_keywords)-9):
        print(f"  {i}. {kw}")
    
    # 询问确认
    print(f"\n{'='*60}")
    print(f"将从 {len(original_keywords)} 个减少到 {len(quality_keywords)} 个")
    print(f"{'='*60}")
    
    confirm = input("确认执行清理? (y/n): ")
    if confirm.lower() != 'y':
        print("取消操作")
        return
    
    # 备份
    backup_path = file_path.with_suffix('.json.backup2')
    with open(backup_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ 已备份到: {backup_path}")
    
    # 保存清理后的数据
    cleaned_data = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'keywords': quality_keywords,
        'count': len(quality_keywords),
        'cleaned_from': len(original_keywords),
        'removed': len(removed)
    }
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ 激进清理完成!")
    print(f"   原始: {len(original_keywords)} 个")
    print(f"   清理后: {len(quality_keywords)} 个")
    print(f"   移除: {len(removed)} 个")

if __name__ == '__main__':
    aggressive_clean()
