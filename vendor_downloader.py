#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
厂商官网下载器 - 直接从各大厂商官网下载电源资料
使用 site: 搜索限定符，质量更高，成功率更高
"""

import json
import time
import random
import requests
import sys
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
import re

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

# 配置
DOWNLOADS_DIR = Path("downloads_continuous")
RESULTS_FILE = DOWNLOADS_DIR / "results.jsonl"
KEYWORDS_FILE = DOWNLOADS_DIR / "explored_keywords.json"
VENDORS_FILE = DOWNLOADS_DIR / "explored_vendors.json"
USED_KEYWORDS_FILE = DOWNLOADS_DIR / "used_keywords.json"

# 问题厂商列表（搜索结果不可靠，暂时跳过）
SKIP_VENDORS = set()  # 暂时不跳过任何厂商

# 默认厂商列表（如果没有探索文件）
DEFAULT_VENDOR_SITES = {
    'TI': 'ti.com',
    'ADI': 'analog.com',
    'ST': 'st.com',
    'Infineon': 'infineon.com',
    'onsemi': 'onsemi.com',
    'NXP': 'nxp.com',
    'Microchip': 'microchip.com',
    'Renesas': 'renesas.com',
    'MPS': 'monolithicpower.com',
    'ROHM': 'rohm.com',
    'Vishay': 'vishay.com',
    'Diodes': 'diodes.com',
    'PI': 'power.com',
    'Navitas': 'navitassemi.com',
    'Richtek': 'richtek.com',
    'AOS': 'aosmd.com',
    'Vicor': 'vicorpower.com'
}

# 默认关键词列表（如果没有探索文件）
DEFAULT_POWER_KEYWORDS = [
    'dc-dc converter datasheet',
    'buck converter',
    'boost converter',
    'flyback converter',
    'power management',
    'voltage regulator',
    'switching regulator',
    'pmic datasheet',
    'power supply design',
    'application note power'
]

def load_used_keywords():
    """加载已使用的关键词"""
    if USED_KEYWORDS_FILE.exists():
        try:
            with open(USED_KEYWORDS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return set(data.get('used', []))
        except Exception:
            pass
    return set()

def save_used_keyword(keyword):
    """保存已使用的关键词"""
    used = load_used_keywords()
    used.add(keyword)
    try:
        with open(USED_KEYWORDS_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'used': list(used),
                'count': len(used)
            }, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️  保存已使用关键词失败: {e}")

def load_explored_data():
    """加载探索得到的关键词和厂商"""
    vendors = DEFAULT_VENDOR_SITES.copy()
    keywords = DEFAULT_POWER_KEYWORDS.copy()
    
    # 尝试加载探索的关键词
    if KEYWORDS_FILE.exists():
        try:
            with open(KEYWORDS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                explored_keywords = data.get('keywords', [])
                if explored_keywords:
                    print(f"📥 加载 Gemini 探索的 {len(explored_keywords)} 个关键词")
                    keywords = explored_keywords
        except Exception as e:
            print(f"⚠️  加载关键词文件失败: {e}")
    
    # 尝试加载探索的厂商
    if VENDORS_FILE.exists():
        try:
            with open(VENDORS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                explored_vendors = data.get('vendors', {})
                if explored_vendors:
                    print(f"📥 加载 Gemini 探索的 {len(explored_vendors)} 个厂商")
                    vendors.update(explored_vendors)
        except Exception as e:
            print(f"⚠️  加载厂商文件失败: {e}")
    
    # 过滤掉已使用的关键词
    used_keywords = load_used_keywords()
    if used_keywords:
        original_count = len(keywords)
        keywords = [k for k in keywords if k not in used_keywords]
        filtered_count = original_count - len(keywords)
        if filtered_count > 0:
            print(f"🔄 过滤掉 {filtered_count} 个已使用的关键词，剩余 {len(keywords)} 个")
    
    return vendors, keywords

# 在启动时加载
VENDOR_SITES, POWER_KEYWORDS = load_explored_data()

def sanitize_filename(title: str, max_length: int = 200) -> str:
    """清理文件名"""
    filename = re.sub(r'[<>:"/\\|?*]', '', title)
    if len(filename) > max_length:
        filename = filename[:max_length]
    filename = filename.strip('. ')
    return filename or "untitled"

def is_pdf_url(url: str) -> bool:
    """判断是否是PDF URL"""
    url_lower = url.lower()
    if url_lower.endswith('.pdf'):
        return True
    
    pdf_patterns = [
        '/pdf/', '/lit/', '/datasheet/', '/ds/',
        'filetype=pdf', 'type=pdf', '.pdf?',
        '/media/', '/technical-documentation/',
        '/application-note/', '/an/'
    ]
    return any(p in url_lower for p in pdf_patterns)

def download_pdf(url: str, vendor_dir: Path, title: str) -> tuple:
    """下载PDF"""
    try:
        filename = sanitize_filename(title)
        if not filename.lower().endswith('.pdf'):
            filename += '.pdf'
        
        filepath = vendor_dir / filename
        
        if filepath.exists():
            return True, str(filepath), None
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=30, stream=True)
        response.raise_for_status()
        
        content_type = response.headers.get('Content-Type', '').lower()
        if 'pdf' not in content_type and 'octet-stream' not in content_type:
            return False, None, f"非PDF: {content_type}"
        
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        if filepath.stat().st_size < 1024:
            filepath.unlink()
            return False, None, "文件太小"
        
        return True, str(filepath), None
        
    except Exception as e:
        return False, None, str(e)[:50]

def save_result(result: dict):
    """保存结果"""
    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_FILE, 'a', encoding='utf-8') as f:
        f.write(json.dumps(result, ensure_ascii=False) + '\n')

def search_vendor_site(vendor: str, site: str, keyword: str, max_results: int = 20) -> list:
    """搜索特定厂商官网"""
    query = f"site:{site} {keyword} filetype:pdf"
    
    try:
        with DDGS() as ddgs:
            results = []
            for result in ddgs.text(query, max_results=max_results):
                url = result.get('href', '')
                if is_pdf_url(url) and site in url:
                    results.append({
                        'title': result.get('title', ''),
                        'url': url,
                        'snippet': result.get('body', '')
                    })
            return results
    except Exception as e:
        print(f"    ⚠️  搜索失败: {e}")
        return []

def main():
    # 解析命令行参数
    selected_vendors = None
    if len(sys.argv) > 1:
        # 支持: python vendor_downloader.py TI,ADI,ST
        vendor_arg = sys.argv[1]
        input_vendors = [v.strip() for v in vendor_arg.split(',')]
        
        # 不区分大小写匹配
        vendor_map = {k.upper(): k for k in VENDOR_SITES.keys()}
        selected_vendors = []
        invalid = []
        
        for v in input_vendors:
            v_upper = v.upper()
            if v_upper in vendor_map:
                selected_vendors.append(vendor_map[v_upper])
            else:
                invalid.append(v)
        
        if invalid:
            print(f"❌ 无效的厂商名称: {', '.join(invalid)}")
            print(f"\n可用厂商: {', '.join(VENDOR_SITES.keys())}")
            return
    
    # 过滤厂商列表
    if selected_vendors:
        vendors_to_process = {k: v for k, v in VENDOR_SITES.items() if k in selected_vendors}
    else:
        vendors_to_process = VENDOR_SITES
    
    print("="*70)
    print("厂商官网电源资料下载器")
    print("="*70)
    print(f"目标厂商: {len(vendors_to_process)} 个 - {', '.join(vendors_to_process.keys())}")
    print(f"搜索关键词: {len(POWER_KEYWORDS)} 个")
    print(f"策略: 轮流访问各厂商，避免被识别为机器人")
    print("="*70)
    print()
    
    total_downloaded = 0
    total_searched = 0
    vendor_stats = {vendor: 0 for vendor in vendors_to_process.keys()}
    
    # 外层循环：关键词
    for keyword_idx, keyword in enumerate(POWER_KEYWORDS, 1):
        print(f"\n{'='*70}")
        print(f"关键词 [{keyword_idx}/{len(POWER_KEYWORDS)}]: {keyword}")
        print(f"{'='*70}")
        
        # 内层循环：轮流访问每个厂商
        for vendor, site in vendors_to_process.items():
            # 跳过问题厂商
            if vendor in SKIP_VENDORS:
                print(f"\n  {vendor} ({site}) - ⏭️  跳过（网站不兼容）")
                continue
            
            print(f"\n  {vendor} ({site})")
            
            vendor_dir = DOWNLOADS_DIR / vendor.lower()
            vendor_dir.mkdir(parents=True, exist_ok=True)
            
            results = search_vendor_site(vendor, site, keyword, max_results=150)
            total_searched += 1
            
            if not results:
                print(f"    ⚠️  未找到PDF")
                time.sleep(random.uniform(1, 2))
                continue
            
            print(f"    找到 {len(results)} 个PDF，开始下载...")
            
            # 下载所有找到的PDF（最多100个）
            download_limit = min(len(results), 100)
            downloaded_this_round = 0
            
            for i, result in enumerate(results[:download_limit], 1):
                url = result.get('url', '')
                title = result.get('title', 'Untitled')
                
                success, filepath, error = download_pdf(url, vendor_dir, title)
                
                if success:
                    downloaded_this_round += 1
                    vendor_stats[vendor] += 1
                    total_downloaded += 1
                    if i % 20 == 0 or i <= 3:  # 每20个或前3个显示
                        print(f"      ✅ [{i}/{download_limit}] {Path(filepath).name[:50]}...")
                    
                    save_result({
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'query': f"site:{site} {keyword}",
                        'vendor': vendor,
                        'title': title,
                        'url': url,
                        'filetype': 'pdf',
                        'filepath': str(filepath),
                        'status': 'success',
                        'error': None,
                        'official': True
                    })
                else:
                    if i <= 2:
                        print(f"      ❌ [{i}/{download_limit}] {error}")
                
                time.sleep(random.uniform(0.3, 0.5))
            
            if downloaded_this_round > 0:
                print(f"    📥 本轮下载: {downloaded_this_round} 个")
            
            # 每个厂商后短暂延迟
            time.sleep(random.uniform(1, 2))
        
        # 每个关键词完成后，标记为已使用
        save_used_keyword(keyword)
        
        # 每个关键词后显示进度
        print(f"\n  总计已下载: {total_downloaded} 个")
        time.sleep(random.uniform(2, 3))
    
    print("\n" + "="*70)
    print("下载完成")
    print("="*70)
    print(f"✅ 成功下载: {total_downloaded} 个")
    print(f"🔍 搜索次数: {total_searched} 次")
    print(f"📁 保存位置: {DOWNLOADS_DIR}")
    print()
    print("这些文件质量高，来自官方网站！")
    print("分类器会自动处理这些文件。")
    print()
    
    # 按厂商统计
    if vendor_stats:
        print("各厂商下载统计:")
        for vendor, count in sorted(vendor_stats.items(), key=lambda x: x[1], reverse=True):
            if count > 0:
                print(f"  {vendor}: {count} 个")
    
    # 检查是否有新关键词
    print()
    print("="*70)
    print("提示：")
    print("1. 可重新运行此批处理，会自动加载新关键词")
    print("2. 运行 start_download_only.bat 生成更多关键词")
    print("3. 已用关键词会自动跳过")
    print("="*70)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
        print("已下载的文件已保存")
