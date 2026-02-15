#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
持续搜索下载系统 - 完整集成版
整合 ChatGPT 关键词生成 + DuckDuckGo 搜索 + 实际下载功能

作者: AI 助手
版本: 1.1.0
日期: 2026-01-26
Python: 3.10+
"""

import argparse
import atexit
import json
import logging
import signal
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from chatgpt_keyword_generator import GeminiKeywordGenerator
from keyword_manager import KeywordManager


class IntegratedSearcher:
    """集成下载功能的持续搜索器"""
    
    def __init__(
        self,
        output_dir: Path,
        keyword_db_path: Path,
        use_browser: bool = True,
        config: Optional[Dict] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        初始化搜索器
        
        Args:
            output_dir: 输出目录
            keyword_db_path: 关键词数据库路径
            use_browser: 是否使用浏览器版本（强制为 True，必须使用 Chrome 以避免被拒绝）
            config: 配置字典
            logger: 日志记录器
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger = logger or logging.getLogger(__name__)
        
        # 处理配置：如果是嵌套配置则扁平化，否则使用默认
        if config:
            # 检查是否是嵌套配置
            if any(k in config for k in ["gemini", "chatgpt", "keywords", "search", "loop_control", "limits"]):
                base_config = self._default_config()
                flattened = self._flatten_config(config)
                base_config.update(flattened)
                self.config = base_config
            else:
                # 已经是扁平配置
                base_config = self._default_config()
                base_config.update(config)
                self.config = base_config
        else:
            self.config = self._default_config()
        
        # 强制使用浏览器版本（必须使用 Chrome 以避免请求被拒绝）
        self.use_browser = True
        
        # 初始化组件
        self.keyword_manager = KeywordManager(keyword_db_path, self.logger)
        self.chatgpt_generator = None
        
        # 运行状态
        self.is_running = False
        self.current_round = 0
        self.total_files_downloaded = 0
        self.total_size_downloaded = 0
        
        # 状态文件
        self.state_file = self.output_dir / "search_state.json"
        self._load_state()
        
        # 注册优雅退出处理
        self._setup_signal_handlers()
    
    def _default_config(self) -> Dict:
        """默认配置"""
        return {
            "gemini_headless": False,
            "gemini_response_timeout": 60,
            "keywords_per_round": 10,
            "focus_areas": [
                "DC-DC converter",
                "buck converter",
                "boost converter",
                "automotive power",
            ],
            "results_per_keyword": 20,
            "max_downloads_per_keyword": 10,
            "max_rounds": 0,
            "min_files_per_round": 3,
            "round_interval": 300,
            "total_size_limit_gb": 50,
            "total_files_limit": 5000,
            "save_state_interval": 5,
        }
    
    def _flatten_config(self, config: Dict) -> Dict:
        """将嵌套配置扁平化"""
        flattened = {}
        
        # 处理 gemini 配置
        if "gemini" in config:
            gemini_cfg = config["gemini"]
            flattened["gemini_headless"] = gemini_cfg.get("headless", False)
            flattened["gemini_response_timeout"] = gemini_cfg.get("response_timeout", 60)
        # 兼容旧的 chatgpt 配置
        elif "chatgpt" in config:
            chatgpt_cfg = config["chatgpt"]
            flattened["gemini_headless"] = chatgpt_cfg.get("headless", False)
        
        # 处理 keywords 配置
        if "keywords" in config:
            keywords_cfg = config["keywords"]
            flattened["keywords_per_round"] = keywords_cfg.get("per_round", 10)
            flattened["focus_areas"] = keywords_cfg.get("focus_areas", [])
        
        # 处理 search 配置
        if "search" in config:
            search_cfg = config["search"]
            flattened["results_per_keyword"] = search_cfg.get("results_per_keyword", 20)
            flattened["max_downloads_per_keyword"] = search_cfg.get("max_downloads_per_keyword", 10)
        
        # 处理 loop_control 配置
        if "loop_control" in config:
            loop_cfg = config["loop_control"]
            flattened["max_rounds"] = loop_cfg.get("max_rounds", 0)
            flattened["min_files_per_round"] = loop_cfg.get("min_files_per_round", 3)
            flattened["round_interval"] = loop_cfg.get("round_interval_seconds", 300)
        
        # 处理 limits 配置
        if "limits" in config:
            limits_cfg = config["limits"]
            flattened["total_size_limit_gb"] = limits_cfg.get("total_size_gb", 50)
            flattened["total_files_limit"] = limits_cfg.get("total_files", 5000)
        
        # 处理 other 配置
        if "other" in config:
            other_cfg = config["other"]
            flattened["save_state_interval"] = other_cfg.get("save_state_interval", 5)
        
        return flattened
    
    def _load_state(self):
        """加载运行状态"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    self.current_round = state.get("current_round", 0)
                    self.logger.info(f"📥 加载状态: 第 {self.current_round} 轮")
            except Exception as e:
                self.logger.error(f"❌ 加载状态失败: {e}")
        
        # 始终基于实际文件系统重新统计（避免累计误差）
        actual_stats = self._count_downloaded_files()
        self.total_files_downloaded = actual_stats["files_downloaded"]
        self.total_size_downloaded = actual_stats["total_size"]
        if self.total_files_downloaded > 0:
            self.logger.info(f"📊 当前实际文件: {self.total_files_downloaded} 个, {self.total_size_downloaded / (1024**3):.2f} GB")
    
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
        except Exception as e:
            self.logger.error(f"❌ 保存状态失败: {e}")
    
    def _setup_signal_handlers(self):
        """设置信号处理器（优雅退出）"""
        def signal_handler(signum, frame):
            self.logger.warning(f"\n⚠️ 收到中断信号 ({signum})，正在优雅退出...")
            self.is_running = False
            self._cleanup()
            sys.exit(0)
        
        # 注册信号处理
        signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
        signal.signal(signal.SIGTERM, signal_handler)  # 终止信号
        
        # 注册退出处理
        atexit.register(self._cleanup)
    
    def _cleanup(self):
        """清理资源"""
        try:
            if hasattr(self, 'chatgpt_generator') and self.chatgpt_generator:
                self.logger.info("🧹 关闭浏览器...")
                self._cleanup_components()
            
            if hasattr(self, 'state_file'):
                self._save_state()
                self.logger.info("💾 状态已保存")
        except Exception as e:
            self.logger.error(f"清理资源时出错: {e}")
            self.logger.error(f"清理资源时出错: {e}")
    
    def _initialize_components(self):
        """初始化组件"""
        self.logger.info("🔧 初始化 Gemini 关键词生成器...")
        
        try:
            self.chatgpt_generator = GeminiKeywordGenerator(
                logger=self.logger,
                headless=self.config["gemini_headless"],
                response_timeout=self.config.get("gemini_response_timeout", 60)
            )
            self.chatgpt_generator.start()
            
            if not self.chatgpt_generator.check_login_status():
                self.logger.error("❌ ChatGPT 未登录")
                return False
            
            self.logger.info("✅ 组件初始化完成")
            return True
        except KeyboardInterrupt:
            self.logger.warning("⚠️ 初始化被用户中断")
            raise
        except Exception as e:
            self.logger.error(f"❌ 初始化失败: {e}")
            return False
    
    def _cleanup_components(self):
        """清理组件"""
        if self.chatgpt_generator:
            self.chatgpt_generator.stop()
    
    def _generate_keywords(self) -> List[str]:
        """生成新关键词"""
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"🎯 第 {self.current_round + 1} 轮: 生成关键词")
        self.logger.info(f"{'='*60}\n")
        
        context = self._prepare_context()
        keywords = self.chatgpt_generator.generate_keywords(
            context=context,
            num_keywords=self.config["keywords_per_round"],
            focus_areas=self.config["focus_areas"]
        )
        
        if not keywords:
            return []
        
        new_keywords = self.keyword_manager.filter_new_keywords(keywords)
        self.logger.info(f"✅ 生成 {len(keywords)} 个关键词，{len(new_keywords)} 个新的")
        
        return new_keywords
    
    def _prepare_context(self) -> Dict:
        """准备上下文"""
        recent_keywords = self.keyword_manager.get_recent_keywords(limit=10)
        vendors_found = self._analyze_downloaded_vendors()
        
        return {
            "downloaded_count": self.total_files_downloaded,
            "vendors": list(vendors_found),
            "used_keywords": recent_keywords,
            "current_round": self.current_round,
        }
    
    def _analyze_downloaded_vendors(self) -> Set[str]:
        """分析已下载供应商"""
        vendors = set()
        for vendor_dir in self.output_dir.iterdir():
            if vendor_dir.is_dir() and not vendor_dir.name.startswith(('_', '.')):
                vendors.add(vendor_dir.name)
        return vendors
    
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
            
            try:
                result = self._download_with_ddg_fetcher(keyword)
                
                files_found = result["files_downloaded"]
                size = result["total_size"]
                
                round_stats["files_downloaded"] += files_found
                round_stats["total_size"] += size
                round_stats["keyword_results"][keyword] = result
                
                self.keyword_manager.add_keyword(keyword, files_found, size)
                self.logger.info(f"✅ {keyword}: {files_found} 文件, {size / (1024*1024):.2f} MB")
                
            except Exception as e:
                self.logger.error(f"❌ 处理失败: {e}")
                self.keyword_manager.add_keyword(keyword, 0, 0)
            
            if self._check_limits():
                break
        
        return round_stats
    
    def _download_with_ddg_fetcher(self, keyword: str) -> Dict:
        """使用 ddg_fetcher 下载（强制使用 Chrome 浏览器版本）"""
        # 强制使用浏览器版本（Chrome）以避免请求被拒绝
        script = "ddg_fetcher_browser.py"
        
        cmd = [
            sys.executable,
            script,
            "--query", keyword,
            "--out", str(self.output_dir),
            "--max-results", str(self.config["results_per_keyword"]),
        ]
        
        # 如果配置了无头模式
        if self.config.get("gemini_headless", False):
            cmd.append("--headless")
        
        self.logger.info(f"🌐 启动 Chrome 浏览器搜索: {keyword}")
        self.logger.debug(f"执行命令: {' '.join(cmd)}")
        
        # 执行命令（不捕获输出，直接显示在控制台）
        try:
            result = subprocess.run(
                cmd,
                timeout=600,  # 10分钟超时
                text=True
            )
            
            # 检查返回码
            if result.returncode != 0:
                self.logger.error(f"❌ Chrome 浏览器脚本执行失败，返回码: {result.returncode}")
                return {"files_downloaded": 0, "total_size": 0}
            
            # 统计下载文件
            return self._count_downloaded_files()
            
        except subprocess.TimeoutExpired:
            self.logger.error(f"⏰ Chrome 浏览器执行超时（600秒）")
            return {"files_downloaded": 0, "total_size": 0}
        except FileNotFoundError:
            self.logger.error(f"❌ 找不到脚本: {script}")
            self.logger.error(f"   当前目录: {Path.cwd()}")
            self.logger.error(f"   请确认 {script} 文件存在")
            return {"files_downloaded": 0, "total_size": 0}
        except Exception as e:
            self.logger.error(f"❌ Chrome 浏览器执行失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return {"files_downloaded": 0, "total_size": 0}
    
    def _parse_ddg_output(self, stdout: str, stderr: str) -> Dict:
        """解析 ddg_fetcher 的输出"""
        result = {
            "files_downloaded": 0,
            "total_size": 0,
            "urls_found": 0
        }
        
        # 查找摘要行
        for line in stdout.split('\n'):
            if "成功下载" in line or "下载成功" in line:
                import re
                match = re.search(r'(\d+)', line)
                if match:
                    result["files_downloaded"] = int(match.group(1))
            elif "MB" in line or "GB" in line:
                # 尝试提取大小
                import re
                match = re.search(r'([\d.]+)\s*(MB|GB)', line)
                if match:
                    size = float(match.group(1))
                    unit = match.group(2)
                    result["total_size"] = int(size * (1024*1024 if unit == "MB" else 1024*1024*1024))
        
        # 如果没有解析到，尝试统计文件
        if result["files_downloaded"] == 0:
            result["files_downloaded"] = self._count_new_files()
        
        return result
    
    def _count_downloaded_files(self) -> Dict:
        """统计下载的文件数和大小"""
        count = 0
        total_size = 0
        
        for vendor_dir in self.output_dir.iterdir():
            if vendor_dir.is_dir() and not vendor_dir.name.startswith(('_', '.')):
                for file in vendor_dir.rglob("*"):
                    if file.is_file() and file.suffix.lower() == '.pdf':
                        count += 1
                        total_size += file.stat().st_size
        
        return {
            "files_downloaded": count,
            "total_size": total_size
        }
    
    def _count_new_files(self) -> int:
        """统计新增文件数（基于实际文件系统）"""
        # 返回当前实际 PDF 文件数
        count = 0
        for vendor_dir in self.output_dir.iterdir():
            if vendor_dir.is_dir() and not vendor_dir.name.startswith(('_', '.')):
                for file in vendor_dir.rglob("*.pdf"):
                    if file.is_file():
                        count += 1
        return count
    
    def _check_limits(self) -> bool:
        """检查限制（基于实际文件系统统计）"""
        # 重新统计实际文件数和大小
        actual_stats = self._count_downloaded_files()
        self.total_files_downloaded = actual_stats["files_downloaded"]
        self.total_size_downloaded = actual_stats["total_size"]
        
        size_limit = self.config["total_size_limit_gb"] * 1024 * 1024 * 1024
        
        if self.total_size_downloaded >= size_limit:
            self.logger.warning(f"⚠️  达到大小限制 ({self.total_size_downloaded / (1024**3):.2f} GB / {self.config['total_size_limit_gb']} GB)")
            return True
        
        if self.total_files_downloaded >= self.config["total_files_limit"]:
            self.logger.warning(f"⚠️  达到文件数限制 ({self.total_files_downloaded} / {self.config['total_files_limit']})")
            return True
        
        return False
    
    def _print_round_summary(self, round_stats: Dict):
        """打印总结"""
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"📊 第 {self.current_round + 1} 轮总结")
        self.logger.info(f"{'='*60}")
        self.logger.info(f"本轮文件: {round_stats['files_downloaded']}")
        self.logger.info(f"本轮大小: {round_stats['total_size'] / (1024*1024):.2f} MB")
        self.logger.info(f"累计文件: {self.total_files_downloaded}")
        self.logger.info(f"累计大小: {self.total_size_downloaded / (1024*1024*1024):.2f} GB")
        self.logger.info(f"{'='*60}\n")
    
    def run(self):
        """运行"""
        self.logger.info("\n" + "🚀 启动持续搜索系统".center(60, "="))
        self.logger.info(f"输出: {self.output_dir}")
        self.logger.info(f"使用: Chrome 浏览器版（必需，以避免请求被拒绝）")
        self.logger.info("💡 按 Ctrl+C 可随时安全退出\n")
        
        try:
            if not self._initialize_components():
                return
        except KeyboardInterrupt:
            self.logger.warning("\n⚠️ 初始化被中断")
            return
        
        try:
            self.is_running = True
            
            while self.is_running:
                # 检查限制
                if self.config["max_rounds"] > 0 and self.current_round >= self.config["max_rounds"]:
                    self.logger.info(f"✅ 达到最大轮数")
                    break
                
                if self._check_limits():
                    break
                
                # 生成关键词
                try:
                    keywords = self._generate_keywords()
                    if not keywords:
                        self.logger.warning("⚠️  无新关键词")
                        time.sleep(60)
                        continue
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    self.logger.error(f"❌ 生成关键词失败: {e}")
                    time.sleep(30)
                    continue
                
                # 搜索下载
                try:
                    round_stats = self._search_and_download(keywords)
                    
                    # 重新统计实际文件数（避免重复计数）
                    actual_stats = self._count_downloaded_files()
                    self.total_files_downloaded = actual_stats["files_downloaded"]
                    self.total_size_downloaded = actual_stats["total_size"]
                    
                    # 打印总结
                    self._print_round_summary(round_stats)
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    self.logger.error(f"❌ 搜索下载出错: {e}")
                
                # 更新轮数
                self.current_round += 1
                
                # 保存状态
                if self.current_round % self.config["save_state_interval"] == 0:
                    self._save_state()
                
                # 显示统计
                if self.current_round % 5 == 0:
                    self.keyword_manager.print_statistics()
                
                # 等待（分段睡眠以便响应中断）
                if self.is_running:
                    interval = self.config["round_interval"]
                    self.logger.info(f"⏸️  等待 {interval} 秒...\n")
                    
                    # 分段睡眠，每秒检查一次中断
                    for _ in range(interval):
                        if not self.is_running:
                            break
                        time.sleep(1)
            
            # 最终统计
            self.logger.info("\n" + "🎉 完成".center(60, "="))
            self.keyword_manager.print_statistics()
        
        except KeyboardInterrupt:
            self.logger.warning("\n⚠️ 收到中断信号，正在安全退出...")
        except Exception as e:
            self.logger.error(f"❌ 错误: {e}", exc_info=True)
        finally:
            self.is_running = False
            self._save_state()
            self._cleanup()
            self.logger.info("✅ 程序已安全退出")


def setup_logging(debug: bool = False) -> logging.Logger:
    """配置日志"""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger("integrated_searcher")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="持续搜索下载系统")
    parser.add_argument("-o", "--output", type=Path, default=Path("downloads_continuous"))
    parser.add_argument("-k", "--keywords-db", type=Path, default=Path("keywords.json"))
    parser.add_argument("-c", "--config", type=Path)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--rounds", type=int, default=0)
    # 注意：搜索和下载必须通过 Chrome 浏览器，否则会被拒绝
    
    args = parser.parse_args()
    logger = setup_logging(args.debug)
    
    # 加载配置
    config = None
    if args.config and args.config.exists():
        with open(args.config, 'r', encoding='utf-8-sig') as f:  # utf-8-sig 自动处理 BOM
            config = json.load(f)
    
    if config is None:
        config = {}
    
    if args.rounds > 0:
        config["max_rounds"] = args.rounds
    
    # 运行（强制使用 Chrome 浏览器）
    searcher = IntegratedSearcher(
        output_dir=args.output,
        keyword_db_path=args.keywords_db,
        use_browser=True,  # 强制使用 Chrome 浏览器
        config=config,
        logger=logger
    )
    
    searcher.run()


if __name__ == "__main__":
    main()
