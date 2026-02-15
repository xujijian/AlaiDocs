#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动化持续搜索下载系统
整合 ChatGPT 关键词生成 + DuckDuckGo 搜索 + 自动下载

作者: AI 助手
版本: 1.0.0
日期: 2026-01-26
Python: 3.10+
"""

import argparse
import json
import logging
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from chatgpt_keyword_generator import GeminiKeywordGenerator
from keyword_manager import KeywordManager

# 尝试导入 ddg_fetcher_browser 或 ddg_fetcher（优先）或 Google Fetcher
try:
    from ddg_fetcher_browser import DDGFetcher
    USE_BROWSER = True
    USE_GOOGLE = False
except ImportError:
    try:
        from ddg_fetcher import DDGFetcher
        USE_BROWSER = False
        USE_GOOGLE = False
    except ImportError:
        from google_fetcher import GoogleFetcher
        USE_GOOGLE = True
        USE_BROWSER = False


class ContinuousSearcher:
    """持续搜索下载器"""
    
    def __init__(
        self,
        output_dir: Path,
        keyword_db_path: Path,
        config: Optional[Dict] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        初始化持续搜索器
        
        Args:
            output_dir: 输出目录
            keyword_db_path: 关键词数据库路径
            config: 配置字典
            logger: 日志记录器
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger = logger or logging.getLogger(__name__)
        self.config = config or self._default_config()
        
        # 初始化组件
        self.keyword_manager = KeywordManager(keyword_db_path, self.logger)
        self.chatgpt_generator = None
        self.google_fetcher = None  # Google 搜索器
        self.ddg_fetcher = None     # DuckDuckGo 搜索器（备用）
        self.ddgs = None            # DuckDuckGo 简单搜索（API）
        
        # 运行状态
        self.is_running = False
        self.current_round = 0
        self.total_files_downloaded = 0
        self.total_size_downloaded = 0
        
        # 状态文件
        self.state_file = self.output_dir / "continuous_search_state.json"
        self._load_state()
    
    def _default_config(self) -> Dict:
        """默认配置"""
        return {
            # ChatGPT 配置
            "chatgpt_headless": False,  # 首次运行建议 False，以便登录
            "keywords_per_round": 10,   # 每轮生成的关键词数
            "focus_areas": [            # 重点关注领域
                "DC-DC converter",
                "buck converter",
                "boost converter",
                "flyback",
                "automotive power",
                "high efficiency",
            ],
            
            # 搜索配置
            "results_per_keyword": 20,  # 每个关键词的搜索结果数
            "max_downloads_per_keyword": 10,  # 每个关键词最多下载数
            
            # 循环控制
            "max_rounds": 100,          # 最大轮数（0=无限）
            "min_files_per_round": 5,   # 每轮最少下载文件数（低于此值提前结束）
            "round_interval": 300,      # 轮次间隔（秒）
            
            # 下载控制
            "total_size_limit_gb": 50,  # 总下载大小限制（GB）
            "total_files_limit": 5000,  # 总文件数限制
            
            # 其他
            "save_state_interval": 5,   # 保存状态间隔（轮数）
        }
    
    def _load_state(self):
        """加载运行状态"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    self.current_round = state.get("current_round", 0)
                    self.total_files_downloaded = state.get("total_files_downloaded", 0)
                    self.total_size_downloaded = state.get("total_size_downloaded", 0)
                    self.logger.info(f"📥 加载运行状态: 第 {self.current_round} 轮")
            except Exception as e:
                self.logger.error(f"❌ 加载状态失败: {e}")
    
    def _save_state(self):
        """保存运行状态"""
        try:
            state = {
                "current_round": self.current_round,
                "total_files_downloaded": self.total_files_downloaded,
                "total_size_downloaded": self.total_size_downloaded,
                "last_updated": datetime.now().isoformat()
            }
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2)
            self.logger.debug(f"💾 保存运行状态")
        except Exception as e:
            self.logger.error(f"❌ 保存状态失败: {e}")
    
    def _initialize_components(self):
        """初始化各个组件"""
        self.logger.info("🔧 初始化组件...")
        
        # 初始化 Gemini 生成器
        self.chatgpt_generator = GeminiKeywordGenerator(
            logger=self.logger,
            headless=self.config["chatgpt_headless"]
        )
        self.chatgpt_generator.start()
        
        # 检查登录状态
        if not self.chatgpt_generator.check_login_status():
            self.logger.error("❌ Gemini 未登录，无法继续")
            return False
        
        self.logger.info("✅ 组件初始化完成")
        return True
    
    def _cleanup_components(self):
        """清理组件"""
        if self.chatgpt_generator:
            self.chatgpt_generator.stop()
            self.chatgpt_generator = None
        
        if self.google_fetcher:
            self.google_fetcher.close()
            self.google_fetcher = None
        
        if self.ddg_fetcher:
            if hasattr(self.ddg_fetcher, 'close'):
                self.ddg_fetcher.close()
            self.ddg_fetcher = None
    
    def _generate_keywords(self) -> List[str]:
        """生成新的关键词"""
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"🎯 第 {self.current_round + 1} 轮: 生成关键词")
        self.logger.info(f"{'='*60}\n")
        
        # 准备上下文
        context = self._prepare_context()
        
        # 生成关键词
        keywords = self.chatgpt_generator.generate_keywords(
            context=context,
            num_keywords=self.config["keywords_per_round"],
            focus_areas=self.config["focus_areas"]
        )
        
        if not keywords:
            self.logger.warning("⚠️  未能生成关键词")
            return []
        
        # 过滤关键词：优先新的，允许重用旧的有效关键词
        new_keywords = self.keyword_manager.filter_new_keywords(
            keywords, 
            allow_reuse_days=self.config.get("keyword_reuse_days", 7)
        )
        
        if not new_keywords:
            self.logger.warning("⚠️  无新关键词，将重用所有生成的关键词")
            new_keywords = keywords  # 全部使用
        
        self.logger.info(f"✅ 生成 {len(keywords)} 个关键词，{len(new_keywords)} 个可用")
        
        return new_keywords
    
    def _prepare_context(self) -> Dict:
        """准备 ChatGPT 的上下文信息"""
        stats = self.keyword_manager.get_statistics()
        recent_keywords = self.keyword_manager.get_recent_keywords(limit=10)
        
        # 分析已下载文件
        vendors_found = self._analyze_downloaded_vendors()
        recent_topics = self._extract_recent_topics()
        
        context = {
            "downloaded_count": self.total_files_downloaded,
            "vendors": list(vendors_found),
            "used_keywords": recent_keywords,
            "recent_topics": recent_topics,
            "current_round": self.current_round,
        }
        
        return context
    
    def _analyze_downloaded_vendors(self) -> Set[str]:
        """分析已下载的供应商"""
        vendors = set()
        for vendor_dir in self.output_dir.iterdir():
            if vendor_dir.is_dir() and not vendor_dir.name.startswith(('_', '.')):
                vendors.add(vendor_dir.name)
        return vendors
    
    def _extract_recent_topics(self) -> List[str]:
        """提取最近的主题（从关键词中）"""
        recent = self.keyword_manager.get_recent_keywords(limit=20)
        
        # 简单提取主要词汇
        topics = set()
        for kw in recent:
            words = kw.lower().split()
            for word in words:
                if len(word) > 4 and word not in ["datasheet", "guide", "note"]:
                    topics.add(word)
                    if len(topics) >= 10:
                        break
            if len(topics) >= 10:
                break
        
        return list(topics)
    
    def _search_and_download(self, keywords: List[str]) -> Dict:
        """搜索并下载"""
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"🔍 第 {self.current_round + 1} 轮: 搜索与下载")
        self.logger.info(f"{'='*60}\n")
        
        round_stats = {
            "files_downloaded": 0,
            "total_size": 0,
            "keyword_results": {}
        }
        
        for i, keyword in enumerate(keywords, 1):
            self.logger.info(f"\n--- 关键词 {i}/{len(keywords)}: {keyword} ---")
            
            # 搜索并下载
            try:
                result = self._process_single_keyword(keyword)
                
                # 更新统计
                files_found = result["files_downloaded"]
                size = result["total_size"]
                
                round_stats["files_downloaded"] += files_found
                round_stats["total_size"] += size
                round_stats["keyword_results"][keyword] = result
                
                # 更新关键词管理器
                self.keyword_manager.add_keyword(keyword, files_found, size)
                
                self.logger.info(f"✅ {keyword}: {files_found} 文件, {size / (1024*1024):.2f} MB")
                
            except Exception as e:
                self.logger.error(f"❌ 处理关键词失败: {e}")
                self.keyword_manager.add_keyword(keyword, 0, 0)
            
            # 检查是否达到限制
            if self._check_limits():
                self.logger.warning("⚠️  达到下载限制，停止本轮")
                break
        
        return round_stats
    
    def _process_single_keyword(self, keyword: str) -> Dict:
        """处理单个关键词的搜索下载"""
        result = {
            "files_downloaded": 0,
            "total_size": 0,
            "urls_found": 0
        }
        
        try:
            # 初始化搜索器（如果尚未初始化）
            if USE_GOOGLE:
                if not self.google_fetcher:
                    self.logger.info("🌐 初始化 Google 搜索器...")
                    self.google_fetcher = GoogleFetcher(
                        output_dir=self.output_dir,
                        results_limit=self.config.get("results_per_keyword", 20),
                        download_limit=self.config.get("max_downloads_per_keyword", 10),
                        domain_whitelist=self.config.get("domain_whitelist"),
                        logger=self.logger,
                        headless=self.config.get("headless", True)
                    )
                
                # 使用 Google 搜索
                self.logger.info(f"🔍 使用 Google 搜索: {keyword}")
                fetch_result = self.google_fetcher.fetch_and_download(keyword)
                
                result["files_downloaded"] = fetch_result.get("files_downloaded", 0)
                result["urls_found"] = fetch_result.get("results_found", 0)
                
                # 获取实际下载大小
                stats = self.google_fetcher.get_stats()
                result["total_size"] = stats.get("total_size", 0)
                
            else:
                # 使用 DuckDuckGo 搜索（备用）
                self.logger.info(f"🔍 使用 DuckDuckGo 搜索: {keyword}")
                
                if not self.ddg_fetcher:
                    # DuckDuckGo 使用简单的 API 方式（非浏览器）
                    # 直接调用 ddgs 进行搜索
                    from ddgs import DDGS
                    self.ddgs = DDGS()
                
                # 使用 DDGS 搜索
                try:
                    results = list(self.ddgs.text(keyword, max_results=self.config.get("results_per_keyword", 20)))
                    result["urls_found"] = len(results)
                    
                    # 过滤 PDF 链接
                    pdf_urls = [r['href'] for r in results if r['href'].lower().endswith('.pdf')]
                    
                    # 下载 PDF
                    downloads = 0
                    total_size = 0
                    max_downloads = self.config.get("max_downloads_per_keyword", 10)
                    
                    for url in pdf_urls[:max_downloads]:
                        try:
                            # 简单下载
                            import requests
                            response = requests.get(url, timeout=30, stream=True)
                            if response.status_code == 200:
                                filename = Path(url).name or "download.pdf"
                                filepath = self.output_dir / filename
                                
                                with open(filepath, 'wb') as f:
                                    for chunk in response.iter_content(chunk_size=8192):
                                        f.write(chunk)
                                
                                file_size = filepath.stat().st_size
                                total_size += file_size
                                downloads += 1
                                self.logger.info(f"✅ 已下载: {filename} ({file_size/1024/1024:.2f} MB)")
                        except Exception as e:
                            self.logger.debug(f"下载失败 {url}: {e}")
                            continue
                    
                    result["files_downloaded"] = downloads
                    result["total_size"] = total_size
                    
                except Exception as e:
                    self.logger.error(f"DuckDuckGo 搜索失败: {e}")
                    result["files_downloaded"] = 0
            
        except Exception as e:
            self.logger.error(f"❌ 处理关键词失败: {e}", exc_info=True)
        
        return result
    
    def _check_limits(self) -> bool:
        """检查是否达到限制"""
        size_limit_bytes = self.config["total_size_limit_gb"] * 1024 * 1024 * 1024
        
        if self.total_size_downloaded >= size_limit_bytes:
            self.logger.warning(f"⚠️  达到总大小限制: {self.config['total_size_limit_gb']} GB")
            return True
        
        if self.total_files_downloaded >= self.config["total_files_limit"]:
            self.logger.warning(f"⚠️  达到总文件数限制: {self.config['total_files_limit']}")
            return True
        
        return False
    
    def _print_round_summary(self, round_stats: Dict):
        """打印本轮总结"""
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"📊 第 {self.current_round + 1} 轮总结")
        self.logger.info(f"{'='*60}")
        self.logger.info(f"本轮下载文件: {round_stats['files_downloaded']}")
        self.logger.info(f"本轮下载大小: {round_stats['total_size'] / (1024*1024):.2f} MB")
        self.logger.info(f"累计下载文件: {self.total_files_downloaded}")
        self.logger.info(f"累计下载大小: {self.total_size_downloaded / (1024*1024*1024):.2f} GB")
        self.logger.info(f"{'='*60}\n")
    
    def run(self):
        """运行持续搜索"""
        self.logger.info("\n" + "🚀 启动持续搜索下载系统".center(60, "="))
        self.logger.info(f"输出目录: {self.output_dir}")
        self.logger.info(f"关键词数据库: {self.keyword_manager.db_path}")
        self.logger.info("")
        
        # 初始化组件
        if not self._initialize_components():
            return
        
        try:
            self.is_running = True
            
            while self.is_running:
                # 检查轮数限制
                if self.config["max_rounds"] > 0 and self.current_round >= self.config["max_rounds"]:
                    self.logger.info(f"✅ 达到最大轮数: {self.config['max_rounds']}")
                    break
                
                # 检查其他限制
                if self._check_limits():
                    self.logger.info("✅ 达到下载限制")
                    break
                
                # 生成关键词
                keywords = self._generate_keywords()
                if not keywords:
                    self.logger.warning("⚠️  没有新关键词，等待下一轮...")
                    time.sleep(60)
                    continue
                
                # 搜索并下载
                round_stats = self._search_and_download(keywords)
                
                # 更新统计
                self.total_files_downloaded += round_stats["files_downloaded"]
                self.total_size_downloaded += round_stats["total_size"]
                
                # 打印总结
                self._print_round_summary(round_stats)
                
                # 检查最少文件数
                if round_stats["files_downloaded"] < self.config["min_files_per_round"]:
                    self.logger.warning(
                        f"⚠️  本轮下载文件数过少 ({round_stats['files_downloaded']} < "
                        f"{self.config['min_files_per_round']})，可能需要调整策略"
                    )
                
                # 更新轮数
                self.current_round += 1
                
                # 定期保存状态
                if self.current_round % self.config["save_state_interval"] == 0:
                    self._save_state()
                
                # 打印关键词统计
                if self.current_round % 5 == 0:
                    self.keyword_manager.print_statistics()
                
                # 等待下一轮
                if self.is_running:
                    interval = self.config["round_interval"]
                    self.logger.info(f"⏸️  等待 {interval} 秒后开始下一轮...\n")
                    time.sleep(interval)
            
            # 最终统计
            self.logger.info("\n" + "🎉 搜索完成".center(60, "="))
            self.logger.info(f"总轮数: {self.current_round}")
            self.logger.info(f"总文件数: {self.total_files_downloaded}")
            self.logger.info(f"总大小: {self.total_size_downloaded / (1024*1024*1024):.2f} GB")
            self.keyword_manager.print_statistics()
            
        except KeyboardInterrupt:
            self.logger.info("\n\n⚠️  用户中断，正在保存状态...")
            self._save_state()
            
        except Exception as e:
            self.logger.error(f"❌ 运行出错: {e}", exc_info=True)
            
        finally:
            self.is_running = False
            self._save_state()
            self._cleanup_components()
            self.logger.info("✅ 已清理资源")


