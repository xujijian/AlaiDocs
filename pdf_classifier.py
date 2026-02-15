#!/usr/bin/env python3
"""
DC-DC PDF 自动分类系统
作者：资深 Python 工程师 + 电力电子资料归档系统工程师
版本：1.0.0
"""

import os
import sys
import json
import time
import hashlib
import logging
import argparse
import sqlite3
import shutil
import re
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# PDF 文本抽取
try:
    from pypdf import PdfReader
    PDF_LIBRARY = "pypdf"
except ImportError:
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract
        PDF_LIBRARY = "pdfminer"
    except ImportError:
        print("错误：请安装 pypdf 或 pdfminer.six")
        sys.exit(1)


# ============================================================================
# 分类规则定义
# ============================================================================

VENDORS = {
    'TI': {'keywords': ['ti', 'texas instruments', 'ti.com'], 'weight': 1.0},
    'ST': {'keywords': ['st', 'stmicroelectronics', 'st.com'], 'weight': 1.0},
    'ADI': {'keywords': ['adi', 'analog devices', 'analog.com'], 'weight': 1.0},
    'Infineon': {'keywords': ['infineon', 'infineon.com'], 'weight': 1.0},
    'onsemi': {'keywords': ['onsemi', 'on semiconductor', 'onsemi.com'], 'weight': 1.0},
    'Renesas': {'keywords': ['renesas', 'renesas.com'], 'weight': 1.0},
    'Microchip': {'keywords': ['microchip', 'microchip.com'], 'weight': 1.0},
    'ROHM': {'keywords': ['rohm', 'rohm.com'], 'weight': 1.0},
    'NXP': {'keywords': ['nxp', 'nxp.com'], 'weight': 1.0},
    'MPS': {'keywords': ['mps', 'monolithic power', 'monolithicpower.com'], 'weight': 1.0},
    'PI': {'keywords': ['power integrations', 'powerint.com'], 'weight': 1.0},
    'Vicor': {'keywords': ['vicor', 'vicorpower.com'], 'weight': 1.0},
    'Littelfuse': {'keywords': ['littelfuse', 'littelfuse.com'], 'weight': 1.0},
    'Bourns': {'keywords': ['bourns', 'bourns.com'], 'weight': 1.0},
    'Nexperia': {'keywords': ['nexperia', 'nexperia.com'], 'weight': 1.0},
    'Vishay': {'keywords': ['vishay', 'vishay.com'], 'weight': 1.0},
    'Murata': {'keywords': ['murata', 'murata.com'], 'weight': 1.0},
    'TDK': {'keywords': ['tdk', 'tdk.com', 'tdk electronics'], 'weight': 1.0},
    'Wurth': {'keywords': ['wurth', 'würth', 'we-online', 'wurth elektronik'], 'weight': 1.0},
    'Kemet': {'keywords': ['kemet', 'kemet.com'], 'weight': 1.0},
    'Semtech': {'keywords': ['semtech', 'semtech.com'], 'weight': 1.0},
    'Laird': {'keywords': ['laird', 'laird connectivity', 'lairdtech'], 'weight': 1.0},
    'Fair-Rite': {'keywords': ['fair-rite', 'fair rite'], 'weight': 1.0},
    'Others': {'keywords': [], 'weight': 0.5},
}

