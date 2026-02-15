#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速恢复下载器 - 专门恢复丢失的文件
结合 continuous_searcher 一起工作，加速恢复
"""

import json
import time
import random
import requests
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
import re

# DuckDuckGo 搜索
try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        print("❌ 需要安装搜索库")
        print("   运行: pip install ddgs")
        exit(1)

# 配置
DOWNLOADS_DIR = Path("downloads_continuous")
RESULTS_FILE = DOWNLOADS_DIR / "results.jsonl"
SUMMARY_FILE = DOWNLOADS_DIR / "summary.csv"

def sanitize_filename(title: str, max_length: int = 200) -> str:
    """清理文件名"""
    # 移除非法字符
    filename = re.sub(r'[<>:"/\\|?*]', '', title)
    # 限制长度
    if len(filename) > max_length:
        filename = filename[:max_length]
    # 移除首尾空格和点
    filename = filename.strip('. ')
    return filename or "untitled"

def download_pdf(url: str, save_dir: Path, title: str) -> tuple:
    """
    下载PDF文件
    返回: (成功, 文件路径, 错误信息)
    """
    try:
        # 生成文件名
        filename = sanitize_filename(title)
        if not filename.lower().endswith('.pdf'):
            filename += '.pdf'
        
        filepath = save_dir / filename
        
        # 如果文件已存在，跳过
        if filepath.exists():
            return True, str(filepath), None
        
        # 下载
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=30, stream=True)
        response.raise_for_status()
        
        # 检查是否是PDF
        content_type = response.headers.get('Content-Type', '').lower()
        if 'pdf' not in content_type and 'application/octet-stream' not in content_type:
            return False, None, f"不是PDF文件: {content_type}"
        
        # 保存文件
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        # 验证文件大小
        if filepath.stat().st_size < 1024:  # 小于1KB
            filepath.unlink()
            return False, None, "文件太小"
        
        return True, str(filepath), None
        
    except requests.Timeout:
        return False, None, "下载超时"
    except requests.RequestException as e:
        return False, None, f"下载失败: {str(e)}"
    except Exception as e:
        return False, None, f"错误: {str(e)}"

def save_result(result: dict):
    """保存下载结果"""
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    
    with open(RESULTS_FILE, 'a', encoding='utf-8') as f:
        f.write(json.dumps(result, ensure_ascii=False) + '\n')

def search_ddg(query: str, max_results: int = 20) -> list:
    """使用 DuckDuckGo 搜索"""
    try:
        with DDGS() as ddgs:
            results = []
            for result in ddgs.text(query, max_results=max_results):
                url = result.get('href', '')
                # 只保留可能是 PDF 的 URL
                if is_likely_pdf_url(url):
                    results.append({
                        'title': result.get('title', ''),
                        'url': url,
                        'snippet': result.get('body', '')
                    })
            return results
    except Exception as e:
        print(f"  ⚠️  搜索失败: {e}")
        return []

def is_likely_pdf_url(url: str) -> bool:
    """判断 URL 是否可能是 PDF"""
    url_lower = url.lower()
    
    # 明确的 PDF URL
    if url_lower.endswith('.pdf'):
        return True
    
    # 常见的 PDF 路径特征
    pdf_indicators = [
        '/pdf/', '/pdfs/', '/downloads/', '/datasheet/',
        'filetype=pdf', 'type=pdf', '.pdf?',
        'lit/pdf', 'media/pdf', 'doc/pdf',
        '/ds/', '/an/', 'technical-documentation'
    ]
    
    return any(indicator in url_lower for indicator in pdf_indicators)

def load_recovery_queries():
    """加载恢复搜索清单"""
    recovery_file = Path("recovery_searches.json")
    if not recovery_file.exists():
        print("❌ 找不到 recovery_searches.json")
        print("   请先运行: python create_recovery_plan.py")
        return []
    
    with open(recovery_file, 'r', encoding='utf-8') as f:
        queries = json.load(f)
    
    return queries

def recovery_search():
    """执行恢复搜索"""
    queries = load_recovery_queries()
    
    if not queries:
        return
    
    print("="*70)
    print("快速恢复下载器")
    print("="*70)
    print(f"恢复搜索清单: {len(queries)} 个查询")
    print(f"目标: 快速恢复丢失的 2000+ 个文件")
    print(f"策略: 高优先级查询 + 快速下载")
    print("="*70)
    print()
    
    total_downloaded = 0
    total_failed = 0
    
    for idx, query_info in enumerate(queries, 1):
        query = query_info['query']
        vendor = query_info.get('vendor', 'unknown')
        doc_type = query_info.get('doc_type', 'unknown')
        priority = query_info.get('priority', 0)
        
        print(f"\n[{idx}/{len(queries)}] 优先级: {priority}")
        print(f"查询: {query}")
        print(f"类型: {vendor} / {doc_type}")
        
        try:
            # 搜索
            results = search_ddg(query, max_results=20)
            
            if not results:
                print("  ⚠️  未找到结果")
                continue
            
            print(f"  找到 {len(results)} 个PDF链接")
            
            # 下载前 10 个
            downloaded_count = 0
            for i, result in enumerate(results[:10], 1):
                url = result.get('url', '')
                title = result.get('title', 'Untitled')
                
                # 确定厂商目录
                if vendor != 'Unknown' and vendor != 'unknown':
                    vendor_dir = DOWNLOADS_DIR / vendor.lower()
                else:
                    vendor_dir = DOWNLOADS_DIR / "unknown"
                
                vendor_dir.mkdir(parents=True, exist_ok=True)
                
                # 下载
                success, filepath, error = download_pdf(url, vendor_dir, title)
                
                if success:
                    downloaded_count += 1
                    total_downloaded += 1
                    print(f"    ✅ [{i}/10] {Path(filepath).name[:50]}...")
                    
                    # 保存记录
                    save_result({
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'query': query,
                        'title': title,
                        'url': url,
                        'filetype': 'pdf',
                        'filepath': str(filepath),
                        'status': 'success',
                        'error': None,
                        'recovery': True  # 标记为恢复下载
                    })
                else:
                    total_failed += 1
                    if i <= 3:  # 只显示前3个失败
                        print(f"    ❌ [{i}/10] {error}")
                
                # 短暂延迟
                time.sleep(random.uniform(1, 2))
            
            print(f"  📥 本轮下载: {downloaded_count} 个")
            
            # 每次搜索后延迟
            time.sleep(random.uniform(3, 5))
            
        except KeyboardInterrupt:
            print("\n\n⚠️  用户中断")
            break
        except Exception as e:
            print(f"  ❌ 搜索失败: {e}")
            continue
    
    # 总结
    print("\n" + "="*70)
    print("快速恢复完成")
    print("="*70)
    print(f"✅ 成功下载: {total_downloaded} 个")
    print(f"❌ 失败: {total_failed} 个")
    print(f"📁 保存位置: {DOWNLOADS_DIR}")
    print()
    print("下一步:")
    print("1. 这些文件会被分类器自动处理")
    print("2. continuous_searcher 继续运行，会补充更多文件")
    print("3. 建议运行几轮恢复下载（Ctrl+C 可随时停止）")

if __name__ == "__main__":
    recovery_search()
