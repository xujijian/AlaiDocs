#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整自动化系统：检索 → 下载 → 分类 → 知识库
自动生成关键词、搜索、下载PDF、分类归档、更新知识库

作者: AI 助手
版本: 2.0.0
日期: 2026-01-27
"""

import argparse
import json
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

from continuous_searcher import ContinuousSearcher
from pdf_classifier import PDFClassifier, ProcessedFilesDB


class IntegratedDownloaderClassifier:
    """完整自动化系统：下载 + 分类 + 知识库"""
    
    def __init__(
        self,
        download_dir: Path,
        classified_dir: Path,
        keyword_db_path: Path,
        kb_system_path: Optional[Path] = None,
        config: Optional[Dict] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        初始化完整自动化系统
        
        Args:
            download_dir: 下载目录
            classified_dir: 分类后的目标目录
            keyword_db_path: 关键词数据库路径
            kb_system_path: 知识库系统路径（axis-SQLite目录）
            config: 配置字典
            logger: 日志记录器
        """
        self.download_dir = Path(download_dir)
        self.classified_dir = Path(classified_dir)
        self.kb_system_path = Path(kb_system_path) if kb_system_path else None
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.classified_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger = logger or logging.getLogger(__name__)
        self.config = config or self._default_config()
        
        # 初始化下载器
        self.logger.info("📦 初始化下载系统...")
        self.downloader = ContinuousSearcher(
            output_dir=self.download_dir,
            keyword_db_path=keyword_db_path,
            config=self.config.get("downloader", {}),
            logger=self.logger
        )
        
        # 初始化分类器
        self.logger.info("🗂️  初始化分类系统...")
        
        # 如果下载和分类目录相同，使用 copy 模式避免移动文件
        mode = "copy" if self.download_dir == self.classified_dir else "move"
        
        # 创建 ProcessedFilesDB 实例
        from pdf_classifier import ProcessedFilesDB
        db_path = Path("classified_files.db")
        self.classifier_db = ProcessedFilesDB(db_path)
        
        # 创建 metadata 文件路径
        metadata_file = self.classified_dir / "metadata.jsonl"
        
        self.classifier = PDFClassifier(
            source_dir=self.download_dir,
            target_dir=self.classified_dir,
            db=self.classifier_db,
            metadata_file=metadata_file,
            head_pages=self.config.get("classifier", {}).get("head_pages", 3),
            mode=mode,
            dry_run=False
        )
        
        self.is_running = False
    
    def _default_config(self) -> Dict:
        """默认配置"""
        return {
            "downloader": {
                "chatgpt_headless": False,
                "keywords_per_round": 10,
                "results_per_keyword": 20,
                "max_downloads_per_keyword": 10,
                "max_rounds": 0,  # 无限
                "min_files_per_round": 5,
                "round_interval": 300,
                "total_size_limit_gb": 50,
                "total_files_limit": 5000,
            },
            "classifier": {
                "head_pages": 3,
                "min_stable_seconds": 10,
                "scan_interval": 30,  # 每30秒扫描一次下载目录
            },
                "update_kb_after_classify": True,  # 分类后更新知识库
                "kb_update_interval": 1,  # 每N轮更新一次知识库
            "integration": {
                "classify_after_download": True,  # 每轮下载后立即分类
                "classify_interval": 60,  # 或者定期扫描分类（秒）
            }
        }
    
    def run_download_round(self) -> Dict:
        """
        运行一轮下载
        
        Returns:
            Dict: 下载统计信息
        """
        self.logger.info("\n" + "="*60)
        self.logger.info("🔽 开始下载轮次")
        self.logger.info("="*60)
        
        # 生成关键词
        keywords = self.downloader._generate_keywords()
        
        if not keywords:
            self.logger.warning("⚠️  没有新关键词")
            return {"files_downloaded": 0, "keywords": []}
        
        # 搜索并下载
        round_stats = self.downloader._search_and_download(keywords)
        
        self.downloader.total_files_downloaded += round_stats["files_downloaded"]
        self.downloader.total_size_downloaded += round_stats["total_size"]
        self.downloader.current_round += 1
        
        self.logger.info(f"✅ 下载完成: {round_stats['files_downloaded']} 个文件")
        
        return round_stats
    
    def run_classification_round(self) -> Dict:
        """
        运行一轮分类
        
        Returns:
            Dict: 分类统计信息
        """
        self.logger.info("\n" + "="*60)
        self.logger.info("🗂️  开始分类轮次")
        self.logger.info("="*60)
        
        stats = {
            "total_processed": 0,
            "successful": 0,
            "failed": 0,
            "skipped": 0
        }
        
        # 扫描下载目录中的所有 PDF 文件
        pdf_files = []
        for vendor_dir in self.download_dir.iterdir():
            if vendor_dir.is_dir() and not vendor_dir.name.startswith(('_', '.')):
                pdf_files.extend(vendor_dir.glob("*.pdf"))
        
        if not pdf_files:
            self.logger.info("📭 没有需要分类的文件")
            return stats
        
        self.logger.info(f"📋 发现 {len(pdf_files)} 个待分类文件")
        
        # 逐个分类
        for pdf_file in pdf_files:
            try:
                result = self.classifier.classify_file(pdf_file)
                
                if result:
                    stats["successful"] += 1
                    self.logger.info(f"✅ 已分类: {pdf_file.name}")
                else:
                    stats["skipped"] += 1
                    
                stats["total_processed"] += 1
                
            except Exception as e:
                stats["failed"] += 1
                self.logger.error(f"❌ 分类失败 {pdf_file.name}: {e}")
        
        self.logger.info(f"✅ 分类完成: {stats['successful']}/{stats['total_processed']}")
        
        return stats
    
    def run_integrated_mode(self):
        """
        运行整合模式：下载 → 分类 → 循环
        """
        self.logger.info("\n" + "🚀 启动整合下载分类系统".center(60, "="))
        self.logger.info(f"下载目录: {self.download_dir}")
        self.logger.info(f"分类目录: {self.classified_dir}")
        self.logger.info("")
        
        # 初始化下载器组件
        if not self.downloader._initialize_components():
            self.logger.error("❌ 下载器初始化失败")
            return
        
        try:
            self.is_running = True
            
            while self.is_running:
                # ===== 下载阶段 =====
                download_stats = self.run_download_round()
                
                # ===== 分类阶段 =====
                if download_stats["files_downloaded"] > 0:
                    self.logger.info(f"✅ 本轮下载了 {download_stats['files_downloaded']} 个文件，开始分类...")
                    
                    # 等待文件稳定
                    self.logger.info(f"⏳ 等待 {self.config['classifier']['min_stable_seconds']} 秒确保文件下载完成...")
                    time.sleep(self.config["classifier"]["min_stable_seconds"])
                    
                    # 分类新下载的文件
                    classify_stats = self.run_classification_round()
                    
                    # 打印统计
                    self._print_integrated_stats(download_stats, classify_stats)
                    
                    # ===== 知识库更新阶段 =====
                    if self.config["integration"].get("update_kb_after_classify", False):
                        self.logger.info(f"🔍 检查知识库更新条件...")
                        kb_interval = self.config["integration"].get("kb_update_interval", 1)
                        self.logger.info(f"   当前轮次: {self.downloader.current_round}, 更新间隔: {kb_interval}")
                        
                        if self.downloader.current_round % kb_interval == 0:
                            self.logger.info(f"✅ 满足更新条件，开始更新知识库...")
                            self.update_knowledge_base()
                        else:
                            self.logger.info(f"⏭️  跳过本轮知识库更新（每 {kb_interval} 轮更新一次）")
                    else:
                        self.logger.info(f"⚠️  知识库自动更新未启用")
                else:
                    self.logger.warning(f"⚠️  本轮未下载新文件，跳过分类和知识库更新")
                
                # ===== 检查限制 =====
                if self.downloader._check_limits():
                    self.logger.info("✅ 达到下载限制")
                    break
                
                # ===== 等待下一轮 =====
                interval = self.config["downloader"]["round_interval"]
                self.logger.info(f"⏸️  等待 {interval} 秒后开始下一轮...\n")
                time.sleep(interval)
            
            # 最终统计
            self.logger.info("\n" + "🎉 完成".center(60, "="))
            self.logger.info(f"总下载文件: {self.downloader.total_files_downloaded}")
            self.logger.info(f"总下载大小: {self.downloader.total_size_downloaded / (1024**3):.2f} GB")
            
        except KeyboardInterrupt:
            self.logger.info("\n\n⚠️  用户中断")
        except Exception as e:
            self.logger.error(f"❌ 运行出错: {e}", exc_info=True)
        finally:
            self.is_running = False
            self.downloader._cleanup_components()
            self.logger.info("✅ 已清理资源")
    
    def run_classify_only_mode(self):
        """
        仅运行分类模式：对已下载的文件进行分类
        """
        self.logger.info("\n" + "🗂️  分类模式".center(60, "="))
        self.logger.info(f"源目录: {self.download_dir}")
        self.logger.info(f"目标目录: {self.classified_dir}")
        self.logger.info("")
        
        stats = self.run_classification_round()
        
        self.logger.info("\n" + "📊 分类统计".center(60, "="))
        self.logger.info(f"总处理: {stats['total_processed']}")
        self.logger.info(f"成功: {stats['successful']}")
        self.logger.info(f"失败: {stats['failed']}")
        self.logger.info(f"跳过: {stats['skipped']}")
    
    def run_download_only_mode(self):
        """
        仅运行下载模式：持续下载，不分类
        """
        self.logger.info("\n" + "🔽 下载模式".center(60, "="))
        self.logger.info(f"下载目录: {self.download_dir}")
        self.logger.info("")
        
        # 初始化下载器组件
        if not self.downloader._initialize_components():
            self.logger.error("❌ 下载器初始化失败")
            return
        
        try:
            self.is_running = True
            
            while self.is_running:
                # 仅下载
                download_stats = self.run_download_round()
                
                self.logger.info(f"✅ 本轮下载: {download_stats['files_downloaded']} 个文件")
                
                # 检查限制
                if self.downloader._check_limits():
                    self.logger.info("✅ 达到下载限制")
                    break
                
                # 等待下一轮
                interval = self.config["downloader"]["round_interval"]
                self.logger.info(f"⏸️  等待 {interval} 秒后开始下一轮...\n")
                time.sleep(interval)
            
            self.logger.info("\n" + "🎉 完成".center(60, "="))
            
        except KeyboardInterrupt:
            self.logger.info("\n\n⚠️  用户中断")
        except Exception as e:
            self.logger.error(f"❌ 运行出错: {e}", exc_info=True)
        finally:
            self.is_running = False
            self.downloader._cleanup_components()
            self.logger.info("✅ 已清理资源")
    
    def update_knowledge_base(self):
        """
        更新知识库（调用 axis-SQLite 的 ingest.py）
        """
        if not self.kb_system_path or not self.kb_system_path.exists():
            self.logger.warning("⚠️  知识库系统路径未配置或不存在，跳过知识库更新")
            return
        
        self.logger.info("\n" + "="*60)
        self.logger.info("📚 更新知识库")
        self.logger.info("="*60)
        
        ingest_script = self.kb_system_path / "ingest.py"
        if not ingest_script.exists():
            self.logger.error(f"❌ 找不到 ingest.py: {ingest_script}")
            return
        
        # 构建命令
        # 注意：使用 axis-SQLite 自己的 Python 环境
        kb_python = self.kb_system_path / ".venv" / "Scripts" / "python.exe"
        if not kb_python.exists():
            # 如果没有虚拟环境，尝试使用系统 Python
            self.logger.warning(f"⚠️  未找到知识库虚拟环境: {kb_python}，使用当前 Python")
            kb_python = sys.executable
        
        cmd = [
            str(kb_python),
            str(ingest_script),
            "--root", str(self.classified_dir.absolute()),
            "--only-new",  # 仅处理新文档
        ]
        
        # 如果配置了 workers
        if "kb_workers" in self.config.get("integration", {}):
            cmd.extend(["--workers", str(self.config["integration"]["kb_workers"])])
        
        try:
            self.logger.info(f"🔄 运行: {' '.join(cmd)}")
            
            # 运行 ingest.py
            result = subprocess.run(
                cmd,
                cwd=str(self.kb_system_path),
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore'
            )
            
            if result.returncode == 0:
                self.logger.info("✅ 知识库更新成功")
                # 打印部分输出
                if result.stdout:
                    lines = result.stdout.strip().split('\n')
                    for line in lines[-10:]:  # 只显示最后10行
                        self.logger.info(f"  {line}")
            else:
                self.logger.error(f"❌ 知识库更新失败 (退出码: {result.returncode})")
                if result.stderr:
                    self.logger.error(f"错误输出: {result.stderr[:500]}")
                    
        except Exception as e:
            self.logger.error(f"❌ 调用 ingest.py 失败: {e}")
        
        self.logger.info("="*60 + "\n")
    
    def _print_integrated_stats(self, download_stats: Dict, classify_stats: Dict):
        """打印整合统计信息"""
        self.logger.info("\n" + "="*60)
        self.logger.info("📊 本轮统计")
        self.logger.info("="*60)
        self.logger.info(f"下载文件: {download_stats['files_downloaded']}")
        self.logger.info(f"分类成功: {classify_stats['successful']}")
        self.logger.info(f"分类失败: {classify_stats['failed']}")
        self.logger.info(f"累计下载: {self.downloader.total_files_downloaded}")
        self.logger.info("="*60 + "\n")