DOC_TYPES = {
    'datasheet': {
        'keywords': [
            'electrical characteristics', 'absolute maximum ratings',
            'pin configuration', 'typical application', 'ordering information',
            'mechanical data', 'package information', 'thermal characteristics'
        ],
        'weight': 1.0
    },
    'application_note': {
        'keywords': [
            'application note', 'design considerations', 'compensation',
            'loop stability', 'layout guidelines', 'design guide',
            'implementation', 'practical design'
        ],
        'weight': 1.0
    },
    'reference_design': {
        'keywords': [
            'reference design', 'bom', 'bill of materials', 'schematic',
            'test results', 'design files', 'gerber', 'assembly drawing'
        ],
        'weight': 1.0
    },
    'eval_user_guide': {
        'keywords': [
            'user guide', 'evaluation module', 'evm', 'quick start',
            'getting started', 'evaluation board', 'user manual'
        ],
        'weight': 1.0
    },
    'whitepaper': {
        'keywords': [
            'white paper', 'technical article', 'overview', 'introduction to'
        ],
        'weight': 0.8
    },
    'standard': {
        'keywords': [
            'iec', 'ul', 'iso', 'gb/t', 'standard', 'specification', 'compliance',
            'cispr', 'sae', 'iso 7637', 'iso 16750', 'iec 61000', 'iec 62132',
            'aec-q100', 'aec-q101', 'aec-q200', 'jedec', 'normative', 'annex'
        ],
        'weight': 1.0
    },
    'test_report': {
        'keywords': [
            'test report', 'test result', 'measurement result', 'compliance report',
            'qualification report', 'emc test report', 'immunity test',
            'emission test', 'pass', 'fail', 'test configuration', 'test setup',
            'test procedure', 'certificate', 'certification'
        ],
        'weight': 1.0
    },
    'presentation': {
        'keywords': [
            'presentation', 'slide', 'seminar', 'workshop', 'training'
        ],
        'weight': 0.7
    },
    'software': {
        'keywords': [
            'software', 'firmware', 'driver', 'api', 'programming guide', 'sdk'
        ],
        'weight': 0.8
    },
}

TOPICS = {
    'power_ic': {
        'keywords': [
            'pmic', 'controller', 'regulator', 'dc-dc', 'dc/dc', 'converter',
            'buck', 'boost', 'ldo', 'switching regulator'
        ],
        'weight': 1.0
    },
    'power_stage': {
        'keywords': [
            'mosfet', 'gan', 'sic', 'gate driver', 'half-bridge', 'module',
            'power switch', 'transistor', 'igbt'
        ],
        'weight': 1.0
    },
    'magnetics': {
        'keywords': [
            'inductor', 'transformer', 'magnetic', 'core', 'winding',
            'coupled inductor', 'saturation'
        ],
        'weight': 0.9
    },
    'emi_emc': {
        'keywords': [
            'emi', 'emc', 'cispr', 'filter', 'layout', 'grounding',
            'electromagnetic interference', 'noise', 'conducted', 'radiated',
            'electromagnetic compatibility', 'emission', 'susceptibility',
            'common mode', 'differential mode', 'shielding', 'decoupling',
            'ferrite', 'choke', 'emi filter', 'emc compliance',
            'spread spectrum', 'frequency modulation', 'near field',
            'spectrum analyzer', 'pcb layout emc', 'ground plane'
        ],
        'weight': 1.0
    },
    'transient_protection': {
        'keywords': [
            'transient', 'tvs', 'tvs diode', 'transient voltage suppressor',
            'surge', 'surge protection', 'load dump', 'clamping',
            'overvoltage', 'overvoltage protection', 'reverse battery',
            'reverse polarity', 'iso 7637', 'iso 16750', 'pulse',
            'cold crank', 'jump start', 'voltage spike', 'inrush',
            'crowbar', 'varistor', 'suppressor'
        ],
        'weight': 1.0
    },
    'esd_protection': {
        'keywords': [
            'esd', 'electrostatic discharge', 'esd protection',
            'iec 61000-4-2', 'human body model', 'hbm', 'charged device model',
            'cdm', 'machine model', 'esd suppressor', 'esd diode',
            'system level esd', 'contact discharge', 'air discharge'
        ],
        'weight': 1.0
    },
    'reliability_qualification': {
        'keywords': [
            'reliability', 'qualification', 'aec-q100', 'aec-q101', 'aec-q200',
            'htol', 'htsl', 'hast', 'thermal cycling', 'temperature cycling',
            'halt', 'hass', 'fmea', 'mission profile', 'lifetime',
            'accelerated life', 'burn-in', 'stress test', 'environmental test',
            'vibration', 'humidity', 'salt spray', 'mechanical shock',
            'mtbf', 'fit rate', 'failure analysis'
        ],
        'weight': 1.0
    },
    'immunity_testing': {
        'keywords': [
            'immunity', 'immunity test', 'iec 61000-4-3', 'iec 61000-4-4',
            'iec 61000-4-5', 'iec 61000-4-6', 'iec 62132',
            'bci', 'bulk current injection', 'dpi', 'direct power injection',
            'radiated immunity', 'conducted immunity', 'rf immunity',
            'fast transient', 'burst', 'eft', 'electrical fast transient',
            'tem cell', 'stripline', 'reverberation chamber'
        ],
        'weight': 1.0
    },
    'control_loop': {
        'keywords': [
            'compensation', 'stability', 'bode', 'phase margin', 'loop',
            'frequency response', 'transfer function', 'feedback'
        ],
        'weight': 0.9
    },
    'thermal': {
        'keywords': [
            'thermal', 'junction', 'heatsink', 'derating', 'temperature',
            'cooling', 'thermal resistance'
        ],
        'weight': 0.8
    },
    'safety_reliability': {
        'keywords': [
            'ovp', 'ocp', 'scp', 'functional safety', 'reliability', 'fit',
            'mtbf', 'protection', 'fault', 'fmea', 'fmeda', 'asil',
            'iso 26262', 'diagnostic', 'safe state'
        ],
        'weight': 0.9
    },
    'system_solution': {
        'keywords': [
            'system', 'solution', 'architecture', 'design guide',
            'platform', 'multi-phase'
        ],
        'weight': 0.8
    },
    'test_measurement': {
        'keywords': [
            'test setup', 'measurement', 'oscilloscope', 'probe',
            'efficiency measurement', 'characterization', 'testing',
            'spectrum analyzer', 'network analyzer', 'lisn', 'antenna',
            'pre-compliance', 'test chamber', 'anechoic'
        ],
        'weight': 0.9
    },
    'automotive_electrical': {
        'keywords': [
            'automotive', 'vehicle', 'ecu', 'car', '12v system', '24v system',
            '48v system', 'mild hybrid', 'power distribution', 'wire harness',
            'can bus', 'lin bus', 'connector', 'automotive grade',
            'iatf', 'ppap', 'apqp'
        ],
        'weight': 0.9
    },
}

