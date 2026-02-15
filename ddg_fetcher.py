#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DC-DC Datasheet/Application Note 自动下载工具
使用 DuckDuckGo 搜索并下载 PDF/ZIP 文件

作者: AI 助手
版本: 1.0.0
日期: 2026-01-26
Python: 3.10+
"""

import argparse
import csv
import hashlib
import json
import logging
import mimetypes
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import unquote, urlparse

import requests
from duckduckgo_search import DDGS

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

# HTTP 配置
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# 重试配置
MAX_RETRIES = 3
INITIAL_BACKOFF = 2  # 秒
MAX_BACKOFF = 60     # 秒

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
    
    logger = logging.getLogger("ddg_fetcher")
    logger.setLevel(level)
    
    return logger


# ============================================================================
# 工具函数
# ============================================================================

def safe_filename(name: str, max_length: int = 200) -> str:
    """
    生成安全的文件名
    - 移除非法字符
    - 限制长度
    - 保留扩展名
    """
    # 移除非法字符
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = name.strip()
    
    # 移除前导点和空格（Windows 不允许）
    name = name.lstrip(". ")
    
    if not name:
        name = "unnamed"
    
    # 限制长度，保留扩展名
    if len(name) > max_length:
        name_part, ext = name.rsplit(".", 1) if "." in name else (name, "")
        available = max_length - len(ext) - 1 if ext else max_length
        name = name_part[:available] + ("." + ext if ext else "")
    
    return name


def get_url_hash(url: str) -> str:
    """生成 URL 的短哈希（用于去重）"""
    return hashlib.md5(url.encode()).hexdigest()[:8]


def is_likely_pdf_url(url: str) -> bool:
    """通过 URL 判断是否可能是 PDF"""
    url_lower = url.lower()
    return (
        url_lower.endswith(".pdf") or
        "/pdf/" in url_lower or
        "datasheet" in url_lower or
        "application-note" in url_lower
    )


def is_likely_zip_url(url: str) -> bool:
    """通过 URL 判断是否可能是 ZIP"""
    url_lower = url.lower()
    return url_lower.endswith(".zip") or "/download/" in url_lower


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


def domain_matches_whitelist(url: str, whitelist: Set[str]) -> bool:
    """检查 URL 域名是否在白名单中"""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # 精确匹配
        if domain in whitelist:
            return True
        
        # 子域名匹配
        for allowed in whitelist:
            if domain.endswith("." + allowed) or domain == allowed:
                return True
        
        return False
    except Exception:
        return False


# ============================================================================
# 下载器类
# ============================================================================

class Downloader:
    """
    HTTP 下载器
    支持：重试、超时、断点续传检测、Content-Type 验证
    """
    
    def __init__(self, logger: logging.Logger, timeout: int = 30):
        self.logger = logger
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
    
    def head_request(self, url: str, max_retries: int = 2) -> Optional[requests.Response]:
        """发送 HEAD 请求获取元信息"""
        for attempt in range(max_retries):
            try:
                self.logger.debug(f"HEAD {url} (attempt {attempt + 1})")
                resp = self.session.head(
                    url,
                    timeout=self.timeout,
                    allow_redirects=True,
                    headers={"Range": "bytes=0-0"}  # 有些服务器需要 Range
                )
                return resp
            except requests.RequestException as e:
                self.logger.debug(f"HEAD 失败: {e}")
                if attempt == max_retries - 1:
                    return None
                time.sleep(INITIAL_BACKOFF * (2 ** attempt))
        return None
    
    def download_file(
        self,
        url: str,
        output_path: Path,
        expected_type: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        下载文件到指定路径
        
        返回: (成功标志, 错误信息)
        """
        # 先用 HEAD 检查
        head_resp = self.head_request(url)
        if head_resp is None:
            return False, "HEAD request failed"
        
        if head_resp.status_code >= 400:
            return False, f"HTTP {head_resp.status_code}"
        
        # 检查 Content-Type
        content_type = head_resp.headers.get("Content-Type", "").lower()
        self.logger.debug(f"Content-Type: {content_type}")
        
        if expected_type == "pdf" and "pdf" not in content_type:
            if "html" in content_type or "text" in content_type:
                return False, f"Wrong Content-Type: {content_type}"
        
        # 检查文件大小
        content_length = head_resp.headers.get("Content-Length")
        if content_length:
            size = int(content_length)
            if size < MIN_FILE_SIZE:
                return False, f"File too small: {size} bytes"
            if size > MAX_FILE_SIZE:
                return False, f"File too large: {size} bytes"
            self.logger.debug(f"File size: {size} bytes")
        
        # 下载文件（带重试）
        for attempt in range(MAX_RETRIES):
            try:
                self.logger.debug(f"GET {url} (attempt {attempt + 1})")
                resp = self.session.get(
                    url,
                    timeout=self.timeout,
                    stream=True,
                    allow_redirects=True
                )
                
                if resp.status_code >= 400:
                    return False, f"HTTP {resp.status_code}"
                
                # 流式写入文件
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(output_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                # 验证文件
                if not output_path.exists():
                    return False, "File not created"
                
                file_size = output_path.stat().st_size
                if file_size < MIN_FILE_SIZE:
                    output_path.unlink()
                    return False, f"Downloaded file too small: {file_size} bytes"
                
                # 验证魔数
                if expected_type and not check_file_magic(output_path, expected_type):
                    self.logger.warning(f"File magic number mismatch for {expected_type}")
                    # 不删除，但记录警告
                
                self.logger.info(f"✓ Downloaded: {output_path.name} ({file_size} bytes)")
                return True, None
            
            except requests.RequestException as e:
                self.logger.debug(f"下载失败: {e}")
                if attempt == MAX_RETRIES - 1:
                    return False, str(e)
                
                backoff = min(INITIAL_BACKOFF * (2 ** attempt), MAX_BACKOFF)
                self.logger.debug(f"等待 {backoff}s 后重试...")
                time.sleep(backoff)
        
        return False, "Max retries exceeded"


# ============================================================================
# 搜索器类
# ============================================================================

class DDGSearcher:
    """DuckDuckGo 搜索封装"""
    
    def __init__(self, logger: logging.Logger, sleep_interval: float = 2.0):
        self.logger = logger
        self.sleep_interval = sleep_interval
    
    def search(
        self,
        query: str,
        max_results: int = 20,
        region: str = "wt-wt"
    ) -> List[Dict[str, str]]:
        """
        执行搜索
        
        返回: [{"title": ..., "url": ..., "body": ...}, ...]
        """
        results = []
        
        try:
            self.logger.info(f"搜索: {query}")
            
            with DDGS() as ddgs:
                search_results = ddgs.text(
                    query,
                    region=region,
                    safesearch="off",
                    max_results=max_results
                )
                
                for r in search_results:
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "body": r.get("body", "")
                    })
            
            self.logger.info(f"找到 {len(results)} 个结果")
            
            # 限速
            time.sleep(self.sleep_interval)
            
        except Exception as e:
            self.logger.error(f"搜索失败: {e}")
        
        return results