def setup_logging(debug: bool = False) -> logging.Logger:
    """配置日志"""
    level = logging.DEBUG if debug else logging.INFO
    
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("integrated_system.log", encoding="utf-8")
        ]
    )
    
    return logging.getLogger("integrated_system")


def load_config(config_path: Path) -> Dict:
    """加载配置文件"""
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="整合下载与分类系统",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--download-dir",
        type=Path,
        default=Path("./downloads_temp"),
        help="下载临时目录（默认: ./downloads_temp）"
    )
    
    parser.add_argument(
        "--classified-dir",
        type=Path,
        default=Path("./downloads_classified"),
        help="分类后的目标目录（默认: ./downloads_classified）"
    )
    
    parser.add_argument(
        "--keyword-db",
        type=Path,
        default=Path("./keywords.json"),
        help="关键词数据库路径（默认: ./keywords.json）"
    )
    
    parser.add_argument(
        "--kb-system",
        type=Path,
        default=Path("../axis-SQLite"),
        help="知识库系统路径（axis-SQLite目录，默认: ../axis-SQLite）"
    )
    
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("./integrated_config.json"),
        help="配置文件路径"
    )
    
    parser.add_argument(
        "--mode",
        choices=["integrated", "classify-only", "download-only"],
        default="integrated",
        help="运行模式"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="调试模式"
    )
    
    args = parser.parse_args()
    
    # 设置日志
    logger = setup_logging(args.debug)
    
    # 加载配置
    config = load_config(args.config)
    
    # 从配置文件覆盖路径（如果有）
    if "paths" in config:
        paths = config["paths"]
        if "download_dir" in paths:
            args.download_dir = Path(paths["download_dir"])
        if "classified_dir" in paths:
            args.classified_dir = Path(paths["classified_dir"])
        if "kb_system" in paths:
            args.kb_system = Path(paths["kb_system"])
    
    # 创建整合系统
    system = IntegratedDownloaderClassifier(
        download_dir=args.download_dir,
        classified_dir=args.classified_dir,
        keyword_db_path=args.keyword_db,
        kb_system_path=args.kb_system,
        config=config,
        logger=logger
    )
    
    # 根据模式运行
    if args.mode == "integrated":
        system.run_integrated_mode()
    elif args.mode == "classify-only":
        system.run_classify_only_mode()
    elif args.mode == "download-only":
        system.run_download_only_mode()
    else:
        logger.error(f"未知模式: {args.mode}")


if __name__ == "__main__":
    main()