TOPOLOGIES = {
    'buck': {'keywords': ['buck', 'step-down', 'step down'], 'weight': 1.0},
    'boost': {'keywords': ['boost', 'step-up', 'step up'], 'weight': 1.0},
    'buck_boost': {'keywords': ['buck-boost', 'buck boost', 'inverting'], 'weight': 1.0},
    '4switch_buck_boost': {
        'keywords': ['4-switch', '4 switch', 'four-switch', 'four switch', '4-sw'],
        'weight': 1.0
    },
    'flyback': {'keywords': ['flyback', 'fly-back'], 'weight': 1.0},
    'llc': {'keywords': ['llc', 'resonant'], 'weight': 1.0},
    'cllc': {'keywords': ['cllc', 'bidirectional resonant'], 'weight': 1.0},
    'dab': {'keywords': ['dab', 'dual active bridge'], 'weight': 1.0},
    'sepic': {'keywords': ['sepic'], 'weight': 1.0},
    'cuk': {'keywords': ['cuk', 'ćuk'], 'weight': 1.0},
    'inverter': {'keywords': ['inverter', 'dc-ac', 'dc/ac'], 'weight': 1.0},
    'charger': {'keywords': ['charger', 'charging', 'battery charger'], 'weight': 1.0},
    'bms': {'keywords': ['bms', 'battery management'], 'weight': 1.0},
    'other': {'keywords': ['forward', 'push-pull', 'full-bridge', 'half-bridge'], 'weight': 0.8},
    'bidirectional': {'keywords': ['bidirectional', 'bi-directional', 'bibuckboost', 'bi buck boost'], 'weight': 1.0},
    'protection_circuit': {'keywords': ['tvs', 'tvs diode', 'esd protection', 'surge protection', 'clamping circuit', 'suppressor', 'varistor'], 'weight': 1.0},
    'filter_circuit': {'keywords': ['emi filter', 'emc filter', 'common mode choke', 'differential mode', 'pi filter', 'lc filter', 'ferrite bead'], 'weight': 1.0},
}


