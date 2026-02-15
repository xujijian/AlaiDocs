#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AlaiDocs — DC-DC 知识库一站式 CLI
让每个人都能用一句话建立专业的 DC-DC 技术知识库。

用法:
  python alaidocs.py init                  # 首次初始化 (创建目录+配置)
  python alaidocs.py                       # 交互模式
  python alaidocs.py collect               # 一键采集
  python alaidocs.py classify              # 自动 4D 分类
  python alaidocs.py pack "降压变换器热管理" # 检索打包
  python alaidocs.py run "GaN效率优化"     # 全流程: 采集→分类→打包
  python alaidocs.py status                # 系统状态

版本: 3.1.0 (portable — 无硬编码路径)
"""

import argparse
import json
import logging
import os
import shutil
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# ============================================================================
# 路径约定 — 全部相对于项目根目录，零硬编码
# ============================================================================

PROJECT_ROOT = Path(__file__).resolve().parent

# 默认目录结构 (全部可通过 alaidocs_config.json 覆盖)
DEFAULT_DIRS = {
    "download_dir":   "data/downloads",       # 下载缓冲区
    "classified_dir": "data/classified",       # 4D 分类归档
    "kb_dir":         "data/kb",               # 知识库 (SQLite + FAISS)
    "pack_output":    "data/packed",           # NotebookLM 打包输出
    "keywords_db":    "data/keywords.json",    # 关键词数据库
}

USER_CONFIG_FILE = PROJECT_ROOT / "alaidocs_config.json"
TEMPLATE_CONFIG  = PROJECT_ROOT / "integrated_config.json"

BANNER = r"""
╔══════════════════════════════════════════════════════════════╗
║           AlaiDocs — DC-DC 知识库自动化系统                  ║
║   Collect → Classify (4D) → Pack → NotebookLM              ║
╚══════════════════════════════════════════════════════════════╝
"""

HELP_TEXT = """
  可用命令:
  ──────────────────────────────────────────────────────────────
  init                 首次初始化 (创建目录和配置文件)
  collect              一键采集 (Gemini → DuckDuckGo → PDF)
  classify             自动整理 (4D 分类归档)
  pack <查询>          检索打包 (高置信度筛选 → NotebookLM)
  run  <查询>          全流程   (采集 → 分类 → 打包)
  status               系统状态摘要
  config               显示当前配置
  help                 显示帮助
  quit / exit          退出
  ──────────────────────────────────────────────────────────────

  pack 参数:
    pack <查询> [--top N] [--min-score 0.5]
    例: pack 降压变换器热管理 --top 15 --min-score 0.6
