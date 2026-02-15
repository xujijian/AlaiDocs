#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分类监控器 - 持续监控并分类新下载的PDF文件
"""

import sys
import time
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import json
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from threading import Lock

from pdf_classifier import PDFClassifier, ProcessedFilesDB


class PDFWatcher(FileSystemEventHandler):
    """PDF文件监控器"""
    
    def __init__(self, classifier, logger, stable_seconds=15, workers=4):
        self.classifier = classifier
        self.logger = logger
        self.stable_seconds = stable_seconds
        self.workers = workers
        self.pending_files = {}  # {path: first_seen_time}
        self.processing_files = set()  # 正在处理的文件
        self.lock = Lock()  # 线程锁
        self.executor = ThreadPoolExecutor(max_workers=workers)
        self.futures = []  # 跟踪进行中的任务
        self.logger.info(f"⚡ 使用线程池 ({workers} 线程)")
        self.logger.info(f"💡 PDF解析受GIL限制，实际加速约 2-3x")
    
    def _classify_single_file(self, path):
        """处理单个文件（线程安全）"""
        try:
            pdf_path = Path(path)
            if pdf_path.exists():
                with self.lock:
                    self.processing_files.add(path)
                
                self.logger.info(f"🗂️  分类: {pdf_path.name}")
                self.classifier.process_file(pdf_path)
                
                with self.lock:
                    self.processing_files.discard(path)
            else:
                self.logger.warning(f"⚠️  文件不存在: {pdf_path.name}")
        except Exception as e:
            self.logger.error(f"❌ 分类失败 {Path(path).name}: {e}")
            with self.lock:
                self.processing_files.discard(path)
    
    def on_created(self, event):
        """文件创建事件"""
        if event.is_directory:
            return
        
        if event.src_path.lower().endswith('.pdf'):
            with self.lock:
                # 避免重复添加
                if event.src_path not in self.pending_files and event.src_path not in self.processing_files:
                    self.logger.info(f"📥 发现新文件: {Path(event.src_path).name}")
                    self.pending_files[event.src_path] = time.time()
    
    def process_pending(self):
        """处理待处理文件（并行）"""
        current_time = time.time()
        to_process = []
        
        with self.lock:
            for path, first_seen in list(self.pending_files.items()):
                if current_time - first_seen >= self.stable_seconds:
                    to_process.append(path)
                    del self.pending_files[path]
        
        if to_process:
            # 使用线程池并行处理
            for path in to_process:
                future = self.executor.submit(self._classify_single_file, path)
                self.futures.append(future)
            
            # 清理已完成的任务
            self.futures = [f for f in self.futures if not f.done()]
    
    def shutdown(self):
        """关闭线程池"""
        self.logger.info("⏳ 等待所有任务完成...")
        self.executor.shutdown(wait=True)
        self.logger.info("✅ 所有任务已完成")


def main():
    """主函数"""
    # 加载配置
    config_path = Path("integrated_config.json")
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("classify_watcher.log", encoding="utf-8")
        ]
    )
    logger = logging.getLogger("classify_watcher")
    
    # 路径配置
    watch_dir = Path(config["paths"]["download_dir"]).resolve()
    target_dir = Path(config["paths"]["classified_dir"]).resolve()
    
    logger.info("=" * 60)
    logger.info("🚀 启动分类监控器")
    logger.info("=" * 60)
    logger.info(f"监控目录: {watch_dir}")
    logger.info(f"分类目录: {target_dir}")
    logger.info(f"📝 配置文件读取: download_dir={config['paths']['download_dir']}, classified_dir={config['paths']['classified_dir']}")
    
    # 检查待分类文件
    existing_pdfs = list(watch_dir.rglob("*.pdf"))
    # 修改：处理所有PDF文件，不限于特定厂商子目录
    if existing_pdfs:
        logger.info(f"🔍 发现 {len(existing_pdfs)} 个待分类PDF文件")
        for pdf in existing_pdfs[:5]:
            relative_path = pdf.relative_to(watch_dir)
            logger.info(f"   - {relative_path}")
        if len(existing_pdfs) > 5:
            logger.info(f"   ... 还有 {len(existing_pdfs) - 5} 个文件")
    else:
        logger.info("📭 当前没有待分类文件")
    logger.info("")
    
    # 创建分类器
    db_path = Path("classified_files.db")
    classifier_db = ProcessedFilesDB(db_path)
    metadata_file = target_dir / "metadata.jsonl"
    logger.info(f"📊 数据库: {db_path.absolute()}")
    
    classifier = PDFClassifier(
        source_dir=watch_dir,
        target_dir=target_dir,
        db=classifier_db,
        metadata_file=metadata_file,
        head_pages=config.get("classifier", {}).get("head_pages", 3),
        mode="copy",
        dry_run=False
    )
    
    logger.info(f"🎯 分类器配置: source={classifier.source_dir}, target={classifier.target_dir}")
    
    # 获取并发数
    workers = config.get("classifier", {}).get("workers", 4)
    logger.info(f"⚡ 并发线程数: {workers}")
    
    # 创建监控器
    event_handler = PDFWatcher(
        classifier, 
        logger,
        stable_seconds=config.get("classifier", {}).get("min_stable_seconds", 15),
        workers=workers
    )
    observer = Observer()
    observer.schedule(event_handler, str(watch_dir), recursive=True)
    observer.start()
    
    logger.info("✅ 监控已启动，等待新文件...")
    logger.info("按 Ctrl+C 停止\n")
    
    # 处理启动时存在的文件（并行）
    if existing_pdfs:
        logger.info(f"🔄 处理启动前已存在的 {len(existing_pdfs)} 个文件 ({workers} 并发)...")
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(event_handler._classify_single_file, str(pdf)) for pdf in existing_pdfs]
            for future in as_completed(futures):
                pass  # 结果已在 _classify_single_file 中记录
        logger.info(f"✅ 启动时文件处理完成\n")
    
    try:
        while True:
            time.sleep(5)
            event_handler.process_pending()
    except KeyboardInterrupt:
        logger.info("\n⚠️  用户中断")
        observer.stop()
        event_handler.shutdown()
    
    observer.join()
    logger.info("✅ 监控已停止")


if __name__ == "__main__":
    main()