# ============================================================================
# 工具函数
# ============================================================================

def calculate_sha256(filepath: Path) -> str:
    """计算文件的SHA256哈希值"""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def is_valid_pdf(filepath: Path) -> Tuple[bool, str]:
    """
    验证文件是否为有效的PDF
    
    Args:
        filepath: 文件路径
    
    Returns:
        (是否有效, 错误信息)
    """
    try:
        with open(filepath, 'rb') as f:
            header = f.read(10)
            # PDF文件必须以 %PDF 开头
            if not header.startswith(b'%PDF'):
                header_str = header[:10] if len(header) >= 10 else header
                return False, f"无效的PDF头部: {header_str}"
        return True, ""
    except Exception as e:
        return False, f"读取失败: {e}"


def is_file_stable(filepath: Path, checks: int = 3, min_stable_seconds: int = 10) -> bool:
    """
    检查文件是否稳定（不在下载/写入中）
    
    Args:
        filepath: 文件路径
        checks: 检查次数
        min_stable_seconds: 最小稳定时间（秒）
    
    Returns:
        True if stable, False otherwise
    """
    if not filepath.exists():
        return False
    
    # 检查文件修改时间
    mtime = filepath.stat().st_mtime
    age = time.time() - mtime
    if age < min_stable_seconds:
        return False
    
    # 连续检查文件大小
    sizes = []
    interval = min_stable_seconds / checks
    for _ in range(checks):
        if not filepath.exists():
            return False
        sizes.append(filepath.stat().st_size)
        if len(sizes) >= 2 and sizes[-1] != sizes[-2]:
            return False
        if _ < checks - 1:  # 最后一次不需要等待
            time.sleep(interval)
    
    # 尝试打开文件检查是否被锁定
    try:
        with open(filepath, 'rb') as f:
            f.read(1)
    except (PermissionError, IOError):
        return False
    
    return True


def extract_pdf_text(filepath: Path, max_pages: int = 3) -> Tuple[str, int]:
    """
    抽取PDF前N页的文本
    
    Args:
        filepath: PDF文件路径
        max_pages: 最大抽取页数
    
    Returns:
        (文本内容, 总页数)
    """
    text = ""
    page_count = 0
    
    try:
        if PDF_LIBRARY == "pypdf":
            reader = PdfReader(str(filepath))
            page_count = len(reader.pages)
            for i in range(min(max_pages, page_count)):
                page = reader.pages[i]
                text += page.extract_text() + "\n"
        else:  # pdfminer
            # pdfminer提取所有页，我们只取前N页的近似
            full_text = pdfminer_extract(str(filepath))
            text = full_text[:50000]  # 粗略限制
            page_count = -1  # 无法准确获取
    except Exception as e:
        logging.warning(f"PDF文本抽取失败 {filepath}: {e}")
        return "", 0
    
    return text, page_count


def normalize_text(text: str) -> str:
    """规范化文本：小写、去除多余空格"""
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def score_keywords(text: str, keywords: List[str], weight: float = 1.0) -> Tuple[float, List[str]]:
    """
    关键词打分
    
    Args:
        text: 待匹配文本
        keywords: 关键词列表
        weight: 权重
    
    Returns:
        (得分, 匹配的关键词列表)
    """
    text_norm = normalize_text(text)
    score = 0.0
    matched = []
    
    for keyword in keywords:
        keyword_norm = normalize_text(keyword)
        # 使用单词边界匹配，避免部分匹配
        pattern = r'\b' + re.escape(keyword_norm) + r'\b'
        matches = re.findall(pattern, text_norm)
        if matches:
            count = len(matches)
            score += weight * count
            matched.append(keyword)
    
    return score, matched