def setup_logging(debug: bool = False) -> logging.Logger:
    """配置日志"""
    level = logging.DEBUG if debug else logging.INFO
    
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )
    
    return logging.getLogger("continuous_searcher")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="DC-DC 资料持续搜索下载系统",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("downloads_continuous"),
        help="输出目录（默认: downloads_continuous）"
    )
    
    parser.add_argument(
        "-k", "--keywords-db",
        type=Path,
        default=Path("keywords.json"),
        help="关键词数据库文件（默认: keywords.json）"
    )
    
    parser.add_argument(
        "-c", "--config",
        type=Path,
        help="配置文件（JSON格式）"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="启用调试模式"
    )
    
    parser.add_argument(
        "--rounds",
        type=int,
        default=0,
        help="最大轮数（0=无限，默认: 0）"
    )
    
    parser.add_argument(
        "--keywords-per-round",
        type=int,
        default=10,
        help="每轮生成关键词数（默认: 10）"
    )
    
    args = parser.parse_args()
    
    # 设置日志
    logger = setup_logging(args.debug)
    
    # 加载配置
    config = None
    if args.config and args.config.exists():
        try:
            with open(args.config, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info(f"📄 加载配置文件: {args.config}")
        except Exception as e:
            logger.error(f"❌ 加载配置文件失败: {e}")
            sys.exit(1)
    
    # 应用命令行参数
    if config is None:
        config = {}
    
    if args.rounds > 0:
        config["max_rounds"] = args.rounds
    
    if args.keywords_per_round > 0:
        config["keywords_per_round"] = args.keywords_per_round
    
    # 创建并运行搜索器
    searcher = ContinuousSearcher(
        output_dir=args.output,
        keyword_db_path=args.keywords_db,
        config=config,
        logger=logger
    )
    
    searcher.run()


if __name__ == "__main__":
    main()
