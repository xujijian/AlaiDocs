#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google 搜索引擎适配器
基于 googlesearch-python 库实现的 Google 搜索功能

作者: AI 助手
版本: 1.0.0
日期: 2026-01-27
Python: 3.10+
依赖: googlesearch-python, requests, selenium
"""

import logging
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import unquote, urlparse

try:
    from googlesearch import search as google_search
    GOOGLESEARCH_AVAILABLE = True
except ImportError:
    GOOGLESEARCH_AVAILABLE = False
    print("警告: googlesearch-python 库未安装")
    print("请运行: pip install googlesearch-python")

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

# ============================================================================
# 配置常量
# ============================================================================

# 供应商域名白名单（与 ddg_fetcher_browser.py 保持一致）
VENDOR_DOMAINS = {
    "ti": ["ti.com", "www.ti.com"],
    "st": ["st.com", "www.st.com"],
    "analog": ["analog.com", "www.analog.com"],
    "infineon": ["infineon.com", "www.infineon.com"],
    "onsemi": ["onsemi.com", "www.onsemi.com"],
    "renesas": ["renesas.com", "www.renesas.com"],
    "nxp": ["nxp.com", "www.nxp.com"],
    "microchip": ["microchip.com", "www.microchip.com"],
    "rohm": ["rohm.com", "www.rohm.com"],
    "toshiba": ["toshiba-semiconductor.com", "www.toshiba-semiconductor.com"],
    "vishay": ["vishay.com", "www.vishay.com"],
    "mps": ["monolithicpower.com", "www.monolithicpower.com"],
    "pi": ["power.com", "www.power.com"],
    "vicor": ["vicorpower.com", "www.vicorpower.com"],
    "navitas": ["navitassemi.com", "www.navitassemi.com"],
    "diodes": ["diodes.com", "www.diodes.com"],
    "aos": ["aosmd.com", "www.aosmd.com"],
    "richtek": ["richtek.com", "www.richtek.com"],
    "silergy": ["silergy.com", "www.silergy.com"],
}

# 所有白名单域名（扁平化）
ALL_WHITELIST_DOMAINS = set()
for domains in VENDOR_DOMAINS.values():
    ALL_WHITELIST_DOMAINS.update(domains)


class GoogleFetcher:
    """Google 搜索引擎适配器"""
    
    def __init__(
        self,
        output_dir: Path,
        results_limit: int = 50,
        download_limit: int = 20,
        domain_whitelist: Optional[List[str]] = None,
        logger: Optional[logging.Logger] = None,
        headless: bool = True,
        download_timeout: int = 300
    ):
        """
        初始化 Google 搜索器
        
        Args:
            output_dir: 输出目录
            results_limit: 搜索结果数量限制
            download_limit: 下载文件数量限制
            domain_whitelist: 域名白名单（None 则使用默认白名单）
            logger: 日志记录器
            headless: 是否使用无头模式
            download_timeout: 下载超时时间（秒）
        """
        if not GOOGLESEARCH_AVAILABLE:
            raise ImportError("googlesearch-python 库未安装，请运行: pip install googlesearch-python")
        
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.results_limit = results_limit
        self.download_limit = download_limit
        self.domain_whitelist = domain_whitelist or list(ALL_WHITELIST_DOMAINS)
        self.logger = logger or logging.getLogger(__name__)
        self.headless = headless
        self.download_timeout = download_timeout
        
        # 浏览器驱动
        self.driver = None
        self.download_dir = self.output_dir / "_temp_downloads"
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        # 统计信息
        self.stats = {
            "total_queries": 0,
            "total_results": 0,
            "total_downloads": 0,
            "total_size": 0,
            "vendor_downloads": {},
        }
    
    def _init_chrome_driver(self):
        """初始化 Chrome WebDriver"""
        if self.driver:
            return
        
        self.logger.info("🌐 初始化 Chrome 浏览器...")
        
        options = Options()
        
        if self.headless:
            options.add_argument("--headless=new")
        
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        # 下载设置
        prefs = {
            "download.default_directory": str(self.download_dir.absolute()),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True,
            "safebrowsing.enabled": False,
        }
        options.add_experimental_option("prefs", prefs)
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            self.logger.info("✅ Chrome 浏览器已启动")
        except Exception as e:
            self.logger.error(f"❌ 启动 Chrome 失败: {e}")
            raise
    
    def search(self, query: str) -> List[Dict]:
        """
        使用 Google 搜索
        
        Args:
            query: 搜索查询
            
        Returns:
            List[Dict]: 搜索结果列表，每个结果包含 url, title, description
        """
        self.logger.info(f"🔍 Google 搜索: {query}")
        self.stats["total_queries"] += 1
        
        results = []
        
        try:
            # 使用 googlesearch-python 库搜索
            search_results = google_search(
                query,
                num_results=self.results_limit * 2,  # 多搜索一些确保有足够结果
                lang="en",
                sleep_interval=2,  # 两次请求之间暂停2秒
                timeout=30
            )
            
            for url in search_results:
                # 检查域名白名单
                if not self._is_whitelisted_domain(url):
                    continue
                
                # 检查是否是 PDF
                if not self._is_pdf_url(url):
                    continue
                
                results.append({
                    "url": url,
                    "title": self._extract_title_from_url(url),
                    "description": f"来自 {urlparse(url).netloc}",
                    "vendor": self._get_vendor_from_url(url)
                })
                
                if len(results) >= self.results_limit:
                    break
            
            self.logger.info(f"✅ 找到 {len(results)} 个结果")
            self.stats["total_results"] += len(results)
            
        except Exception as e:
            self.logger.error(f"❌ Google 搜索失败: {e}")
        
        return results
    
    def download_result(self, result: Dict) -> Optional[Path]:
        """
        下载单个搜索结果
        
        Args:
            result: 搜索结果字典
            
        Returns:
            Optional[Path]: 下载成功返回文件路径，否则返回 None
        """
        url = result["url"]
        vendor = result.get("vendor", "unknown")
        
        self.logger.info(f"📥 下载: {url}")
        
        try:
            if not self.driver:
                self._init_chrome_driver()
            
            # 清空临时下载目录
            for file in self.download_dir.iterdir():
                if file.is_file():
                    file.unlink()
            
            # 使用浏览器下载
            self.driver.get(url)
            
            # 等待下载完成
            downloaded_file = self._wait_for_download()
            
            if not downloaded_file:
                self.logger.warning(f"⚠️  下载失败: {url}")
                return None
            
            # 移动到供应商目录
            vendor_dir = self.output_dir / vendor
            vendor_dir.mkdir(parents=True, exist_ok=True)
            
            dest_path = vendor_dir / downloaded_file.name
            
            # 避免重名
            counter = 1
            while dest_path.exists():
                stem = downloaded_file.stem
                suffix = downloaded_file.suffix
                dest_path = vendor_dir / f"{stem}_{counter}{suffix}"
                counter += 1
            
            downloaded_file.rename(dest_path)
            
            file_size = dest_path.stat().st_size
            self.stats["total_downloads"] += 1
            self.stats["total_size"] += file_size
            self.stats["vendor_downloads"][vendor] = self.stats["vendor_downloads"].get(vendor, 0) + 1
            
            self.logger.info(f"✅ 已保存: {dest_path.name} ({file_size / 1024:.1f} KB)")
            
            return dest_path
            
        except Exception as e:
            self.logger.error(f"❌ 下载失败 {url}: {e}")
            return None
    
    def _wait_for_download(self, timeout: int = None) -> Optional[Path]:
        """等待下载完成"""
        timeout = timeout or self.download_timeout
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            files = list(self.download_dir.glob("*"))
            
            # 过滤掉临时文件
            completed_files = [
                f for f in files
                if f.is_file() and not f.name.endswith((".crdownload", ".tmp"))
            ]
            
            if completed_files:
                # 等待文件大小稳定
                time.sleep(2)
                return completed_files[0]
            
            time.sleep(1)
        
        return None
    
    def _is_whitelisted_domain(self, url: str) -> bool:
        """检查 URL 是否在域名白名单中"""
        try:
            domain = urlparse(url).netloc.lower()
            return any(wd in domain for wd in self.domain_whitelist)
        except:
            return False
    
    def _is_pdf_url(self, url: str) -> bool:
        """检查 URL 是否指向 PDF 文件"""
        try:
            url_lower = url.lower()
            if url_lower.endswith(".pdf"):
                return True
            parsed = urlparse(url)
            if ".pdf" in parsed.path.lower():
                return True
            return False
        except:
            return False
    
    def _extract_title_from_url(self, url: str) -> str:
        """从 URL 提取标题"""
        try:
            parsed = urlparse(url)
            filename = parsed.path.split("/")[-1]
            title = filename.replace(".pdf", "").replace(".PDF", "")
            title = unquote(title)
            title = title.replace("_", " ").replace("-", " ").replace("+", " ")
            return title[:100] if title else "未知标题"
        except:
            return "未知标题"
    
    def _get_vendor_from_url(self, url: str) -> str:
        """从 URL 识别供应商"""
        try:
            domain = urlparse(url).netloc.lower()
            for vendor, domains in VENDOR_DOMAINS.items():
                if any(d in domain for d in domains):
                    return vendor
            return "unknown"
        except:
            return "unknown"
    
    def fetch_and_download(self, query: str) -> Dict:
        """
        搜索并下载（完整流程）
        
        Args:
            query: 搜索查询
            
        Returns:
            Dict: 统计信息
        """
        results = self.search(query)
        
        downloaded_count = 0
        for result in results[:self.download_limit]:
            if self.download_result(result):
                downloaded_count += 1
        
        return {
            "query": query,
            "results_found": len(results),
            "files_downloaded": downloaded_count,
        }
    
    def close(self):
        """关闭浏览器"""
        if self.driver:
            try:
                self.driver.quit()
                self.logger.info("🔒 Chrome 浏览器已关闭")
            except:
                pass
            self.driver = None
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return self.stats.copy()
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.close()


# ============================================================================
# 命令行接口（用于测试）
# ============================================================================

def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Google 搜索引擎测试工具")
    parser.add_argument("query", help="搜索查询")
    parser.add_argument("-o", "--output", default="./downloads_google", help="输出目录")
    parser.add_argument("-r", "--results", type=int, default=20, help="搜索结果数量")
    parser.add_argument("-d", "--downloads", type=int, default=10, help="下载数量限制")
    parser.add_argument("--visible", action="store_true", help="显示浏览器窗口")
    parser.add_argument("--debug", action="store_true", help="调试模式")
    
    args = parser.parse_args()
    
    # 配置日志
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    logger = logging.getLogger(__name__)
    
    try:
        with GoogleFetcher(
            output_dir=args.output,
            results_limit=args.results,
            download_limit=args.downloads,
            headless=not args.visible,
            logger=logger
        ) as fetcher:
            logger.info(f"🚀 开始搜索: {args.query}")
            result = fetcher.fetch_and_download(args.query)
            
            logger.info("\n" + "="*60)
            logger.info("📊 统计信息")
            logger.info("="*60)
            logger.info(f"搜索结果: {result['results_found']}")
            logger.info(f"下载文件: {result['files_downloaded']}")
            
            stats = fetcher.get_stats()
            logger.info(f"总下载量: {stats['total_size'] / (1024*1024):.2f} MB")
            logger.info(f"供应商分布: {dict(stats['vendor_downloads'])}")
            logger.info("="*60)
    
    except KeyboardInterrupt:
        logger.info("\n⚠️  用户中断")
    except Exception as e:
        logger.error(f"\n❌ 错误: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