def classify_dimension(
    filename: str,
    text: str,
    dimension_dict: Dict,
    unknown_label: str = "unknown"
) -> Tuple[str, float, List[str]]:
    """
    对单个维度进行分类
    
    Args:
        filename: 文件名
        text: PDF文本内容
        dimension_dict: 维度的关键词字典
        unknown_label: 未知类别标签
    
    Returns:
        (分类结果, 置信度, 匹配关键词)
    """
    scores = {}
    all_matched = {}
    
    # 文件名匹配权重更高
    filename_norm = normalize_text(filename)
    
    for label, config in dimension_dict.items():
        keywords = config['keywords']
        weight = config['weight']
        
        # 文件名打分 (权重 x3)
        fn_score, fn_matched = score_keywords(filename_norm, keywords, weight * 3)
        
        # 文本打分
        text_score, text_matched = score_keywords(text, keywords, weight)
        
        total_score = fn_score + text_score
        scores[label] = total_score
        all_matched[label] = list(set(fn_matched + text_matched))
    
    # 选择最高分
    if not scores or max(scores.values()) == 0:
        return unknown_label, 0.0, []
    
    best_label = max(scores, key=scores.get)
    best_score = scores[best_label]
    
    # 计算置信度 (0-1)
    total_score = sum(scores.values())
    confidence = best_score / (total_score + 1e-6) if total_score > 0 else 0.0
    
    return best_label, confidence, all_matched[best_label]


def guess_title_from_text(text: str) -> str:
    """从文本中猜测标题（取第一行或第一段）"""
    lines = text.strip().split('\n')
    for line in lines:
        line = line.strip()
        if len(line) > 10 and len(line) < 200:
            return line
    return "Unknown Title"


def guess_language(text: str) -> str:
    """简单的语言猜测（中文 vs 英文）"""
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    english_chars = len(re.findall(r'[a-zA-Z]', text))
    
    if chinese_chars > english_chars * 0.3:
        return "zh"
    return "en"


# ============================================================================
# 数据库管理
# ============================================================================