# ============================================================================
# 主程序类
# ============================================================================

class DDGFetcher:
    """主程序：搜索 + 过滤 + 下载 + 归档"""
    
    def __init__(self, args):
        self.args = args
        self.logger = setup_logging(args.debug)
        
        # 组件初始化
        self.searcher = DDGSearcher(self.logger, sleep_interval=args.sleep)
        self.downloader = Downloader(self.logger, timeout=args.timeout)
        
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
        
        # 单查询
        if self.args.query:
            queries.append(self.args.query)
        
        # 文件查询
        if self.args.queries:
            try:
                with open(self.args.queries, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            queries.append(line)
            except Exception as e:
                self.logger.error(f"读取查询文件失败: {e}")
        
        # 自动生成查询
        if self.args.vendor and self.args.keywords:
            vendor = self.args.vendor.lower()
            keywords = self.args.keywords
            
            # 获取域名
            domains = VENDOR_DOMAINS.get(vendor, [])
            if domains:
                site = domains[0]
                query = f"site:{site} {keywords} filetype:pdf"
                queries.append(query)
        
        return queries
    
    def filter_url(self, url: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        过滤 URL
        
        返回: (是否保留, 文件类型, 拒绝理由)
        """
        # 白名单检查
        if self.whitelist and not domain_matches_whitelist(url, self.whitelist):
            return False, None, "Domain not in whitelist"
        
        # 去重
        if url in self.downloaded_urls:
            return False, None, "Already downloaded"
        
        # 文件类型判断
        filetypes = [ft.strip().lower() for ft in self.args.filetypes.split(",")]
        
        detected_type = None
        if "pdf" in filetypes and is_likely_pdf_url(url):
            detected_type = "pdf"
        elif "zip" in filetypes and is_likely_zip_url(url):
            detected_type = "zip"
        
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
            # 尝试从域名提取
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
        
        # 生成文件名
        # 优先使用标题，其次使用 URL 路径
        if title:
            filename = safe_filename(title)
        else:
            path = unquote(urlparse(url).path)
            filename = safe_filename(Path(path).name or "download")
        
        # 确保扩展名
        if not filename.lower().endswith(f".{filetype}"):
            filename += f".{filetype}"
        
        # 去重处理（文件名冲突）
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
        
        # 过滤
        keep, filetype, reason = self.filter_url(url)
        if not keep:
            self.logger.debug(f"跳过: {url} ({reason})")
            return
        
        self.logger.info(f"处理: {title[:50]}...")
        
        # 标记为已处理
        self.downloaded_urls.add(url)
        
        # 生成文件路径（传递 keywords 用于目录分类）
        keywords = self.args.keywords if hasattr(self.args, 'keywords') else None
        filepath = self.generate_filepath(url, title, vendor, filetype, keywords)
        
        # 下载
        success, error = self.downloader.download_file(url, filepath, filetype)
        
        # 记录结果
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
        
        # 立即写入 JSONL（防止崩溃丢失）
        self.append_to_jsonl(record)
        
        if success:
            self.downloaded_files.add(filepath)
        
        # 限速
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
        self.logger.info("DC-DC Datasheet 下载工具 v1.0.0")
        self.logger.info("=" * 60)
        
        # 构建查询
        queries = self.build_queries()
        
        if not queries:
            self.logger.error("没有查询输入！请使用 --query 或 --queries")
            return 1
        
        self.logger.info(f"总共 {len(queries)} 个查询")
        
        # 执行搜索和下载
        for i, query in enumerate(queries, 1):
            self.logger.info(f"\n[{i}/{len(queries)}] {query}")
            
            # 搜索
            results = self.searcher.search(query, max_results=self.args.max_results)
            
            if not results:
                self.logger.warning("没有搜索结果")
                continue
            
            # 处理每个结果
            for result in results:
                self.process_search_result(query, result, self.args.vendor)
        
        # 保存汇总
        self.save_summary_csv()
        
        # 打印统计
        self.print_statistics()
        
        return 0
    
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
        
        # 失败原因统计
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
        description="DC-DC Datasheet/Application Note 自动下载工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 单条查询
  python ddg_fetcher.py --query "TI buck converter datasheet" --out downloads

  # 从文件读取查询
  python ddg_fetcher.py --queries queries.txt --out downloads

  # 指定供应商 + 关键词
  python ddg_fetcher.py --vendor ti --keywords "dcdc buck boost" --out downloads

  # 只下载白名单域名
  python ddg_fetcher.py --query "dcdc" --only-whitelist --out downloads

  # 调试模式
  python ddg_fetcher.py --query "test" --debug --max-results 5
        """
    )
    
    # 输入
    input_group = parser.add_argument_group("输入选项")
    input_group.add_argument("--query", type=str, help="单条搜索查询")
    input_group.add_argument("--queries", type=str, help="查询文件路径（每行一个查询）")
    input_group.add_argument("--vendor", type=str, 
                            choices=list(VENDOR_DOMAINS.keys()),
                            help="供应商代码（综合大厂: ti/st/analog/infineon/onsemi/renesas/nxp/microchip/rohm/toshiba/vishay；电源专精: mps/pi/vicor/navitas/diodes/aos/richtek/silergy）")
    input_group.add_argument("--keywords", type=str,
                            help="关键词（与 --vendor 配合使用）")
    
    # 过滤
    filter_group = parser.add_argument_group("过滤选项")
    filter_group.add_argument("--filetypes", type=str, default="pdf,zip",
                             help="文件类型（逗号分隔，默认: pdf,zip）")
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
    behavior_group.add_argument("--sleep", type=float, default=2.0,
                               help="下载间隔（秒，默认: 2.0）")
    behavior_group.add_argument("--timeout", type=int, default=30,
                               help="HTTP 超时（秒，默认: 30）")
    behavior_group.add_argument("--debug", action="store_true",
                               help="启用调试模式")
    
    args = parser.parse_args()
    
    # 验证参数
    if not args.query and not args.queries and not (args.vendor and args.keywords):
        parser.error("必须提供 --query, --queries 或 --vendor + --keywords")
    
    # 运行
    fetcher = DDGFetcher(args)
    return fetcher.run()


if __name__ == "__main__":
    sys.exit(main())
