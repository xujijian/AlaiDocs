#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DC-DC Datasheet/Application Note 自动下载工具（浏览器版）
使用 Chrome 浏览器自动化，避免被识别为机器人

作者: AI 助手
版本: 2.0.0
日期: 2026-01-26
Python: 3.10+
依赖: selenium, webdriver-manager
"""

import argparse
import csv
import json
import logging
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import unquote, urlparse

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

# 供应商域名白名单（可扩展）
VENDOR_DOMAINS = {
    # 综合型大厂
    "ti": ["ti.com", "www.ti.com"],
    "st": ["st.com", "www.st.com"],
    "analog": ["analog.com", "www.analog.com"],  # 含 Linear Tech/Maxim
    "infineon": ["infineon.com", "www.infineon.com"],  # 含 IR
    "onsemi": ["onsemi.com", "www.onsemi.com"],
    "renesas": ["renesas.com", "www.renesas.com"],  # 含 Intersil
    "nxp": ["nxp.com", "www.nxp.com"],
    "microchip": ["microchip.com", "www.microchip.com"],
    "rohm": ["rohm.com", "www.rohm.com"],
    "toshiba": ["toshiba-semiconductor.com", "www.toshiba-semiconductor.com"],
    "vishay": ["vishay.com", "www.vishay.com"],
    
    # 电源专精厂商
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

# 文件类型魔数（用于验证文件内容）
FILE_MAGIC_NUMBERS = {
    "pdf": [b"%PDF-1."],
    "zip": [b"PK\x03\x04", b"PK\x05\x06"],
}

# 文件大小限制
MIN_FILE_SIZE = 1024  # 1KB，过滤错误页面
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB

# ============================================================================
# 日志配置
# ============================================================================

def setup_logging(debug: bool = False) -> logging.Logger:
    """配置日志系统"""
    level = logging.DEBUG if debug else logging.INFO
    
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )
    
    logger = logging.getLogger("ddg_fetcher_browser")
    logger.setLevel(level)
    
    return logger


# ============================================================================
# 工具函数
# ============================================================================

def safe_filename(name: str, max_length: int = 200) -> str:
    """生成安全的文件名"""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = name.strip()
    name = name.lstrip(". ")
    
    if not name:
        name = "unnamed"
    
    if len(name) > max_length:
        name_part, ext = name.rsplit(".", 1) if "." in name else (name, "")
        available = max_length - len(ext) - 1 if ext else max_length
        name = name_part[:available] + ("." + ext if ext else "")
    
    return name


def domain_matches_whitelist(url: str, whitelist: Set[str]) -> bool:
    """检查 URL 域名是否在白名单中"""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        if domain in whitelist:
            return True
        
        for allowed in whitelist:
            if domain.endswith("." + allowed) or domain == allowed:
                return True
        
        return False
    except Exception:
        return False


def is_likely_pdf_url(url: str) -> bool:
    """通过 URL 判断是否可能是 PDF"""
    url_lower = url.lower()
    return (
        url_lower.endswith(".pdf") or
        "/pdf/" in url_lower or
        "datasheet" in url_lower or
        "application-note" in url_lower
    )


def check_file_magic(filepath: Path, expected_type: str) -> bool:
    """检查文件魔数是否匹配期望类型"""
    if not filepath.exists() or filepath.stat().st_size < 4:
        return False
    
    try:
        with open(filepath, "rb") as f:
            header = f.read(10)
        
        magic_numbers = FILE_MAGIC_NUMBERS.get(expected_type, [])
        return any(header.startswith(magic) for magic in magic_numbers)
    except Exception:
        return False


# ============================================================================
# 浏览器管理类
# ============================================================================

class BrowserManager:
    """Chrome 浏览器管理器"""
    
    def __init__(self, logger: logging.Logger, headless: bool = False, download_dir: str = None):
        self.logger = logger
        self.headless = headless
        self.download_dir = download_dir or str(Path.cwd() / "downloads")
        self.driver = None
    
    def start(self):
        """启动 Chrome 浏览器"""
        self.logger.info("正在启动 Chrome 浏览器...")
        
        # 配置 Chrome 选项
        chrome_options = Options()
        
        if self.headless:
            chrome_options.add_argument("--headless=new")
            self.logger.info("无头模式：已启用")
        else:
            self.logger.info("无头模式：已禁用（可看到浏览器窗口）")
        
        # 基本选项
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        
        # 设置下载目录（必须使用绝对路径）
        download_path = Path(self.download_dir).resolve()
        download_path.mkdir(parents=True, exist_ok=True)
        
        prefs = {
            "download.default_directory": str(download_path),  # 绝对路径
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True,  # 强制下载PDF而不是预览
            "plugins.plugins_disabled": ["Chrome PDF Viewer"],  # 禁用PDF查看器
            "pdfjs.disabled": True,  # 禁用内置PDF阅读器
            "safebrowsing.enabled": False,
            "safebrowsing.disable_download_protection": True
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        # 允许自动下载
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        
        # 用户代理
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        try:
            # 使用缓存的 ChromeDriver
            chromedriver_path = r"C:\Users\xx2j\.wdm\drivers\chromedriver\win64\144.0.7559.96\chromedriver-win32\chromedriver.exe"
            if Path(chromedriver_path).exists():
                self.logger.info(f"使用缓存的 ChromeDriver: {chromedriver_path}")
                service = Service(chromedriver_path)
            else:
                # 如果缓存不存在，尝试自动下载
                service = Service(ChromeDriverManager(chrome_type=ChromeType.GOOGLE).install())
            
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # 隐藏 webdriver 特征
            self.driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {
                    "source": """
                        Object.defineProperty(navigator, 'webdriver', {
                            get: () => undefined
                        })
                    """
                }
            )
            
            self.driver.set_page_load_timeout(30)
            
            # 启用下载行为监控
            self.driver.execute_cdp_cmd("Page.setDownloadBehavior", {
                "behavior": "allow",
                "downloadPath": str(download_path)
            })
            
            self.logger.info(f"✓ Chrome 浏览器启动成功")
            self.logger.info(f"  下载目录: {download_path}")
            
        except Exception as e:
            self.logger.error(f"启动浏览器失败: {e}")
            raise
    
    def quit(self):
        """关闭浏览器"""
        if self.driver:
            try:
                self.driver.quit()
                self.logger.info("浏览器已关闭")
            except Exception as e:
                self.logger.error(f"关闭浏览器失败: {e}")
    
    def get(self, url: str, timeout: int = 30) -> bool:
        """访问 URL"""
        try:
            self.logger.debug(f"访问: {url}")
            self.driver.get(url)
            time.sleep(2)  # 等待页面稳定
            return True
        except TimeoutException:
            self.logger.error(f"访问超时: {url}")
            return False
        except WebDriverException as e:
            self.logger.error(f"访问失败: {e}")
            return False


# ============================================================================
# DuckDuckGo 搜索器类（浏览器版）
# ============================================================================

class DDGSearcherBrowser:
    """使用 Chrome 浏览器执行 DuckDuckGo 搜索"""
    
    def __init__(self, browser: BrowserManager, logger: logging.Logger, sleep_interval: float = 3.0):
        self.browser = browser
        self.logger = logger
        self.sleep_interval = sleep_interval
    
    def search(self, query: str, max_results: int = 20) -> List[Dict[str, str]]:
        """执行搜索"""
        results = []
        
        try:
            self.logger.info(f"搜索: {query}")
            
            # 构建 DuckDuckGo 搜索 URL
            from urllib.parse import quote
            search_url = f"https://duckduckgo.com/?q={quote(query)}&t=h_&ia=web"
            
            if not self.browser.get(search_url):
                return results
            
            # 等待搜索结果加载
            try:
                WebDriverWait(self.browser.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "article[data-testid='result']"))
                )
            except TimeoutException:
                self.logger.warning("搜索结果加载超时")
                return results
            
            # 提取搜索结果
            result_elements = self.browser.driver.find_elements(
                By.CSS_SELECTOR, "article[data-testid='result']"
            )
            
            self.logger.debug(f"找到 {len(result_elements)} 个原始结果")
            
            for elem in result_elements[:max_results]:
                try:
                    # 提取标题
                    title_elem = elem.find_element(By.CSS_SELECTOR, "h2")
                    title = title_elem.text.strip()
                    
                    # 提取链接
                    link_elem = elem.find_element(By.CSS_SELECTOR, "a[data-testid='result-title-a']")
                    url = link_elem.get_attribute("href")
                    
                    # 提取摘要
                    try:
                        snippet_elem = elem.find_element(By.CSS_SELECTOR, "div[data-result='snippet']")
                        body = snippet_elem.text.strip()
                    except:
                        body = ""
                    
                    if url and title:
                        results.append({
                            "title": title,
                            "url": url,
                            "body": body
                        })
                        self.logger.debug(f"  - {title[:50]}... ({url})")
                
                except Exception as e:
                    self.logger.debug(f"提取结果失败: {e}")
                    continue
            
            self.logger.info(f"✓ 找到 {len(results)} 个有效结果")
            
            # 限速
            time.sleep(self.sleep_interval)
            
        except Exception as e:
            self.logger.error(f"搜索失败: {e}")
        
        return results


# ============================================================================
# 下载器类（浏览器版）
# ============================================================================

class DownloaderBrowser:
    """使用 Chrome 浏览器下载文件"""
    
    def __init__(self, browser: BrowserManager, logger: logging.Logger):
        self.browser = browser
        self.logger = logger
    
    def download_file(
        self,
        url: str,
        output_path: Path,
        expected_type: Optional[str] = None,
        timeout: int = 30
    ) -> Tuple[bool, Optional[str]]:
        """
        使用浏览器下载文件
        
        返回: (成功标志, 错误信息)
        """
        try:
            self.logger.info(f"→ 浏览器下载: {url}")
            
            # 记录开始时间（在访问 URL 之前）
            download_start_time = time.time()
            
            # 清空临时下载目录，避免旧文件干扰检测
            download_dir = Path(self.browser.download_dir).resolve()
            if download_dir.exists():
                for old_file in download_dir.glob("*"):
                    try:
                        if old_file.is_file():
                            old_file.unlink()
                            self.logger.debug(f"清理旧文件: {old_file.name}")
                    except Exception as e:
                        self.logger.debug(f"清理失败: {old_file.name} - {e}")
            
            # 访问 URL，浏览器会自动触发下载
            if not self.browser.get(url):
                return False, "无法访问 URL"
            
            self.logger.info(f"✓ 页面已加载，等待下载开始...")
            
            # 等待下载完成
            download_dir = Path(self.browser.download_dir).resolve()
            self.logger.debug(f"下载目录: {download_dir}")
            downloaded_file = self._wait_for_download(download_dir, timeout, download_start_time)
            
            if not downloaded_file:
                return False, "下载超时或失败"
            
            # 验证文件
            file_size = downloaded_file.stat().st_size
            
            if file_size < MIN_FILE_SIZE:
                downloaded_file.unlink()
                return False, f"文件太小: {file_size} bytes"
            
            if file_size > MAX_FILE_SIZE:
                downloaded_file.unlink()
                return False, f"文件太大: {file_size} bytes"
            
            # 移动到目标路径
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 等待文件不再被占用
            max_retries = 5
            for i in range(max_retries):
                try:
                    downloaded_file.rename(output_path)
                    break
                except PermissionError:
                    if i < max_retries - 1:
                        self.logger.debug(f"文件被占用，等待 2 秒后重试... ({i+1}/{max_retries})")
                        time.sleep(2)
                    else:
                        # 最后尝试复制而不是移动
                        import shutil
                        shutil.copy2(downloaded_file, output_path)
                        self.logger.warning(f"使用复制而不是移动: {downloaded_file.name}")
            
            # 验证魔数
            if expected_type and not check_file_magic(output_path, expected_type):
                self.logger.warning(f"文件魔数不匹配: {expected_type}")
            
            self.logger.info(f"✓ 下载成功: {output_path.name} ({file_size} bytes)")
            return True, None
        
        except Exception as e:
            self.logger.error(f"下载失败: {e}")
            return False, str(e)
    
    def _wait_for_download(self, download_dir: Path, timeout: int, start_time: float) -> Optional[Path]:
        """等待下载完成 - 基于文件修改时间检测"""
        
        self.logger.info(f"⏳ 等待下载完成（超时: {timeout}秒）...")
        
        last_progress_time = start_time
        progress_shown = False
        download_started = False
        
        while time.time() - start_time < timeout:
            # 检查浏览器是否还活着
            try:
                self.browser.driver.title  # 触发一个简单操作检查连接
            except:
                self.logger.error("✗ 浏览器已关闭")
                return None
            
            time.sleep(0.5)  # 短暂等待
            
            # 获取所有文件
            all_files = list(download_dir.glob("*"))
            
            # 检查是否有正在下载的文件
            downloading_files = [
                f for f in all_files 
                if f.name.endswith(('.crdownload', '.tmp', '.part'))
            ]
            
            if downloading_files:
                download_started = True
                elapsed = int(time.time() - start_time)
                # 每5秒显示一次进度
                if time.time() - last_progress_time >= 5:
                    try:
                        file_size = downloading_files[0].stat().st_size
                        self.logger.info(f"  ⬇️ 下载中: {downloading_files[0].name} ({file_size // 1024} KB) - {elapsed}秒")
                        last_progress_time = time.time()
                        progress_shown = True
                    except:
                        pass
                continue
            
            # 如果下载已经开始过，现在没有 .crdownload 文件了，说明下载完成
            # 找最新修改的文件（排除临时文件和 Chrome 管理页面）
            if download_started or time.time() - start_time > 3:  # 3秒后开始检查完成的文件
                completed_files = [
                    f for f in all_files
                    if f.is_file()
                    and f.stat().st_size > MIN_FILE_SIZE
                    and not f.name.endswith(('.crdownload', '.tmp', '.part'))
                    and not f.name.lower().startswith('downloads.')
                    and f.stat().st_mtime > start_time  # 关键：文件修改时间晚于下载开始时间
                ]
                
                if completed_files:
                    # 优先选择PDF文件，然后按修改时间排序
                    pdf_files = [f for f in completed_files if f.name.lower().endswith('.pdf')]
                    target_file = max(pdf_files if pdf_files else completed_files, key=lambda f: f.stat().st_mtime)
                    
                    file_size = target_file.stat().st_size
                    elapsed = int(time.time() - start_time)
                    self.logger.info(f"✓ 下载完成: {target_file.name} ({file_size // 1024} KB) - 用时 {elapsed}秒")
                    return target_file
            
            # 如果超过5秒还没开始下载，显示提示
            if time.time() - start_time > 5 and not progress_shown and not downloading_files:
                self.logger.info(f"  等待下载开始...")
                progress_shown = True
        
        self.logger.error(f"✗ 下载超时（{timeout}秒）- 未检测到下载完成")
        self.logger.info(f"  下载目录: {download_dir}")
        return None


# ============================================================================
# 主程序类
# ============================================================================

class DDGFetcherBrowser:
    """主程序：搜索 + 过滤 + 下载 + 归档（浏览器版）"""
    
    def __init__(self, args):
        self.args = args
        self.logger = setup_logging(args.debug)
        
        # 浏览器管理器
        self.browser = BrowserManager(
            self.logger,
            headless=args.headless,
            download_dir=str(Path(args.out) / "_temp_downloads")
        )
        
        # 组件初始化（浏览器启动后）
        self.searcher = None
        self.downloader = None
        
        # 状态跟踪
        self.downloaded_urls: Set[str] = set()
        self.downloaded_files: Set[Path] = set()
        self.results: List[Dict] = []
        
        # 输出目录
        self.output_dir = Path(args.out)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 结果文件
        self.results_file = self.output_dir / "results.jsonl"
        self.summary_file = self.output_dir / "summary.csv"
        
        # 白名单
        if args.only_whitelist:
            self.whitelist = ALL_WHITELIST_DOMAINS
        else:
            self.whitelist = None
    
    def build_queries(self) -> List[str]:
        """构建查询列表"""
        queries = []
        
        if self.args.query:
            queries.append(self.args.query)
        
        if self.args.queries:
            try:
                with open(self.args.queries, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            queries.append(line)
            except Exception as e:
                self.logger.error(f"读取查询文件失败: {e}")
        
        if self.args.from_file:
            try:
                with open(self.args.from_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        # 跳过注释和空行
                        if not line or line.startswith("#"):
                            continue
                        # 跳过包含占位符的模板行
                        if "<" in line and ">" in line:
                            continue
                        # 添加有效的查询
                        queries.append(line)
                self.logger.info(f"从 {self.args.from_file} 加载了 {len(queries)} 个查询")
            except Exception as e:
                self.logger.error(f"读取模板文件失败: {e}")
        
        if self.args.vendor and self.args.keywords:
            vendor = self.args.vendor.lower()
            keywords = self.args.keywords
            domains = VENDOR_DOMAINS.get(vendor, [])
            if domains:
                site = domains[0]
                query = f"site:{site} {keywords} filetype:pdf"
                queries.append(query)
        
        return queries
    
    def filter_url(self, url: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """过滤 URL"""
        if self.whitelist and not domain_matches_whitelist(url, self.whitelist):
            return False, None, "Domain not in whitelist"
        
        if url in self.downloaded_urls:
            return False, None, "Already downloaded"
        
        filetypes = [ft.strip().lower() for ft in self.args.filetypes.split(",")]
        
        detected_type = None
        if "pdf" in filetypes and is_likely_pdf_url(url):
            detected_type = "pdf"
        
        if detected_type is None:
            return False, None, f"Not matching filetypes: {filetypes}"
        
        return True, detected_type, None
    
    def generate_filepath(
        self,
        url: str,
        title: str,
        vendor: Optional[str],
        filetype: str,
        keywords: Optional[str] = None
    ) -> Path:
        """生成输出文件路径（支持多级目录：vendor/keywords/）"""
        # 第一层：vendor
        if vendor:
            vendor_dir = self.output_dir / vendor
        else:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            vendor_name = None
            
            for v, domains in VENDOR_DOMAINS.items():
                if any(d in domain for d in domains):
                    vendor_name = v
                    break
            
            vendor_dir = self.output_dir / (vendor_name or "unknown")
        
        # 第二层：keywords（如果提供）
        if keywords:
            # 清理 keywords 作为目录名（限制长度，移除特殊字符）
            keywords_clean = safe_filename(keywords, max_length=50)
            subdir = vendor_dir / keywords_clean
        else:
            subdir = vendor_dir
        
        subdir.mkdir(parents=True, exist_ok=True)
        
        if title:
            filename = safe_filename(title)
        else:
            path = unquote(urlparse(url).path)
            filename = safe_filename(Path(path).name or "download")
        
        if not filename.lower().endswith(f".{filetype}"):
            filename += f".{filetype}"
        
        filepath = subdir / filename
        counter = 1
        while filepath in self.downloaded_files or filepath.exists():
            name_part = filename.rsplit(".", 1)[0]
            filepath = subdir / f"{name_part}_{counter}.{filetype}"
            counter += 1
        
        return filepath
    
    def process_search_result(
        self,
        query: str,
        result: Dict[str, str],
        vendor: Optional[str]
    ):
        """处理单个搜索结果"""
        url = result["url"]
        title = result["title"]
        
        keep, filetype, reason = self.filter_url(url)
        if not keep:
            self.logger.debug(f"跳过: {url} ({reason})")
            return
        
        self.logger.info(f"处理: {title[:50]}...")
        self.downloaded_urls.add(url)
        
        # 传递 keywords 参数用于目录分类
        keywords = self.args.keywords if hasattr(self.args, 'keywords') else None
        filepath = self.generate_filepath(url, title, vendor, filetype, keywords)
        
        success, error = self.downloader.download_file(url, filepath, filetype)
        
        record = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "query": query,
            "title": title,
            "url": url,
            "filetype": filetype,
            "filepath": str(filepath) if success else None,
            "status": "success" if success else "failed",
            "error": error
        }
        
        self.results.append(record)
        self.append_to_jsonl(record)
        
        if success:
            self.downloaded_files.add(filepath)
        
        time.sleep(self.args.sleep)
    
    def append_to_jsonl(self, record: Dict):
        """追加一条记录到 JSONL"""
        try:
            with open(self.results_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            self.logger.error(f"写入 JSONL 失败: {e}")
    
    def save_summary_csv(self):
        """保存汇总 CSV"""
        try:
            with open(self.summary_file, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "timestamp", "query", "title", "url", "filetype",
                    "filepath", "status", "error"
                ])
                writer.writeheader()
                writer.writerows(self.results)
            
            self.logger.info(f"汇总已保存: {self.summary_file}")
        except Exception as e:
            self.logger.error(f"保存 CSV 失败: {e}")
    
    def run(self):
        """主运行逻辑"""
        self.logger.info("=" * 60)
        self.logger.info("DC-DC Datasheet 下载工具 v2.0.0 (浏览器版)")
        self.logger.info("=" * 60)
        
        try:
            # 启动浏览器
            self.browser.start()
            
            # 初始化组件
            self.searcher = DDGSearcherBrowser(self.browser, self.logger, self.args.sleep)
            self.downloader = DownloaderBrowser(self.browser, self.logger)
            
            # 构建查询
            queries = self.build_queries()
            
            if not queries:
                self.logger.error("没有查询输入！请使用 --query 或 --queries")
                return 1
            
            self.logger.info(f"总共 {len(queries)} 个查询")
            
            # 执行搜索和下载
            for i, query in enumerate(queries, 1):
                self.logger.info(f"\n[{i}/{len(queries)}] {query}")
                
                results = self.searcher.search(query, max_results=self.args.max_results)
                
                if not results:
                    self.logger.warning("没有搜索结果")
                    continue
                
                for result in results:
                    self.process_search_result(query, result, self.args.vendor)
            
            # 保存汇总
            self.save_summary_csv()
            
            # 打印统计
            self.print_statistics()
            
            return 0
        
        finally:
            # 确保关闭浏览器
            self.browser.quit()
    
    def print_statistics(self):
        """打印统计信息"""
        total = len(self.results)
        success = sum(1 for r in self.results if r["status"] == "success")
        failed = total - success
        
        self.logger.info("\n" + "=" * 60)
        self.logger.info("下载统计")
        self.logger.info("=" * 60)
        self.logger.info(f"总计: {total}")
        self.logger.info(f"成功: {success}")
        self.logger.info(f"失败: {failed}")
        
        if failed > 0:
            error_counts = defaultdict(int)
            for r in self.results:
                if r["status"] == "failed":
                    error_counts[r["error"] or "Unknown"] += 1
            
            self.logger.info("\n失败原因:")
            for error, count in sorted(error_counts.items(), key=lambda x: -x[1]):
                self.logger.info(f"  - {error}: {count}")
        
        self.logger.info(f"\n结果已保存:")
        self.logger.info(f"  - {self.results_file}")
        self.logger.info(f"  - {self.summary_file}")


# ============================================================================
# 命令行入口
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="DC-DC Datasheet/Application Note 自动下载工具（浏览器版）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 单条查询
  python ddg_fetcher_browser.py --query "TI buck converter datasheet" --out downloads

  # 从文件读取查询
  python ddg_fetcher_browser.py --queries queries.txt --out downloads

  # 指定供应商 + 关键词
  python ddg_fetcher_browser.py --vendor ti --keywords "dcdc buck boost" --out downloads

  # 无头模式（后台运行）
  python ddg_fetcher_browser.py --query "test" --headless --max-results 5
        """
    )
    
    # 输入
    input_group = parser.add_argument_group("输入选项")
    input_group.add_argument("--query", type=str, help="单条搜索查询")
    input_group.add_argument("--queries", type=str, help="查询文件路径（每行一个查询）")
    input_group.add_argument("--from-file", type=str, help="从模板文件批量生成查询（支持占位符）")
    input_group.add_argument("--vendor", type=str, 
                            choices=list(VENDOR_DOMAINS.keys()),
                            help="供应商代码")
    input_group.add_argument("--keywords", type=str,
                            help="关键词（与 --vendor 配合使用）")
    
    # 过滤
    filter_group = parser.add_argument_group("过滤选项")
    filter_group.add_argument("--filetypes", type=str, default="pdf",
                             help="文件类型（逗号分隔，默认: pdf）")
    filter_group.add_argument("--only-whitelist", action="store_true",
                             help="只下载白名单域名")
    filter_group.add_argument("--max-results", type=int, default=20,
                             help="每个查询最大结果数（默认: 20）")
    
    # 输出
    output_group = parser.add_argument_group("输出选项")
    output_group.add_argument("--out", type=str, default="downloads",
                             help="输出目录（默认: downloads）")
    
    # 行为
    behavior_group = parser.add_argument_group("行为选项")
    behavior_group.add_argument("--sleep", type=float, default=3.0,
                               help="下载间隔（秒，默认: 3.0）")
    behavior_group.add_argument("--headless", action="store_true",
                               help="无头模式（不显示浏览器窗口）")
    behavior_group.add_argument("--debug", action="store_true",
                               help="启用调试模式")
    
    args = parser.parse_args()
    
    # 验证参数
    if not args.query and not args.queries and not args.from_file and not (args.vendor and args.keywords):
        parser.error("必须提供 --query, --queries, --from-file 或 --vendor + --keywords")
    
    # 运行
    fetcher = DDGFetcherBrowser(args)
    return fetcher.run()


if __name__ == "__main__":
    sys.exit(main())