class ProcessedFilesDB:
    """管理已处理文件的SQLite数据库（线程安全）"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._local = threading.local()
        # 在主线程初始化表结构
        self._init_db_schema()
    
    def _init_db_schema(self):
        """初始化数据库表结构（仅主线程）"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_files (
                doc_id TEXT PRIMARY KEY,
                src_path TEXT,
                dst_path TEXT,
                processed_time TEXT,
                metadata TEXT
            )
        ''')
        conn.commit()
        conn.close()
    
    def _get_conn(self):
        """获取当前线程的数据库连接"""
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(str(self.db_path))
        return self._local.conn
    
    def is_processed(self, doc_id: str) -> bool:
        """检查文件是否已处理"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM processed_files WHERE doc_id = ?', (doc_id,))
        return cursor.fetchone() is not None
    
    def add_record(self, doc_id: str, src_path: str, dst_path: str, metadata: dict):
        """添加处理记录"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO processed_files 
            (doc_id, src_path, dst_path, processed_time, metadata)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            doc_id,
            src_path,
            dst_path,
            datetime.now().isoformat(),
            json.dumps(metadata, ensure_ascii=False)
        ))
        conn.commit()
    
    def close(self):
        """关闭所有线程的数据库连接"""
        if hasattr(self._local, 'conn'):
            self._local.conn.close()


# ============================================================================
# PDF分类器
# ============================================================================

class PDFClassifier:
    """PDF文档分类器"""
    
    def __init__(
        self,
        source_dir: Path,
        target_dir: Path,
        db: ProcessedFilesDB,
        metadata_file: Path,
        head_pages: int = 3,
        mode: str = 'move',
        dry_run: bool = False
    ):
        self.source_dir = source_dir
        self.target_dir = target_dir
        self.db = db
        self.metadata_file = metadata_file
        self.head_pages = head_pages
        self.mode = mode
        self.dry_run = dry_run
    
    def scan_new_files(self) -> List[Path]:
        """扫描源目录中的新PDF文件"""
        pdf_files = []
        for pdf_path in self.source_dir.rglob('*.pdf'):
            if pdf_path.is_file():
                pdf_files.append(pdf_path)
        return pdf_files
    
    def classify_file(self, filepath: Path) -> Dict:
        """
        分类单个PDF文件
        
        Returns:
            包含分类结果的字典
        """
        logging.info(f"开始处理: {filepath}")
        
        # 验证PDF文件有效性
        is_valid, error_msg = is_valid_pdf(filepath)
        if not is_valid:
            logging.warning(f"无效的PDF文件，移除: {filepath.name} - {error_msg}")
            if not self.dry_run:
                try:
                    # 移动到垃圾目录而不是直接删除（安全起见）
                    trash_dir = self.target_dir / "Trash" / "InvalidPDF"
                    trash_dir.mkdir(parents=True, exist_ok=True)
                    trash_path = trash_dir / filepath.name
                    
                    # 处理同名文件
                    if trash_path.exists():
                        filepath.unlink()
                    else:
                        shutil.move(str(filepath), str(trash_path))
                    
                    logging.info(f"已移至垃圾目录: {trash_path}")
                except Exception as e:
                    logging.error(f"移除无效文件失败: {e}")
            return None
        
        # 计算SHA256
        try:
            doc_id = calculate_sha256(filepath)
        except Exception as e:
            logging.error(f"计算SHA256失败 {filepath}: {e}")
            return self._error_result(filepath, f"计算SHA256失败: {e}")
        
        # 检查是否已处理
        if self.db.is_processed(doc_id):
            logging.info(f"文件已处理（重复），删除: {filepath.name} ({doc_id[:8]}...)")
            if not self.dry_run:
                try:
                    filepath.unlink()
                except Exception as e:
                    logging.error(f"删除重复文件失败: {e}")
            return None
        
        # 抽取文本
        text, page_count = extract_pdf_text(filepath, self.head_pages)
        
        if len(text.strip()) < 100:
            logging.warning(f"文本内容过少 ({len(text)} chars): {filepath}")
        
        # 准备分类输入
        filename = filepath.name
        
        # 分类各个维度
        vendor, vendor_conf, vendor_kw = classify_dimension(
            filename, text, VENDORS, "Unknown"
        )
        
        doc_type, dtype_conf, dtype_kw = classify_dimension(
            filename, text, DOC_TYPES, "unknown"
        )
        
        topic, topic_conf, topic_kw = classify_dimension(
            filename, text, TOPICS, "unknown"
        )
        
        topology, topo_conf, topo_kw = classify_dimension(
            filename, text, TOPOLOGIES, "unknown"
        )
        
        # 置信度检查
        confidence = dtype_conf
        if confidence < 0.6:
            logging.warning(f"低置信度 ({confidence:.2f}): {filepath}")
            doc_type = "unknown"
        
        # 猜测标题和语言
        title_guess = guess_title_from_text(text)
        language_guess = guess_language(text)
        
        # 构建目标路径
        dst_path = self._build_target_path(
            vendor, doc_type, topic, topology, filename
        )
        
        # 构建元数据
        metadata = {
            'doc_id': doc_id,
            'src_path': str(filepath),
            'dst_path': str(dst_path),
            'vendor': vendor,
            'doc_type': doc_type,
            'topic': topic,
            'topology': topology,
            'confidence': round(confidence, 3),
            'matched_keywords': {
                'vendor': vendor_kw,
                'doc_type': dtype_kw,
                'topic': topic_kw,
                'topology': topo_kw
            },
            'title_guess': title_guess[:200],
            'language_guess': language_guess,
            'page_count': page_count,
            'processed_time': datetime.now().isoformat(),
            'error': None
        }
        
        logging.debug(f"分类结果: {vendor}/{doc_type}/{topic}/{topology} (conf={confidence:.2f})")
        
        return metadata
    
    def _build_target_path(
        self,
        vendor: str,
        doc_type: str,
        topic: str,
        topology: str,
        filename: str
    ) -> Path:
        """构建目标路径 - 四维分类：厂商/文档类型/主题/拓扑"""
        # 处理低置信度情况
        if doc_type == "unknown":
            return self.target_dir / "Unknown" / "LowConfidence" / filename
        
        # 标准四维分类路径：厂商/文档类型/主题/拓扑
        return self.target_dir / vendor / doc_type / topic / topology / filename
    
    def _error_result(self, filepath: Path, error_msg: str) -> Dict:
        """构建错误结果"""
        return {
            'doc_id': 'error_' + str(time.time()),
            'src_path': str(filepath),
            'dst_path': str(self.target_dir / "Unknown" / "ErrorFiles" / filepath.name),
            'vendor': 'Unknown',
            'doc_type': 'unknown',
            'topic': 'unknown',
            'topology': 'unknown',
            'confidence': 0.0,
            'matched_keywords': {},
            'title_guess': '',
            'language_guess': '',
            'page_count': 0,
            'processed_time': datetime.now().isoformat(),
            'error': error_msg
        }
    
    def move_file(self, src: Path, dst: Path) -> bool:
        """移动或复制文件到目标位置"""
        try:
            # 确保目标目录存在
            dst.parent.mkdir(parents=True, exist_ok=True)
            
            # 处理同名文件 - 直接删除源文件
            if dst.exists():
                logging.info(f"目标文件已存在，删除源文件: {src.name}")
                if not self.dry_run:
                    src.unlink()
                return True
            
            if self.dry_run:
                logging.info(f"[DRY-RUN] {self.mode}: {src} -> {dst}")
                return True
            
            if self.mode == 'copy':
                shutil.copy2(src, dst)
                logging.info(f"复制: {src} -> {dst}")
            else:  # move
                shutil.move(str(src), str(dst))
                logging.info(f"移动: {src} -> {dst}")
            
            return True
        
        except Exception as e:
            logging.error(f"文件操作失败 {src} -> {dst}: {e}")
            return False
    
    def process_file(self, filepath: Path) -> bool:
        """处理单个文件的完整流程"""
        try:
            # 分类
            metadata = self.classify_file(filepath)
            
            if metadata is None:
                return True  # 已处理过，跳过
            
            # 移动文件
            src = filepath
            dst = Path(metadata['dst_path'])
            
            success = self.move_file(src, dst)
            
            if success:
                # 更新数据库
                self.db.add_record(
                    metadata['doc_id'],
                    metadata['src_path'],
                    metadata['dst_path'],
                    metadata
                )
                
                # 写入元数据文件
                with open(self.metadata_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(metadata, ensure_ascii=False) + '\n')
                
                logging.info(f"✓ 处理完成: {filepath.name}")
                return True
            else:
                logging.error(f"✗ 文件移动失败: {filepath.name}")
                return False
        
        except Exception as e:
            logging.error(f"处理文件时发生异常 {filepath}: {e}", exc_info=True)
            return False
    
    def run_once(self, min_stable_seconds: int = 10) -> int:
        """执行一次扫描和处理"""
        logging.info("=" * 60)
        logging.info("开始扫描...")
        
        files = self.scan_new_files()
        logging.info(f"发现 {len(files)} 个PDF文件")
        
        processed = 0
        for filepath in files:
            # 检查文件稳定性
            if not is_file_stable(filepath, checks=3, min_stable_seconds=min_stable_seconds):
                logging.info(f"文件不稳定，跳过: {filepath}")
                continue
            
            # 处理文件
            if self.process_file(filepath):
                processed += 1
        
        logging.info(f"本次处理完成: {processed}/{len(files)}")
        return processed


# ============================================================================
# 主程序
# ============================================================================

def setup_logging(debug: bool = False):
    """设置日志"""
    level = logging.DEBUG if debug else logging.INFO
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    
    # 文件处理器
    file_handler = logging.FileHandler('run.log', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    
    # 配置根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)


def main():
    parser = argparse.ArgumentParser(
        description='DC-DC PDF自动分类系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  # 持续监控模式
  python pdf_classifier.py --source ./pdfs --target ./classified
  
  # 单次运行
  python pdf_classifier.py --source ./pdfs --target ./classified --once
  
  # 调试模式（不移动文件）
  python pdf_classifier.py --source ./pdfs --target ./classified --dry-run --debug
        '''
    )
    
    parser.add_argument('--source', required=True, help='待分类PDF目录')
    parser.add_argument('--target', required=True, help='分类后目标目录')
    parser.add_argument('--scan-interval', type=int, default=30,
                        help='扫描间隔（秒），默认30')
    parser.add_argument('--head-pages', type=int, default=3,
                        help='抽取前N页文本，默认3')
    parser.add_argument('--min-stable-seconds', type=int, default=10,
                        help='文件稳定检测时间（秒），默认10')
    parser.add_argument('--mode', choices=['move', 'copy'], default='move',
                        help='文件操作模式，默认move')
    parser.add_argument('--dry-run', action='store_true',
                        help='试运行模式（不实际移动文件）')
    parser.add_argument('--debug', action='store_true',
                        help='调试模式（详细日志）')
    parser.add_argument('--once', action='store_true',
                        help='只运行一次扫描后退出')
    parser.add_argument('--reprocess', action='store_true',
                        help='重新处理所有文件（忽略历史记录）')
    
    args = parser.parse_args()
    
    # 设置日志
    setup_logging(args.debug)
    
    # 验证目录
    source_dir = Path(args.source)
    target_dir = Path(args.target)
    
    if not source_dir.exists():
        logging.error(f"源目录不存在: {source_dir}")
        sys.exit(1)
    
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # 初始化数据库
    db_path = Path('processed_files.db')
    if args.reprocess and db_path.exists():
        logging.warning("--reprocess: 删除旧数据库")
        db_path.unlink()
    
    db = ProcessedFilesDB(db_path)
    
    # 元数据文件
    metadata_file = Path('metadata.jsonl')
    
    # 创建分类器
    classifier = PDFClassifier(
        source_dir=source_dir,
        target_dir=target_dir,
        db=db,
        metadata_file=metadata_file,
        head_pages=args.head_pages,
        mode=args.mode,
        dry_run=args.dry_run
    )
    
    # 运行
    logging.info("=" * 60)
    logging.info("DC-DC PDF 自动分类系统启动")
    logging.info(f"源目录: {source_dir}")
    logging.info(f"目标目录: {target_dir}")
    logging.info(f"模式: {args.mode}")
    logging.info(f"试运行: {args.dry_run}")
    logging.info("=" * 60)
    
    try:
        if args.once:
            classifier.run_once(args.min_stable_seconds)
            logging.info("单次运行完成")
        else:
            logging.info(f"进入持续监控模式（扫描间隔: {args.scan_interval}秒）")
            logging.info("按 Ctrl+C 停止")
            
            while True:
                try:
                    classifier.run_once(args.min_stable_seconds)
                    time.sleep(args.scan_interval)
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    logging.error(f"处理循环异常: {e}", exc_info=True)
                    logging.info(f"等待 {args.scan_interval} 秒后继续...")
                    time.sleep(args.scan_interval)
    
    except KeyboardInterrupt:
        logging.info("\n收到停止信号，正在退出...")
    finally:
        db.close()
        logging.info("程序已退出")


if __name__ == '__main__':
    main()