"""


# ============================================================================
# 配置管理 — 首次运行自动生成用户配置
# ============================================================================

def resolve_paths(config: Dict) -> Dict[str, Path]:
    """
    从配置解析所有路径 (相对路径基于 PROJECT_ROOT)。
    优先级: alaidocs_config.json > integrated_config.json > 内置默认值
    """
    paths_cfg = config.get("paths", {})
    resolved = {}
    for key, default_rel in DEFAULT_DIRS.items():
        raw = paths_cfg.get(key, default_rel)
        p = Path(raw)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        resolved[key] = p
    # 派生路径
    resolved["kb_db"]    = resolved["kb_dir"] / "kb.sqlite"
    resolved["kb_faiss"] = resolved["kb_dir"] / "kb.faiss"
    return resolved


def load_config(config_path: Path = None) -> Dict:
    """
    加载配置。合并链:
    内置默认 → integrated_config.json → alaidocs_config.json → CLI 参数
    """
    config = {}

    # 1) integrated_config.json (项目级模板，入 Git)
    if TEMPLATE_CONFIG.exists():
        with open(TEMPLATE_CONFIG, "r", encoding="utf-8-sig") as f:
            config = json.load(f)

    # 2) alaidocs_config.json (用户级覆盖，不入 Git)
    user_cfg_path = config_path or USER_CONFIG_FILE
    if user_cfg_path.exists():
        with open(user_cfg_path, "r", encoding="utf-8-sig") as f:
            user_cfg = json.load(f)
        _deep_merge(config, user_cfg)

    return config


def _deep_merge(base: dict, override: dict):
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


def ensure_initialized(paths: Dict[str, Path], logger: logging.Logger) -> bool:
    """检查是否已初始化；未初始化则引导用户。"""
    if paths["classified_dir"].exists() and paths["kb_dir"].exists():
        return True
    logger.warning("⚠️  项目尚未初始化。请先运行:")
    logger.warning("   python alaidocs.py init")
    return False


# ============================================================================
# 日志
# ============================================================================

def setup_logging(debug: bool = False) -> logging.Logger:
    level = logging.DEBUG if debug else logging.INFO
    root = logging.getLogger()
    for h in root.handlers[:]:
        root.removeHandler(h)

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(logging.Formatter(
        "%(asctime)s │ %(message)s", datefmt="%H:%M:%S"
    ))

    log_file = PROJECT_ROOT / "alaidocs.log"
    fh = logging.FileHandler(str(log_file), encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
    ))

    root.setLevel(logging.DEBUG)
    root.addHandler(console)
    root.addHandler(fh)
    return logging.getLogger("alaidocs")


# ============================================================================
# 命令: init
# ============================================================================

def cmd_init(config: Dict, logger: logging.Logger):
    """首次初始化: 创建目录结构 + 生成用户配置文件"""
    print(BANNER)
    print("  🔧 正在初始化 AlaiDocs 项目...\n")

    paths = resolve_paths(config)

    # 1) 创建目录
    for name, p in paths.items():
        if name.endswith("_db") or name.endswith("_faiss") or name == "keywords_db":
            p.parent.mkdir(parents=True, exist_ok=True)
        else:
            p.mkdir(parents=True, exist_ok=True)
        print(f"  ✅ {name:20s} → {p}")

    # 2) 生成 alaidocs_config.json
    if not USER_CONFIG_FILE.exists():
        try:
            rel_paths = {
                k: str(v.relative_to(PROJECT_ROOT)).replace("\\", "/")
                for k, v in paths.items()
                if k in DEFAULT_DIRS
            }
        except ValueError:
            rel_paths = {k: str(v) for k, v in paths.items() if k in DEFAULT_DIRS}

        user_config = {
            "_comment": [
                "AlaiDocs 用户配置 — 此文件不入 Git",
                "编辑 paths 自定义目录，也可使用绝对路径"
            ],
            "paths": rel_paths,
        }
        with open(USER_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(user_config, f, indent=2, ensure_ascii=False)
        print(f"\n  📝 已生成用户配置: {USER_CONFIG_FILE.name}")
    else:
        print(f"\n  📝 用户配置已存在: {USER_CONFIG_FILE.name}")

    # 3) 初始化空关键词库
    kw_path = paths["keywords_db"]
    if not kw_path.exists():
        with open(kw_path, "w", encoding="utf-8") as f:
            json.dump({
                "keywords": {},
                "statistics": {
                    "total_keywords_used": 0,
                    "total_searches": 0,
                    "total_files_downloaded": 0,
                    "last_updated": None,
                },
            }, f, indent=2, ensure_ascii=False)
        print(f"  📝 已创建关键词库: {kw_path.name}")

    # 4) 更新 .gitignore
    gitignore = PROJECT_ROOT / ".gitignore"
    needed = [
        "alaidocs_config.json",
        "alaidocs.log",
        "data/",
        "*.db",
        "__pycache__/",
        ".venv/",
    ]
    existing = set()
    if gitignore.exists():
        existing = set(gitignore.read_text(encoding="utf-8").splitlines())
    missing = [e for e in needed if e not in existing]
    if missing:
        with open(gitignore, "a", encoding="utf-8") as f:
            f.write("\n# AlaiDocs runtime (auto-generated)\n")
            for e in missing:
                f.write(e + "\n")
        print(f"  📝 已更新 .gitignore")

    print(f"""
  ──────────────────────────────────────────────────────────────
  ✅ 初始化完成！下一步:

  1. 安装依赖:
     pip install -r requirements.txt

  2. (浏览器采集需要) 额外安装:
     pip install -r requirements_browser.txt

  3. 启动:
     python alaidocs.py              # 交互模式
     python alaidocs.py collect      # 开始采集
     python alaidocs.py status       # 查看状态

  4. (可选) 编辑 alaidocs_config.json 自定义路径
     例如指向已有的 PDF 目录或知识库

  目录结构:
     data/
     ├── downloads/       # 采集缓冲区
     ├── classified/      # 4D 分类归档
     │   └── TI/datasheet/power_ic/buck/xxx.pdf
     ├── kb/              # 知识库
     │   ├── kb.sqlite
     │   └── kb.faiss
     ├── packed/          # NotebookLM 打包
     └── keywords.json    # 关键词库
  ──────────────────────────────────────────────────────────────
