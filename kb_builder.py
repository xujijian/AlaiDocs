#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识库构建器 — 从分类好的 PDF 构建 SQLite FTS5 + FAISS 向量索引

用法:
  # 作为模块被 alaidocs.py 调用
  from kb_builder import build_kb
  stats = build_kb(classified_dir, kb_dir)

  # 也可独立运行
  python kb_builder.py --source data/classified --output data/kb
"""

import logging
import re
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger("kb_builder")

# PDF 文本提取
try:
    from pypdf import PdfReader
    PDF_AVAILABLE = True
except ImportError:
    try:
        from PyPDF2 import PdfReader
        PDF_AVAILABLE = True
    except ImportError:
        PDF_AVAILABLE = False

# FAISS + SentenceTransformer (可选)
try:
    import faiss
    from sentence_transformers import SentenceTransformer
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

# ──────────────────────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────────────────────

CHUNK_SIZE = 500        # 每块字符数
CHUNK_OVERLAP = 50      # 块间重叠字符
MAX_PAGES = 50          # 每篇 PDF 最大抽取页数
EMBED_MODEL = "all-MiniLM-L6-v2"
BATCH_SIZE = 64         # 嵌入向量批量编码大小

# ──────────────────────────────────────────────────────────────
# PDF 文本提取
# ──────────────────────────────────────────────────────────────

def extract_full_text(filepath: Path, max_pages: int = MAX_PAGES) -> Tuple[str, int]:
    """提取 PDF 全文"""
    if not PDF_AVAILABLE:
        logger.warning("pypdf / PyPDF2 未安装，跳过文本提取")
        return "", 0
    try:
        reader = PdfReader(str(filepath))
        page_count = len(reader.pages)
        pages_to_read = min(max_pages, page_count)
        texts = []
        for i in range(pages_to_read):
            page_text = reader.pages[i].extract_text()
            if page_text:
                # 清理 Unicode surrogates (某些 PDF 字体映射会产生)
                page_text = page_text.encode("utf-8", errors="replace").decode("utf-8")
                texts.append(page_text)
        return "\n".join(texts), page_count
    except Exception as e:
        logger.debug(f"PDF 提取失败 {filepath.name}: {e}")
        return "", 0


def extract_title(text: str, filename: str) -> str:
    """从文本首行或文件名猜测文档标题"""
    # 优先用文本第一行（去掉垃圾字符后）
    if text:
        for line in text.split("\n"):
            line = line.strip()
            # 跳过太短或纯数字/日期行
            if len(line) > 5 and not re.match(r'^[\d\s/\-\.]+$', line):
                return line[:200]
    # 回退：用文件名
    return Path(filename).stem.replace("_", " ").replace("-", " ")[:200]


# ──────────────────────────────────────────────────────────────
# 文本分块
# ──────────────────────────────────────────────────────────────

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE,
               overlap: int = CHUNK_OVERLAP) -> List[Dict]:
    """将文本按固定窗口切分为多个 chunk"""
    if not text or not text.strip():
        return []
    # 按段落先切，再合并到目标大小
    paragraphs = re.split(r'\n\s*\n', text)
    chunks = []
    current = ""
    page_est = 0  # 粗略的页码估计

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) + 1 <= chunk_size:
            current = (current + "\n" + para).strip()
        else:
            if current:
                chunks.append({"text": current, "page_start": page_est})
            # 如果单个段落就超过 chunk_size，强制切分
            if len(para) > chunk_size:
                for start in range(0, len(para), chunk_size - overlap):
                    piece = para[start:start + chunk_size]
                    chunks.append({"text": piece, "page_start": page_est})
            else:
                current = para
                continue
            current = ""
        # 粗略估计页码（每 3000 字符约 1 页）
        page_est = len(text[:text.find(para) + len(para)]) // 3000

    if current:
        chunks.append({"text": current, "page_start": page_est})

    return chunks


# ──────────────────────────────────────────────────────────────
# 路径解析 → 元数据
# ──────────────────────────────────────────────────────────────

def parse_path_metadata(rel_path: str) -> Dict[str, str]:
    """
    从分类目录的相对路径解析厂商 / 文档类型。
    约定层级:  <vendor>/<doc_type>/<topic>/<topology>/file.pdf
    至少需要 vendor 和 doc_type 两级。
    """
    parts = Path(rel_path).parts
    vendor   = parts[0] if len(parts) > 1 else "unknown"
    doc_type = parts[1] if len(parts) > 2 else "general"
    return {"vendor": vendor, "doc_type": doc_type}


# ──────────────────────────────────────────────────────────────
# SQLite 建表
# ──────────────────────────────────────────────────────────────

def create_schema(conn: sqlite3.Connection):
    """创建知识库表结构 (documents / chunks / chunks_fts / embeddings)"""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            doc_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            path     TEXT UNIQUE,
            vendor   TEXT,
            doc_type TEXT,
            title    TEXT
        );

        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id      INTEGER REFERENCES documents(doc_id),
            text        TEXT,
            page_start  INTEGER
        );

        CREATE TABLE IF NOT EXISTS embeddings (
            chunk_id    INTEGER REFERENCES chunks(chunk_id),
            vector_id   INTEGER
        );
    """)

    # FTS5 虚拟表（独立存储，不依赖 content sync）
    try:
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
            USING fts5(text, chunk_id UNINDEXED)
        """)
    except sqlite3.OperationalError:
        pass  # 已存在

    conn.commit()


# ──────────────────────────────────────────────────────────────
# 核心：构建知识库
# ──────────────────────────────────────────────────────────────

def build_kb(classified_dir: Path, kb_dir: Path,
             rebuild: bool = False,
             build_faiss: bool = True,
             progress_callback=None) -> Dict:
    """
    从分类完成的 PDF 目录构建 / 增量更新知识库。

    Args:
        classified_dir: 分类后的 PDF 根目录
        kb_dir:         知识库输出目录
        rebuild:        True = 清空重建；False = 增量追加
        build_faiss:    是否构建 FAISS 向量索引
        progress_callback: 进度回调 fn(current, total, msg)

    Returns:
        {"docs_added": N, "chunks_added": N, "faiss_vectors": N, "skipped": N, "errors": N}
    """
    kb_dir.mkdir(parents=True, exist_ok=True)
    db_path    = kb_dir / "kb.sqlite"
    faiss_path = kb_dir / "kb.faiss"

    stats = {"docs_added": 0, "chunks_added": 0,
             "faiss_vectors": 0, "skipped": 0, "errors": 0}

    if rebuild and db_path.exists():
        db_path.unlink()
        if faiss_path.exists():
            faiss_path.unlink()
        logger.info("🗑️  已清空旧知识库")

    conn = sqlite3.connect(str(db_path))
    create_schema(conn)

    # 收集已有文档路径（增量去重）
    existing_paths = set()
    if not rebuild:
        cursor = conn.execute("SELECT path FROM documents")
        existing_paths = {row[0] for row in cursor.fetchall()}

    # 扫描所有 PDF
    all_pdfs = sorted(classified_dir.rglob("*.pdf"))
    logger.info(f"📂 扫描到 {len(all_pdfs)} 个 PDF")

    all_chunk_texts = []  # 用于最后批量编码向量
    chunk_id_list = []    # 对应的 chunk_id

    for i, pdf in enumerate(all_pdfs):
        rel_path = pdf.relative_to(classified_dir).as_posix()

        if rel_path in existing_paths:
            stats["skipped"] += 1
            continue

        if progress_callback:
            progress_callback(i + 1, len(all_pdfs), pdf.name)

        # 提取文本
        text, page_count = extract_full_text(pdf)
        if not text or len(text.strip()) < 50:
            stats["errors"] += 1
            logger.debug(f"  跳过 (文本过短): {rel_path}")
            continue

        # 元数据
        meta = parse_path_metadata(rel_path)
        title = extract_title(text, pdf.name)

        # 分块
        chunks = chunk_text(text)
        if not chunks:
            stats["errors"] += 1
            continue

        try:
            # 插入 document
            cursor = conn.execute(
                "INSERT INTO documents (path, vendor, doc_type, title) VALUES (?, ?, ?, ?)",
                (rel_path, meta["vendor"], meta["doc_type"], title)
            )
            doc_id = cursor.lastrowid

            # 插入 chunks + FTS
            for chunk in chunks:
                c2 = conn.execute(
                    "INSERT INTO chunks (doc_id, text, page_start) VALUES (?, ?, ?)",
                    (doc_id, chunk["text"], chunk["page_start"])
                )
                cid = c2.lastrowid

                # 同步到 FTS5
                conn.execute(
                    "INSERT INTO chunks_fts (rowid, text, chunk_id) VALUES (?, ?, ?)",
                    (cid, chunk["text"], cid)
                )

                all_chunk_texts.append(chunk["text"])
                chunk_id_list.append(cid)
                stats["chunks_added"] += 1

            stats["docs_added"] += 1

            # 每 50 篇 commit 一次
            if stats["docs_added"] % 50 == 0:
                conn.commit()
                logger.info(f"  进度: {i+1}/{len(all_pdfs)} — "
                            f"已添加 {stats['docs_added']} 篇, "
                            f"{stats['chunks_added']} 块")

        except sqlite3.IntegrityError:
            stats["skipped"] += 1
        except Exception as e:
            stats["errors"] += 1
            logger.warning(f"  ❌ {rel_path}: {e}")

    conn.commit()
    logger.info(f"✅ SQLite + FTS5 构建完成: "
                f"{stats['docs_added']} 篇, {stats['chunks_added']} 块")

    # ── FAISS 向量索引 ──
    if build_faiss and FAISS_AVAILABLE and all_chunk_texts:
        logger.info(f"🧠 构建 FAISS 向量索引 ({len(all_chunk_texts)} 块)...")
        try:
            model = SentenceTransformer(EMBED_MODEL)
            dim = model.get_sentence_embedding_dimension()

            # 如果是增量且已有索引，先加载
            if not rebuild and faiss_path.exists():
                index = faiss.read_index(str(faiss_path))
                next_vid = index.ntotal
            else:
                index = faiss.IndexFlatIP(dim)  # 内积（余弦相似度）
                next_vid = 0

            # 分批编码
            for batch_start in range(0, len(all_chunk_texts), BATCH_SIZE):
                batch_end = min(batch_start + BATCH_SIZE, len(all_chunk_texts))
                batch_texts = all_chunk_texts[batch_start:batch_end]
                batch_cids  = chunk_id_list[batch_start:batch_end]

                vecs = model.encode(batch_texts, show_progress_bar=False,
                                    normalize_embeddings=True)
                vecs = vecs.astype("float32")
                index.add(vecs)

                # 写 embeddings 映射
                for j, cid in enumerate(batch_cids):
                    vid = next_vid + j
                    conn.execute(
                        "INSERT INTO embeddings (chunk_id, vector_id) VALUES (?, ?)",
                        (cid, vid)
                    )
                next_vid += len(batch_cids)
                stats["faiss_vectors"] += len(batch_cids)

                if batch_end % (BATCH_SIZE * 4) == 0 or batch_end == len(all_chunk_texts):
                    logger.info(f"  向量进度: {batch_end}/{len(all_chunk_texts)}")

            conn.commit()
            faiss.write_index(index, str(faiss_path))
            logger.info(f"✅ FAISS 索引已保存: {faiss_path} "
                        f"({index.ntotal} 向量, {faiss_path.stat().st_size/(1024**2):.1f} MB)")

        except Exception as e:
            logger.error(f"⚠️  FAISS 构建失败 (FTS5 仍可用): {e}")
    elif not FAISS_AVAILABLE:
        logger.info("ℹ️  FAISS 未安装，仅使用 FTS5 关键词检索")
        logger.info("   安装: pip install sentence-transformers faiss-cpu")

    conn.close()
    return stats


# ──────────────────────────────────────────────────────────────
# 修复：从已有 chunks 表重建 FTS5 索引
# ──────────────────────────────────────────────────────────────

def repair_fts(kb_dir: Path) -> Dict:
    """
    修复损坏的 FTS5 索引 — 从已有的 chunks 表重建。
    不需要重新提取 PDF，速度很快。

    Returns:
        {"chunks_indexed": N}
    """
    db_path = kb_dir / "kb.sqlite"
    if not db_path.exists():
        logger.error(f"❌ 知识库不存在: {db_path}")
        return {"chunks_indexed": 0}

    conn = sqlite3.connect(str(db_path))

    # 检查 chunks 表是否存在
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    if "chunks" not in tables:
        logger.error("❌ chunks 表不存在，需要完整重建: build-kb --rebuild")
        conn.close()
        return {"chunks_indexed": 0}

    # 删除旧的 FTS5 虚拟表 + 所有 shadow 表（彻底清理）
    shadow_tables = [
        "chunks_fts", "chunks_fts_data", "chunks_fts_idx",
        "chunks_fts_content", "chunks_fts_docsize", "chunks_fts_config",
    ]
    for tbl in shadow_tables:
        try:
            conn.execute(f"DROP TABLE IF EXISTS {tbl}")
        except sqlite3.DatabaseError:
            pass
    conn.commit()
    logger.info("🗑️  已删除旧 FTS5 索引及 shadow 表")

    # 重新创建 FTS5 虚拟表（独立存储，不用 content sync）
    conn.execute("""
        CREATE VIRTUAL TABLE chunks_fts
        USING fts5(text, chunk_id UNINDEXED)
    """)
    conn.commit()
    logger.info("✅ 已创建新 FTS5 虚拟表")

    # 从 chunks 表填充 FTS5
    total = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    logger.info(f"📝 正在索引 {total} 个分块...")

    batch_size = 5000
    indexed = 0
    errors = 0
    cursor = conn.execute("SELECT chunk_id, text FROM chunks ORDER BY chunk_id")

    while True:
        rows = cursor.fetchmany(batch_size)
        if not rows:
            break
        for cid, text in rows:
            if not text:
                errors += 1
                continue
            try:
                conn.execute(
                    "INSERT INTO chunks_fts (text, chunk_id) VALUES (?, ?)",
                    (text, cid)
                )
                indexed += 1
            except Exception as e:
                errors += 1
                if errors <= 3:
                    logger.debug(f"  FTS INSERT 失败 chunk_id={cid}: {e}")
        conn.commit()
        total_processed = indexed + errors
        if total_processed % 10000 < batch_size or total_processed >= total:
            logger.info(f"  进度: {total_processed}/{total} (成功 {indexed}, 失败 {errors})")

    logger.info(f"✅ FTS5 索引重建完成: {indexed} 个分块")
    conn.close()
    return {"chunks_indexed": indexed}


# ──────────────────────────────────────────────────────────────
# CLI 入口（独立运行）
# ──────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="AlaiDocs 知识库构建器")
    parser.add_argument("--source", type=Path, required=True,
                        help="分类后的 PDF 目录 (classified_dir)")
    parser.add_argument("--output", type=Path, required=True,
                        help="知识库输出目录 (kb_dir)")
    parser.add_argument("--rebuild", action="store_true",
                        help="清空重建（默认增量）")
    parser.add_argument("--no-faiss", action="store_true",
                        help="跳过 FAISS 向量索引")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s │ %(message)s", datefmt="%H:%M:%S"
    )

    if not args.source.exists():
        logger.error(f"❌ 源目录不存在: {args.source}")
        sys.exit(1)

    def progress(cur, total, name):
        if cur % 20 == 0 or cur == total:
            logger.info(f"  [{cur}/{total}] {name}")

    stats = build_kb(args.source, args.output,
                     rebuild=args.rebuild,
                     build_faiss=not args.no_faiss,
                     progress_callback=progress)

    print(f"\n{'═'*50}")
    print(f"  📊 构建完成")
    print(f"     新增文档:  {stats['docs_added']}")
    print(f"     新增分块:  {stats['chunks_added']}")
    print(f"     FAISS向量: {stats['faiss_vectors']}")
    print(f"     跳过:      {stats['skipped']}")
    print(f"     错误:      {stats['errors']}")
    print(f"{'═'*50}")


if __name__ == "__main__":
    main()
