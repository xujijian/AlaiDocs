#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
关键词管理器
管理已使用的关键词，追踪效果，避免重复

作者: AI 助手
版本: 1.0.0
日期: 2026-01-26
Python: 3.10+
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set


class KeywordManager:
    """关键词管理器"""
    
    def __init__(self, db_path: Path, logger: Optional[logging.Logger] = None):
        """
        初始化关键词管理器
        
        Args:
            db_path: 数据库文件路径（JSON格式）
            logger: 日志记录器
        """
        self.db_path = Path(db_path)
        self.logger = logger or logging.getLogger(__name__)
        self.data = self._load_db()
    
    def _load_db(self) -> Dict:
        """加载数据库"""
        if self.db_path.exists():
            try:
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.logger.info(f"📚 加载关键词数据库: {len(data.get('keywords', {}))} 个关键词")
                    return data
            except Exception as e:
                self.logger.error(f"❌ 加载数据库失败: {e}")
        
        # 初始化空数据库
        return {
            "keywords": {},  # 关键词: {used_count, last_used, files_found, total_size}
            "statistics": {
                "total_keywords_used": 0,
                "total_searches": 0,
                "total_files_downloaded": 0,
                "last_updated": None
            }
        }
    
    def _save_db(self):
        """保存数据库"""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            self.logger.debug(f"💾 保存关键词数据库")
        except Exception as e:
            self.logger.error(f"❌ 保存数据库失败: {e}")
    
    def add_keyword(self, keyword: str, files_found: int = 0, total_size: int = 0):
        """
        添加或更新关键词
        
        Args:
            keyword: 关键词
            files_found: 找到的文件数
            total_size: 文件总大小（字节）
        """
        keyword_lower = keyword.lower().strip()
        
        if keyword_lower in self.data["keywords"]:
            # 更新现有关键词
            kw_data = self.data["keywords"][keyword_lower]
            kw_data["used_count"] += 1
            kw_data["files_found"] += files_found
            kw_data["total_size"] += total_size
            kw_data["last_used"] = datetime.now().isoformat()
        else:
            # 添加新关键词
            self.data["keywords"][keyword_lower] = {
                "original": keyword,
                "used_count": 1,
                "files_found": files_found,
                "total_size": total_size,
                "first_used": datetime.now().isoformat(),
                "last_used": datetime.now().isoformat()
            }
            self.data["statistics"]["total_keywords_used"] += 1
        
        self.data["statistics"]["total_searches"] += 1
        self.data["statistics"]["total_files_downloaded"] += files_found
        self.data["statistics"]["last_updated"] = datetime.now().isoformat()
        
        self._save_db()
    
    def is_keyword_used(self, keyword: str) -> bool:
        """检查关键词是否已使用"""
        return keyword.lower().strip() in self.data["keywords"]
    
    def get_keyword_info(self, keyword: str) -> Optional[Dict]:
        """获取关键词信息"""
        return self.data["keywords"].get(keyword.lower().strip())
    
    def get_all_keywords(self) -> List[str]:
        """获取所有已使用的关键词"""
        return [kw_data["original"] for kw_data in self.data["keywords"].values()]
    
    def get_recent_keywords(self, limit: int = 20) -> List[str]:
        """获取最近使用的关键词"""
        keywords = sorted(
            self.data["keywords"].items(),
            key=lambda x: x[1]["last_used"],
            reverse=True
        )
        return [kw_data["original"] for _, kw_data in keywords[:limit]]
    
    def get_effective_keywords(self, min_files: int = 1, limit: int = 20) -> List[Dict]:
        """
        获取效果最好的关键词
        
        Args:
            min_files: 最少文件数
            limit: 返回数量
            
        Returns:
            关键词列表，按效果排序
        """
        effective = [
            {
                "keyword": kw_data["original"],
                "files_found": kw_data["files_found"],
                "total_size": kw_data["total_size"],
                "used_count": kw_data["used_count"],
                "avg_files": kw_data["files_found"] / kw_data["used_count"]
            }
            for kw_data in self.data["keywords"].values()
            if kw_data["files_found"] >= min_files
        ]
        
        effective.sort(key=lambda x: x["avg_files"], reverse=True)
        return effective[:limit]
    
    def get_ineffective_keywords(self, max_files: int = 0, limit: int = 20) -> List[str]:
        """获取效果不好的关键词"""
        ineffective = [
            kw_data["original"]
            for kw_data in self.data["keywords"].values()
            if kw_data["files_found"] <= max_files
        ]
        return ineffective[:limit]
    
    def filter_new_keywords(self, keywords: List[str], allow_reuse_days: int = 7) -> List[str]:
        """
        过滤出可用的关键词
        
        Args:
            keywords: 待过滤的关键词列表
            allow_reuse_days: 允许重用的天数间隔（默认7天）
            
        Returns:
            可用关键词列表（未使用的 + 超过重用间隔的）
        """
        from datetime import datetime, timedelta
        
        reuse_keywords = []
        new_keywords = []
        cutoff_time = (datetime.now() - timedelta(days=allow_reuse_days)).isoformat()
        
        for kw in keywords:
            if not self.is_keyword_used(kw):
                # 全新关键词
                new_keywords.append(kw)
            else:
                # 已用关键词，检查是否可重用
                kw_info = self.get_keyword_info(kw)
                if kw_info:
                    # 如果超过重用间隔 且 之前有效果（files_found > 0）
                    if kw_info["last_used"] < cutoff_time and kw_info["files_found"] > 0:
                        reuse_keywords.append(kw)
        
        # 优先使用新关键词，不足时补充可重用的
        result = new_keywords + reuse_keywords
        
        if reuse_keywords:
            self.logger.info(f"🔄 重用 {len(reuse_keywords)} 个旧关键词（超过 {allow_reuse_days} 天且曾有效）")
        
        return result
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        stats = self.data["statistics"].copy()
        
        if self.data["keywords"]:
            total_files = sum(kw["files_found"] for kw in self.data["keywords"].values())
            total_searches = stats["total_searches"]
            stats["avg_files_per_search"] = total_files / total_searches if total_searches > 0 else 0
            
            total_size = sum(kw["total_size"] for kw in self.data["keywords"].values())
            stats["total_size_mb"] = total_size / (1024 * 1024)
        
        return stats
    
    def print_statistics(self):
        """打印统计信息"""
        stats = self.get_statistics()
        
        self.logger.info("\n" + "="*60)
        self.logger.info("📊 关键词使用统计")
        self.logger.info("="*60)
        self.logger.info(f"总关键词数: {stats['total_keywords_used']}")
        self.logger.info(f"总搜索次数: {stats['total_searches']}")
        self.logger.info(f"总下载文件数: {stats['total_files_downloaded']}")
        self.logger.info(f"平均每次搜索文件数: {stats.get('avg_files_per_search', 0):.2f}")
        self.logger.info(f"总下载大小: {stats.get('total_size_mb', 0):.2f} MB")
        
        if stats['last_updated']:
            self.logger.info(f"最后更新: {stats['last_updated']}")
        
        self.logger.info("="*60 + "\n")
        
        # 显示效果最好的关键词
        effective = self.get_effective_keywords(min_files=1, limit=10)
        if effective:
            self.logger.info("🏆 效果最好的关键词 (Top 10):")
            for i, kw_info in enumerate(effective, 1):
                self.logger.info(
                    f"{i:2d}. {kw_info['keyword']}: "
                    f"{kw_info['files_found']} 文件 "
                    f"(平均 {kw_info['avg_files']:.1f} 文件/次)"
                )
            self.logger.info("")
        
        # 显示最近使用的关键词
        recent = self.get_recent_keywords(limit=10)
        if recent:
            self.logger.info("🕐 最近使用的关键词 (Top 10):")
            for i, kw in enumerate(recent, 1):
                info = self.get_keyword_info(kw)
                self.logger.info(
                    f"{i:2d}. {kw}: "
                    f"{info['files_found']} 文件, "
                    f"使用 {info['used_count']} 次"
                )
            self.logger.info("")


def main():
    """测试函数"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    
    logger = logging.getLogger(__name__)
    
    # 测试关键词管理器
    db_path = Path("test_keywords.json")
    manager = KeywordManager(db_path, logger)
    
    # 添加一些测试关键词
    test_keywords = [
        ("LM5164 datasheet", 5, 10000000),
        ("buck converter design", 3, 5000000),
        ("synchronous DCDC", 8, 15000000),
        ("automotive power supply", 2, 3000000),
        ("high efficiency converter", 0, 0),
    ]
    
    for kw, files, size in test_keywords:
        manager.add_keyword(kw, files, size)
        logger.info(f"添加关键词: {kw}")
    
    # 打印统计
    manager.print_statistics()
    
    # 测试过滤
    new_keywords = [
        "LM5164 datasheet",  # 已存在
        "boost converter design",  # 新关键词
        "flyback transformer",  # 新关键词
    ]
    
    filtered = manager.filter_new_keywords(new_keywords)
    logger.info(f"过滤后的新关键词: {filtered}")


if __name__ == "__main__":
    main()