""")


# ============================================================================
# 命令: collect
# ============================================================================

def cmd_collect(config: Dict, paths: Dict[str, Path],
                logger: logging.Logger, rounds: int = 0):
    """一键采集: Gemini 关键词 → DuckDuckGo 搜索 → PDF 下载"""
    logger.info("🚀 启动一键采集系统")
    logger.info(f"   下载目录: {paths['download_dir']}")
    logger.info(f"   关键词库: {paths['keywords_db']}")

    try:
        from integrated_searcher import IntegratedSearcher
    except ImportError as e:
        logger.error(f"❌ 导入失败: {e}")
        logger.error("   pip install -r requirements.txt")
        logger.error("   pip install -r requirements_browser.txt")
        return False

    searcher_config = config.copy()
    if rounds > 0:
        searcher_config["max_rounds"] = rounds

    searcher = IntegratedSearcher(
        output_dir=paths["download_dir"],
        keyword_db_path=paths["keywords_db"],
        use_browser=True,
        config=searcher_config,
        logger=logger,
    )
    searcher.run()

    stats = searcher._count_downloaded_files()
    logger.info(f"\n📊 采集完成: {stats['files_downloaded']} 个文件, "
                f"{stats['total_size'] / (1024**3):.2f} GB")
    return True


# ============================================================================
# 命令: classify
# ============================================================================

def cmd_classify(config: Dict, paths: Dict[str, Path],
                 logger: logging.Logger, once: bool = True) -> Dict:
    """自动整理: 4D 分类 (厂商/类型/主题/拓扑)"""
    logger.info("🗂️  启动 4D 自动分类系统")
    logger.info(f"   源目录:   {paths['download_dir']}")
    logger.info(f"   目标目录: {paths['classified_dir']}")

    source_dir = paths["download_dir"]
    target_dir = paths["classified_dir"]
    stats = {"total": 0, "success": 0, "failed": 0, "skipped": 0}

    if not source_dir.exists():
        logger.warning(f"⚠️  源目录不存在: {source_dir}")
        return stats

    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        from pdf_classifier import PDFClassifier, ProcessedFilesDB, is_file_stable
    except ImportError as e:
        logger.error(f"❌ 导入失败: {e}")
        return stats

    db_path = PROJECT_ROOT / "classified_files.db"
    db = ProcessedFilesDB(db_path)
    metadata_file = target_dir / "metadata.jsonl"
    head_pages = config.get("classifier", {}).get("head_pages", 3)
    min_stable = config.get("classifier", {}).get("min_stable_seconds", 15)

    classifier = PDFClassifier(
        source_dir=source_dir,
        target_dir=target_dir,
        db=db,
        metadata_file=metadata_file,
        head_pages=head_pages,
        mode="move",
        dry_run=False,
    )

    files = classifier.scan_new_files()
    logger.info(f"📋 发现 {len(files)} 个待分类 PDF")
    stats["total"] = len(files)

    for i, pdf_file in enumerate(files, 1):
        try:
            if not is_file_stable(pdf_file, checks=2, min_stable_seconds=min_stable):
                stats["skipped"] += 1
                continue
            result = classifier.process_file(pdf_file)
            if result:
                stats["success"] += 1
            else:
                stats["skipped"] += 1
            if i % 10 == 0 or i == len(files):
                logger.info(f"  进度: {i}/{len(files)} "
                            f"(✅{stats['success']} ❌{stats['failed']} ⏭️{stats['skipped']})")
        except Exception as e:
            stats["failed"] += 1
            logger.error(f"  ❌ {pdf_file.name}: {e}")

    db.close()
    logger.info(f"\n📊 分类完成: 总计 {stats['total']} | 成功 {stats['success']} | "
                f"失败 {stats['failed']} | 跳过 {stats['skipped']}")
    return stats


# ============================================================================
# 命令: pack — 高置信度筛选
# ============================================================================

def cmd_pack(query: str, config: Dict, paths: Dict[str, Path],
             logger: logging.Logger, max_docs: int = 20,
             min_score: float = 0.0, auto_confirm: bool = False
             ) -> Optional[Path]:
    """对话打包: 混合检索 → 高置信度筛选 → NotebookLM Source"""
    logger.info(f"🔎 检索打包: \"{query}\"")
    logger.info(f"   参数: top={max_docs}, min_score={min_score}")

    kb_path    = paths["kb_db"]
    faiss_path = paths["kb_faiss"]
    base_dir   = paths["classified_dir"]
    base_output = paths["pack_output"]

    if not kb_path.exists():
        logger.error(f"❌ 知识库不存在: {kb_path}")
        logger.error("   请先运行 collect + classify 构建知识库，")
        logger.error("   或编辑 alaidocs_config.json 指向已有知识库。")
        return None

    try:
        from smart_pack import (
            hybrid_search, select_diverse_docs, pack_files,
            detect_language, make_slug,
        )
    except ImportError as e:
        logger.error(f"❌ 导入失败: {e}")
        logger.error("   pip install sentence-transformers faiss-cpu deep-translator")
        return None

    results = hybrid_search(query, kb_path, faiss_path, top_k=100)
    if not results:
        logger.warning("❌ 未找到相关文档")
        return None

    logger.info(f"✅ 检索到 {len(results)} 个候选文档")

    if min_score > 0:
        before = len(results)
        results = [r for r in results if r["score"] >= min_score]
        logger.info(f"🎯 置信度筛选 (≥{min_score}): {before} → {len(results)}")

    if not results:
        logger.warning(f"⚠️  没有文档达到置信度 {min_score}")
        return None

    selected = select_diverse_docs(results, max_docs=max_docs)

    # 分层展示
    high = [d for d in selected if d["score"] > 0.7]
    mid  = [d for d in selected if 0.4 <= d["score"] <= 0.7]
    low  = [d for d in selected if d["score"] < 0.4]
    icons = {"fts5": "🔤", "faiss": "🧠", "hybrid": "⚡"}
    idx = 1

    print(f"\n{'═'*70}")
    print(f"  📦 智能选择了 {len(selected)} 个文档")
    print(f"{'═'*70}")

    for label, group in [("🔥 高相关度", high), ("📌 中等相关度", mid), ("💡 参考文档", low)]:
        if group:
            print(f"\n  {label} ({len(group)} 个):")
            for doc in group:
                ic = icons.get(doc["method"], "?")
                print(f"  {idx:2d}. [{doc['score']:.3f}] {ic} "
                      f"{doc['vendor']}/{doc['doc_type']} — {doc.get('title', '')[:55]}")
                idx += 1

    vendors_hit = sorted(set(d["vendor"] for d in selected))
    types_hit   = sorted(set(d["doc_type"] for d in selected))
    avg_score   = sum(d["score"] for d in selected) / len(selected)

    print(f"\n{'─'*70}")
    print(f"  📊 覆盖 {len(vendors_hit)} 厂商: {', '.join(vendors_hit)}")
    print(f"  📊 文档类型: {', '.join(types_hit)}")
    print(f"  📊 平均置信度: {avg_score:.3f}")
    print(f"  📊 图例: 🔤=关键词  🧠=语义  ⚡=混合验证")
    print(f"{'═'*70}")

    if not auto_confirm:
        confirm = input(f"\n  打包这 {len(selected)} 个文件? (Y/n): ").strip().lower()
        if confirm and confirm != "y":
            logger.info("❌ 已取消")
            return None

    lang = detect_language(query)
    date_str = datetime.now().strftime("%Y-%m-%d")
    slug = make_slug(query)
    output_dir = base_output / date_str / slug
    if output_dir.exists():
        shutil.rmtree(output_dir)

    logger.info("📦 打包中...")
    packed = pack_files(selected, base_dir, output_dir)
    _write_manifest(output_dir, query, selected, packed, lang)

    logger.info(f"\n✅ 成功打包 {len(packed)} 个文件")
    logger.info(f"📁 输出目录: {output_dir.absolute()}")
    print(f"\n  💡 下一步: 打开 NotebookLM → 上传 {output_dir.absolute()} 中所有文件")
    return output_dir


def _write_manifest(output_dir, query, selected, packed, lang):
    manifest = output_dir / "manifest.txt"
    with open(manifest, "w", encoding="utf-8") as f:
        f.write(f"AlaiDocs 智能打包清单\n{'='*70}\n")
        f.write(f"查询: {query}\n")
        f.write(f"语言: {'中文' if lang == 'zh' else '英文'}\n")
        f.write(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"方法: FTS5 关键词 + FAISS 语义 (加权融合)\n")
        f.write(f"数量: {len(packed)}\n{'='*70}\n\n")
        for label, pred in [("高相关度", lambda s: s > 0.7),
                            ("中等相关度", lambda s: 0.4 <= s <= 0.7),
                            ("参考文档", lambda s: s < 0.4)]:
            group = [(i, d) for i, d in enumerate(selected, 1) if pred(d["score"])]
            if group:
                f.write(f"【{label}】\n\n")
                for i, doc in group:
                    f.write(f"{i:2d}. {doc.get('title', 'N/A')}\n")
                    f.write(f"    厂商: {doc['vendor']} | 类型: {doc['doc_type']}\n")
                    f.write(f"    置信度: {doc['score']:.3f} | 方法: {doc['method']}\n\n")
        f.write(f"{'='*70}\n")


# ============================================================================
# 命令: run (全流程)
# ============================================================================

def cmd_run(query: str, config: Dict, paths: Dict[str, Path],
            logger: logging.Logger, rounds: int = 1,
            max_docs: int = 20, min_score: float = 0.0):
    """全流程: 采集 → 分类 → 打包"""
    header = f" 🚀 全流程: \"{query}\""
    logger.info(f"\n╔{'═'*68}╗")
    logger.info(f"║{header:<68s}║")
    logger.info(f"╚{'═'*68}╝\n")

    logger.info(f"{'━'*70}")
    logger.info("  Phase 1/3: 采集 (Gemini → DuckDuckGo → PDF)")
    logger.info(f"{'━'*70}")
    cmd_collect(config, paths, logger, rounds=rounds)

    logger.info(f"\n{'━'*70}")
    logger.info("  Phase 2/3: 4D 分类 (厂商/类型/主题/拓扑)")
    logger.info(f"{'━'*70}")
    cls = cmd_classify(config, paths, logger, once=True)

    logger.info(f"\n{'━'*70}")
    logger.info("  Phase 3/3: 高置信度检索打包")
    logger.info(f"{'━'*70}")
    output = cmd_pack(query, config, paths, logger,
                      max_docs=max_docs, min_score=min_score, auto_confirm=True)

    print(f"\n╔{'═'*68}╗")
    print(f"  ✅ 全流程完成 | 分类: {cls.get('success', 0)} 个")
    if output:
        print(f"  📁 打包: {output.absolute()}")
    print(f"╚{'═'*68}╝")


# ============================================================================
# 命令: status / config
# ============================================================================

def cmd_status(config: Dict, paths: Dict[str, Path], logger: logging.Logger):
    print(f"\n{'═'*70}")
    print("  AlaiDocs 系统状态")
    print(f"{'═'*70}\n")

    # 下载
    dl = paths["download_dir"]
    if dl.exists():
        pdfs = list(dl.rglob("*.pdf"))
        size = sum(f.stat().st_size for f in pdfs if f.is_file())
        vendors = sorted(d.name for d in dl.iterdir()
                         if d.is_dir() and not d.name.startswith(("_", ".")))
        print(f"  📥 下载缓冲区: {dl}")
        print(f"     PDF: {len(pdfs)} | {size/(1024**2):.1f} MB")
        print(f"     厂商: {', '.join(vendors) if vendors else '(空)'}")
    else:
        print(f"  📥 下载缓冲区: (未创建) — 运行 init")

    # 分类
    cls = paths["classified_dir"]
    if cls.exists():
        cp = list(cls.rglob("*.pdf"))
        cs = sum(f.stat().st_size for f in cp if f.is_file())
        cv = sorted(d.name for d in cls.iterdir()
                    if d.is_dir() and not d.name.startswith(("_", ".", "T")))
        print(f"\n  🗂️  分类归档: {cls}")
        print(f"     PDF: {len(cp)} | {cs/(1024**3):.2f} GB")
        print(f"     厂商 ({len(cv)}): {', '.join(cv[:12])}"
              f"{'...' if len(cv) > 12 else ''}")
    else:
        print(f"\n  🗂️  分类归档: (未创建)")

    # 知识库
    kb = paths["kb_db"]
    if kb.exists():
        try:
            conn = sqlite3.connect(f"file:{kb}?mode=ro", uri=True)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM documents")
            nd = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM chunks")
            nc = c.fetchone()[0]
            conn.close()
            print(f"\n  📚 知识库: {kb}")
            print(f"     文档: {nd} | 分块: {nc}")
        except Exception as e:
            print(f"\n  📚 知识库: 读取失败 ({e})")
    else:
        print(f"\n  📚 知识库: (未创建)")

    fi = paths["kb_faiss"]
    if fi.exists():
        print(f"  🧠 FAISS: {fi.stat().st_size/(1024**2):.1f} MB")
    else:
        print(f"  🧠 FAISS: (未创建)")

    kw = paths["keywords_db"]
    if kw.exists():
        try:
            kd = json.loads(kw.read_text(encoding="utf-8"))
            print(f"\n  🔑 关键词: {len(kd.get('keywords', {}))} 个, "
                  f"{kd.get('statistics', {}).get('total_searches', 0)} 次搜索")
        except Exception:
            print(f"\n  🔑 关键词库: 解析失败")
    else:
        print(f"\n  🔑 关键词库: (未创建)")

    po = paths["pack_output"]
    if po.exists() and po.is_dir():
        recent = sorted(d.name for d in po.iterdir() if d.is_dir())[-5:]
        print(f"\n  📦 打包输出: {po}")
        if recent:
            print(f"     最近: {', '.join(recent)}")

    dl_cfg = config.get("downloader", {})
    print(f"\n  ⚙️  配置:")
    print(f"     每轮关键词:   {dl_cfg.get('keywords_per_round', 10)}")
    print(f"     每词结果:     {dl_cfg.get('results_per_keyword', 20)}")
    print(f"     文件上限:     {dl_cfg.get('total_files_limit', 10000)}")
    print(f"     容量上限:     {dl_cfg.get('total_size_limit_gb', 100)} GB")
    print(f"     白名单域名:   {len(dl_cfg.get('domain_whitelist', []))} 个")
    print(f"\n{'═'*70}\n")


def cmd_config(config: Dict):
    print(f"\n{'═'*70}")
    print("  当前配置")
    print(f"{'═'*70}\n")
    print(json.dumps(config, indent=2, ensure_ascii=False))
    print(f"\n{'═'*70}\n")


# ============================================================================
# 交互模式 (REPL)
# ============================================================================

def interactive_mode(config: Dict, paths: Dict[str, Path],
                     logger: logging.Logger):
    print(BANNER)
    print(HELP_TEXT)

    while True:
        try:
            raw = input("\n  alaidocs> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  👋 再见!")
            break

        if not raw:
            continue

        parts = raw.split()
        cmd = parts[0].lower()
        rest = parts[1:]

        if cmd in ("quit", "exit", "q"):
            print("  👋 再见!")
            break
        elif cmd in ("help", "h", "?"):
            print(HELP_TEXT)
        elif cmd == "init":
            cmd_init(config, logger)
            # 重新加载路径
            paths.update(resolve_paths(load_config()))
        elif cmd == "collect":
            rounds = int(rest[0]) if rest and rest[0].isdigit() else 0
            cmd_collect(config, paths, logger, rounds=rounds)
        elif cmd == "classify":
            cmd_classify(config, paths, logger, once=True)
        elif cmd == "pack":
            q, top_n, ms = _parse_pack_args(rest)
            if q:
                cmd_pack(q, config, paths, logger, max_docs=top_n, min_score=ms)
            else:
                print("  ⚠️  用法: pack <查询> [--top N] [--min-score 0.5]")
        elif cmd == "run":
            q, top_n, ms, rds = _parse_run_args(rest)
            if q:
                cmd_run(q, config, paths, logger, rounds=rds,
                        max_docs=top_n, min_score=ms)
            else:
                print("  ⚠️  用法: run <查询> [--top N] [--min-score 0.5] [--rounds N]")
        elif cmd == "status":
            cmd_status(config, paths, logger)
        elif cmd == "config":
            cmd_config(config)
        elif "更新资料" in raw or "开始采集" in raw:
            cmd_collect(config, paths, logger)
        elif any(k in raw for k in ("检索", "搜索", "查找")):
            topic = raw
            for prefix in ("帮我检索", "检索", "搜索", "查找"):
                if raw.startswith(prefix):
                    topic = raw[len(prefix):].strip()
                    break
            if topic:
                cmd_pack(topic, config, paths, logger)
        elif "整理" in raw or "分类" in raw:
            cmd_classify(config, paths, logger, once=True)
        elif "状态" in raw:
            cmd_status(config, paths, logger)
        else:
            print(f"  💡 将 \"{raw}\" 作为检索查询...")
            cmd_pack(raw, config, paths, logger)


def _parse_pack_args(rest):
    parts, top, ms, i = [], 20, 0.0, 0
    while i < len(rest):
        if rest[i] == "--top" and i + 1 < len(rest):
            top = int(rest[i+1]); i += 2
        elif rest[i] == "--min-score" and i + 1 < len(rest):
            ms = float(rest[i+1]); i += 2
        else:
            parts.append(rest[i]); i += 1
    return " ".join(parts), top, ms


def _parse_run_args(rest):
    parts, top, ms, rds, i = [], 20, 0.0, 1, 0
    while i < len(rest):
        if rest[i] == "--top" and i + 1 < len(rest):
            top = int(rest[i+1]); i += 2
        elif rest[i] == "--min-score" and i + 1 < len(rest):
            ms = float(rest[i+1]); i += 2
        elif rest[i] == "--rounds" and i + 1 < len(rest):
            rds = int(rest[i+1]); i += 2
        else:
            parts.append(rest[i]); i += 1
    return " ".join(parts), top, ms, rds


# ============================================================================
# CLI 入口
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="AlaiDocs — DC-DC 知识库一站式 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python alaidocs.py init                           # 首次初始化
  python alaidocs.py                                # 交互模式
  python alaidocs.py collect                        # 一键采集
  python alaidocs.py classify                       # 自动分类
  python alaidocs.py pack "降压变换器热管理"         # 检索打包
  python alaidocs.py pack "GaN efficiency" --top 15 # 打包 15 篇
  python alaidocs.py run "LLC谐振变换器" --rounds 2 # 全流程
  python alaidocs.py status                         # 系统状态
        """,
    )

    sub = parser.add_subparsers(dest="command", help="子命令")

    sub.add_parser("init", help="首次初始化")

    sp = sub.add_parser("collect", help="一键采集")
    sp.add_argument("--rounds", type=int, default=0)

    sub.add_parser("classify", help="自动 4D 分类")

    sp = sub.add_parser("pack", help="检索打包")
    sp.add_argument("query")
    sp.add_argument("--top", type=int, default=20)
    sp.add_argument("--min-score", type=float, default=0.0)
    sp.add_argument("-y", "--yes", action="store_true")

    sp = sub.add_parser("run", help="全流程")
    sp.add_argument("query")
    sp.add_argument("--rounds", type=int, default=1)
    sp.add_argument("--top", type=int, default=20)
    sp.add_argument("--min-score", type=float, default=0.0)

    sub.add_parser("status", help="系统状态")
    sub.add_parser("config", help="显示配置")

    parser.add_argument("-c", "--config", type=Path, default=None)
    parser.add_argument("--debug", action="store_true")

    args = parser.parse_args()
    logger = setup_logging(args.debug)
    config = load_config(args.config)
    paths = resolve_paths(config)

    if args.command is None:
        interactive_mode(config, paths, logger)
    elif args.command == "init":
        cmd_init(config, logger)
    elif args.command == "collect":
        if not ensure_initialized(paths, logger):
            return
        cmd_collect(config, paths, logger, rounds=args.rounds)
    elif args.command == "classify":
        if not ensure_initialized(paths, logger):
            return
        cmd_classify(config, paths, logger, once=True)
    elif args.command == "pack":
        if not ensure_initialized(paths, logger):
            return
        cmd_pack(args.query, config, paths, logger,
                 max_docs=args.top, min_score=args.min_score,
                 auto_confirm=args.yes)
    elif args.command == "run":
        if not ensure_initialized(paths, logger):
            return
        cmd_run(args.query, config, paths, logger,
                rounds=args.rounds, max_docs=args.top,
                min_score=args.min_score)
    elif args.command == "status":
        cmd_status(config, paths, logger)
    elif args.command == "config":
        cmd_config(config)


if __name__ == "__main__":
    main()
