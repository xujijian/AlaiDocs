#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能文件打包器 - 自动检索、去重、打包PDF文件供NotebookLM使用
"""

import sys
import sqlite3
import numpy as np
import shutil
from pathlib import Path
from typing import List, Dict, Tuple
import re
from datetime import datetime

# 自动翻译
try:
    from deep_translator import GoogleTranslator
    TRANSLATOR_AVAILABLE = True
except ImportError:
    print("⚠️  未安装翻译库，将尝试直接检索...")
    print("   安装: pip install deep-translator")
    TRANSLATOR_AVAILABLE = False

# 向量检索
try:
    import faiss
    from sentence_transformers import SentenceTransformer
    FAISS_AVAILABLE = True
except ImportError:
    print("⚠️  FAISS未安装，仅使用关键词检索")
    FAISS_AVAILABLE = False

# 模块级缓存：SentenceTransformer 单例（惰性加载）
_cached_model = None

def get_sentence_transformer():
    """获取缓存的 SentenceTransformer 模型（单例模式）"""
    global _cached_model
    if _cached_model is None:
        _cached_model = SentenceTransformer('all-MiniLM-L6-v2')
    return _cached_model


def make_slug(text: str, max_length: int = 50) -> str:
    """将查询文本转换为安全的文件夹名"""
    # 只保留字母数字和中文
    slug = re.sub(r'[^\w\u4e00-\u9fff]+', '_', text)
    slug = slug.strip('_')
    if len(slug) > max_length:
        slug = slug[:max_length]
    return slug if slug else "query"


def detect_language(text: str) -> str:
    """检测文本语言（简单规则）"""
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    return 'zh' if chinese_chars > len(text) * 0.3 else 'en'


def translate_to_english(text: str) -> str:
    """翻译中文到英文"""
    if not TRANSLATOR_AVAILABLE:
        return text
    
    try:
        translator = GoogleTranslator(source='zh-CN', target='en')
        result = translator.translate(text)
        print(f"  🌐 翻译: {text} → {result}")
        return result
    except Exception as e:
        print(f"  ⚠️  翻译失败: {e}，使用原文")
        return text


def extract_keywords(query: str) -> List[str]:
    """提取查询关键词（含缩写展开和驼峰/连写拆分）"""
    import re
    # 移除常见停用词
    stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
                 'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
                 'within', 'options', 'selection', 'choose', 'comparison'}

    # DC-DC 领域常用缩写映射
    ABBREVIATIONS = {
        'bi': 'bidirectional',
        'bb': 'buck boost',
        'buckboost': 'buck boost',
        'bibuckboost': 'bidirectional buck boost',
        'dcdc': 'dc dc',
        'llc': 'llc resonant',
        'emi': 'electromagnetic interference',
        'emc': 'electromagnetic compatibility',
        'esd': 'electrostatic discharge',
        'pcb': 'printed circuit board',
        'gan': 'gallium nitride',
        'sic': 'silicon carbide',
        'mosfet': 'mosfet',
        'sepic': 'sepic',
        'smps': 'switched mode power supply',
        'pfc': 'power factor correction',
        'mppt': 'maximum power point tracking',
        'bms': 'battery management system',
    }

    # 先尝试整串缩写匹配
    query_lower = query.lower().strip()
    if query_lower in ABBREVIATIONS:
        expanded = ABBREVIATIONS[query_lower]
        words = re.findall(r'\w+', expanded)
        return [w for w in words if len(w) > 1]

    # 驼峰 / 连写拆分: "buckBoost" → "buck Boost", "bibuckboost" → 尝试子串匹配
    expanded_query = re.sub(r'([a-z])([A-Z])', r'\1 \2', query)  # camelCase
    # 按已知技术词拆分连写 (贪心匹配)
    KNOWN_TOKENS = sorted([
        'bidirectional', 'buck', 'boost', 'converter', 'inverting',
        'synchronous', 'resonant', 'isolated', 'flyback', 'forward',
        'half', 'bridge', 'full', 'phase', 'shifted', 'charge', 'pump',
        'sepic', 'cuk', 'zeta', 'llc', 'dab', 'controller', 'regulator',
        'driver', 'gate', 'mosfet', 'gan', 'sic', 'efficiency', 'thermal',
        'emi', 'emc', 'esd', 'pcb', 'layout', 'datasheet', 'design',
        'power', 'voltage', 'current', 'output', 'input', 'switching',
        'frequency', 'loop', 'compensation', 'feedback', 'control',
    ], key=len, reverse=True)

    def split_compound(word):
        """贪心拆分连写词: 'bibuckboost' → ['bi','buck','boost']"""
        result = []
        w = word.lower()
        while w:
            matched = False
            for token in KNOWN_TOKENS:
                if w.startswith(token):
                    result.append(token)
                    w = w[len(token):]
                    matched = True
                    break
            if not matched:
                # 没匹配到已知词，取整个剩余
                if w:
                    result.append(w)
                break
        return result

    # 分词
    words = re.findall(r'\w+', expanded_query.lower())

    # 对每个词尝试拆分 + 缩写展开
    all_keywords = []
    for w in words:
        if w in stopwords or len(w) < 2:
            continue
        # 缩写展开
        if w in ABBREVIATIONS:
            expanded_words = re.findall(r'\w+', ABBREVIATIONS[w])
            all_keywords.extend(expanded_words)
        # 长连写词拆分
        elif len(w) > 8:
            parts = split_compound(w)
            if len(parts) > 1:
                # 拆分成功，展开缩写
                for p in parts:
                    if p in ABBREVIATIONS:
                        all_keywords.extend(re.findall(r'\w+', ABBREVIATIONS[p]))
                    elif len(p) > 1 and p not in stopwords:
                        all_keywords.append(p)
            else:
                all_keywords.append(w)
        elif len(w) > 2:
            all_keywords.append(w)

    # 去重保序
    seen = set()
    unique = []
    for kw in all_keywords:
        if kw not in seen:
            seen.add(kw)
            unique.append(kw)

    return unique if unique else [query_lower]


def search_fts5(query: str, kb_path: Path, limit: int = 100) -> List[Dict]:
    """全文搜索（关键词匹配）"""
    # 只读模式打开，避免冲突
    conn = sqlite3.connect(f'file:{kb_path}?mode=ro', uri=True)
    cursor = conn.cursor()
    
    # 提取关键词并构建OR查询
    keywords = extract_keywords(query)
    if not keywords:
        keywords = [query]
    
    # FTS5 OR查询（用双引号包裹关键词，避免特殊符号和保留字问题）
    fts_query = ' OR '.join([f'"{kw}"' for kw in keywords])
    
    try:
        # 使用 bm25() 得分（越小越相关），转换为相似度分数（越大越相关）
        cursor.execute("""
            SELECT chunks.doc_id, chunks.chunk_id, chunks.text, chunks.page_start,
                   d.path, d.vendor, d.doc_type, d.title,
                   bm25(chunks_fts) as bm25_score
            FROM chunks_fts
            JOIN chunks ON chunks_fts.chunk_id = chunks.chunk_id
            JOIN documents d ON chunks.doc_id = d.doc_id
            WHERE chunks_fts MATCH ?
            ORDER BY bm25(chunks_fts) ASC
            LIMIT ?
        """, (fts_query, limit))
        
        # 获取所有结果并提取 bm25 值
        rows = cursor.fetchall()
        if not rows:
            conn.close()
            return []
        
        # 找到最小 bm25 值（最相关，通常最负）
        bm25_vals = [row[8] if row[8] is not None else 0.0 for row in rows]
        min_bm25 = min(bm25_vals)
        
        results = []
        for row in rows:
            bm25_value = row[8] if row[8] is not None else 0.0
            # 相对归一化：最相关的 bm25（最小值）→ adj=0 → score=1.0
            # 越不相关的 bm25 → adj 越大 → score 越接近 0
            # 这样确保 FTS 排序和分数单调一致
            adj = bm25_value - min_bm25
            fts_score = 1.0 / (1.0 + adj)
            
            results.append({
                'doc_id': row[0],
                'chunk_id': row[1],
                'content': row[2],  # text列映射为content
                'page': row[3],     # page_start列映射为page
                'path': row[4],
                'vendor': row[5],
                'doc_type': row[6],
                'title': row[7],
                'score': fts_score,  # 相对归一化的相似度分数
                'method': 'fts5'
            })
    except sqlite3.OperationalError as e:
        print(f"  ⚠️  FTS5查询失败: {e}")
        results = []
    except sqlite3.DatabaseError as e:
        print(f"  ⚠️  数据库错误: {e}")
        print(f"  💡 提示: 请停止 kb_watcher 后重试")
        results = []
    
    conn.close()
    return results


def search_faiss(query: str, kb_path: Path, faiss_path: Path, limit: int = 100) -> List[Dict]:
    """向量搜索（语义相似）
    
    说明：自动检测索引类型（L2 vs IP/余弦），并采用相应的距离映射策略：
    - L2 距离：使用 1/(1+dist) 映射到相似度，确保分数在 (0,1] 范围
    - IP/余弦距离：对 query 做 L2 normalize，直接使用 dist 作为相似度并 clamp 到 [0,1]
    分数越大表示越相关。
    """
    if not FAISS_AVAILABLE:
        return []
    
    try:
        # 加载FAISS索引
        index = faiss.read_index(str(faiss_path))
        
        # 检测索引类型（L2 vs IP/余弦）
        is_inner_product = False
        try:
            # 尝试读取 metric_type (FAISS >= 1.6.0)
            if hasattr(index, 'metric_type'):
                is_inner_product = (index.metric_type == faiss.METRIC_INNER_PRODUCT)
        except:
            # 降级：检查索引类名（不太可靠但能覆盖常见情况）
            index_class = type(index).__name__
            is_inner_product = 'IP' in index_class or 'InnerProduct' in index_class
        
        # 使用缓存的模型
        model = get_sentence_transformer()
        
        # 查询向量
        query_vec = model.encode([query])[0].astype('float32')
        
        # 如果是 IP/余弦索引，对 query 做 L2 归一化
        if is_inner_product:
            norm = np.linalg.norm(query_vec)
            if norm > 0:
                query_vec = query_vec / norm
        
        query_vec = query_vec.reshape(1, -1)
        
        # 搜索
        distances, indices = index.search(query_vec, limit)
        
        # 获取chunk信息（只读模式）
        conn = sqlite3.connect(f'file:{kb_path}?mode=ro', uri=True)
        cursor = conn.cursor()
        
        results = []
        for idx, (dist, vec_id) in enumerate(zip(distances[0], indices[0])):
            if vec_id < 0:
                continue
            
            # 根据vector_id找到chunk
            cursor.execute("""
                SELECT e.chunk_id, c.doc_id, c.text, c.page_start,
                       d.path, d.vendor, d.doc_type, d.title
                FROM embeddings e
                JOIN chunks c ON e.chunk_id = c.chunk_id
                JOIN documents d ON c.doc_id = d.doc_id
                WHERE e.vector_id = ?
            """, (int(vec_id),))
            
            row = cursor.fetchone()
            if row:
                # 根据索引类型映射分数
                if is_inner_product:
                    # IP/余弦：dist 本身就是相似度（已做归一化），clamp 到 [0,1]
                    faiss_score = float(max(0.0, min(1.0, dist)))
                else:
                    # L2 距离映射为相似度：1 / (1 + dist)
                    # 确保分数在 (0, 1] 范围，dist 越小（越相似）score 越大
                    faiss_score = 1.0 / (1.0 + float(dist))
                
                results.append({
                    'chunk_id': row[0],
                    'doc_id': row[1],
                    'content': row[2],  # text列映射为content
                    'page': row[3],     # page_start列映射为page
                    'path': row[4],
                    'vendor': row[5],
                    'doc_type': row[6],
                    'title': row[7],
                    'score': faiss_score,  # 使用 1/(1+dist) 映射的相似度
                    'method': 'faiss'
                })
        
        conn.close()
    except sqlite3.DatabaseError as e:
        print(f"  ⚠️  数据库错误: {e}")
        print(f"  💡 提示: 请停止 kb_watcher 后重试")
        results = []
    except Exception as e:
        print(f"  ⚠️  FAISS查询失败: {e}")
        results = []
    
    return results


def hybrid_search(query: str, kb_path: Path, faiss_path: Path = None,
                  top_k: int = 100) -> List[Dict]:
    """混合搜索：FTS5 + FAISS"""
    # 语言检测和翻译
    lang = detect_language(query)
    print(f"\n🔍 检测语言: {'中文' if lang == 'zh' else '英文'}")
    
    if lang == 'zh' and TRANSLATOR_AVAILABLE:
        en_query = translate_to_english(query)
    else:
        en_query = query
    
    all_results = []
    
    # FTS5搜索
    print(f"📚 关键词搜索 (FTS5)...")
    fts_results = search_fts5(en_query, kb_path, limit=top_k)
    if fts_results:
        print(f"  ✅ 找到 {len(fts_results)} 个结果")
        all_results.extend(fts_results)
    else:
        print(f"  ⚠️  未找到结果")
    
    # FAISS搜索
    if FAISS_AVAILABLE and faiss_path and faiss_path.exists():
        print(f"🧠 语义搜索 (FAISS)...")
        faiss_results = search_faiss(en_query, kb_path, faiss_path, limit=top_k)
        if faiss_results:
            print(f"  ✅ 找到 {len(faiss_results)} 个结果")
            all_results.extend(faiss_results)
        else:
            print(f"  ⚠️  未找到结果")
    
    if not all_results:
        return []
    
    # === 真正的加权融合逻辑 ===
    # 1. 按 doc_id 分组，收集来自 FTS 和 FAISS 的所有分数
    doc_scores = {}  # doc_id -> {'fts': [scores], 'faiss': [scores], 'best_chunk': result}
    
    for result in all_results:
        doc_id = result['doc_id']
        method = result['method']
        score = result['score']
        
        if doc_id not in doc_scores:
            doc_scores[doc_id] = {'fts': [], 'faiss': [], 'best_chunk': result}
        
        # 收集分数
        if method == 'fts5':
            doc_scores[doc_id]['fts'].append(score)
        elif method == 'faiss':
            doc_scores[doc_id]['faiss'].append(score)
        
        # 更新最佳 chunk（用于返回）
        if score > doc_scores[doc_id]['best_chunk']['score']:
            doc_scores[doc_id]['best_chunk'] = result
    
    # 2. 计算每个 doc 的融合分数
    FTS_WEIGHT = 0.6
    FAISS_WEIGHT = 0.4
    DUAL_HIT_BONUS = 0.05  # 双命中奖励
    
    final_results = []
    for doc_id, data in doc_scores.items():
        fts_scores = data['fts']
        faiss_scores = data['faiss']
        best_chunk = data['best_chunk']
        
        # 聚合各通道分数（取最大值）
        fts_max = max(fts_scores) if fts_scores else 0.0
        faiss_max = max(faiss_scores) if faiss_scores else 0.0
        
        # 加权融合
        if fts_scores and faiss_scores:
            # 双命中：加权融合 + 小 bonus
            final_score = FTS_WEIGHT * fts_max + FAISS_WEIGHT * faiss_max + DUAL_HIT_BONUS
            final_score = min(final_score, 1.0)  # clamp 到 1.0
            method = 'hybrid'
        elif fts_scores:
            # 仅 FTS
            final_score = fts_max
            method = 'fts5'
        else:
            # 仅 FAISS
            final_score = faiss_max
            method = 'faiss'
        
        # 更新 best_chunk 的分数和方法
        best_chunk['score'] = final_score
        best_chunk['method'] = method
        final_results.append(best_chunk)
    
    # 3. 排序并返回
    final_results.sort(key=lambda x: x['score'], reverse=True)
    print(f"\n📊 合并结果: {len(final_results)} 个文档")
    return final_results


def select_diverse_docs(results: List[Dict], max_docs: int = 20) -> List[Dict]:
    """智能选择文档：去重、多样性、质量优先"""
    if not results:
        return []
    
    selected = []
    doc_ids_seen = set()
    
    # 第一轮：选择高分文档（score > 0.7）
    high_score_docs = [r for r in results if r['score'] > 0.7]
    for r in high_score_docs[:max_docs // 2]:
        if r['doc_id'] not in doc_ids_seen:
            selected.append(r)
            doc_ids_seen.add(r['doc_id'])
    
    # 第二轮：按厂商和文档类型分组，确保多样性
    by_category = {}
    for r in results:
        if r['doc_id'] in doc_ids_seen:
            continue
        key = f"{r['vendor']}/{r['doc_type']}"
        if key not in by_category:
            by_category[key] = []
        by_category[key].append(r)
    
    # 轮询选择（每个类别选一个）
    categories = sorted(by_category.keys())
    round_idx = 0
    
    while len(selected) < max_docs and categories:
        for cat in categories[:]:
            if len(by_category[cat]) > 0:
                r = by_category[cat].pop(0)
                if r['doc_id'] not in doc_ids_seen:
                    selected.append(r)
                    doc_ids_seen.add(r['doc_id'])
                    if len(selected) >= max_docs:
                        break
            else:
                categories.remove(cat)
        round_idx += 1
        if round_idx > 10:  # 防止死循环
            break
    
    # 第三轮：如果还不够，按分数补充
    if len(selected) < max_docs:
        for r in results:
            if r['doc_id'] not in doc_ids_seen:
                selected.append(r)
                doc_ids_seen.add(r['doc_id'])
                if len(selected) >= max_docs:
                    break
    
    return selected[:max_docs]


def pack_files(selected: List[Dict], base_dir: Path, output_dir: Path) -> List[Path]:
    """打包文件到输出目录"""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    packed = []
    for i, doc in enumerate(selected, 1):
        src = base_dir / doc['path']
        if not src.exists():
            print(f"  ⚠️  文件不存在: {doc['path']}")
            continue
        
        # 保留原文件名，加序号避免冲突
        dst_name = f"{i:02d}_{src.name}"
        dst = output_dir / dst_name
        
        shutil.copy2(src, dst)
        packed.append(dst)
    
    return packed


def main():
    print("="*70)
    print("智能文件打包器 - NotebookLM助手")
    print("="*70)
    
    # 配置
    kb_path = Path(r"D:\E-BOOK\axis-SQLite\kb.sqlite")
    faiss_path = Path(r"D:\E-BOOK\axis-SQLite\kb.faiss")
    base_dir = Path(r"D:\E-BOOK\axis-dcdc-pdf")
    base_output_dir = Path(r"D:\E-BOOK\_to_notebooklm")
    
    if not kb_path.exists():
        print(f"❌ 知识库不存在: {kb_path}")
        return
    
    # 查询
    print("\n请输入查询（支持中文/英文）:")
    query = input("> ").strip()
    
    if not query:
        print("❌ 查询不能为空")
        return
    
    # 创建输出目录：日期 / 查询slug
    date_str = datetime.now().strftime("%Y-%m-%d")
    slug = make_slug(query)
    output_dir = base_output_dir / date_str / slug
    
    print(f"\n{'='*70}")
    print(f"查询: {query}")
    print(f"输出: {output_dir}")
    print(f"{'='*70}")
    
    # 搜索（hybrid_search 内部会自动处理语言检测和翻译）
    results = hybrid_search(query, kb_path, faiss_path, top_k=100)
    
    if not results:
        print("\n❌ 未找到相关文档")
        return
    
    print(f"\n✅ 找到 {len(results)} 个相关文档")
    
    # 智能选择
    max_docs = 20
    selected = select_diverse_docs(results, max_docs=max_docs)
    
    print(f"\n📦 智能选择了 {len(selected)} 个文档:")
    print(f"{'='*70}")
    
    # 按分数分组显示
    high_score = [d for d in selected if d['score'] > 0.7]
    med_score = [d for d in selected if 0.4 <= d['score'] <= 0.7]
    low_score = [d for d in selected if d['score'] < 0.4]
    
    if high_score:
        print(f"\n🔥 高相关度 ({len(high_score)} 个):")
        for i, doc in enumerate(high_score, 1):
            score_str = f"{doc['score']:.3f}"
            method_icon = "🔤" if doc['method'] == 'fts5' else "🧠" if doc['method'] == 'faiss' else "⚡"
            print(f"{i:2d}. [{score_str}] {method_icon} {doc['vendor']}/{doc['doc_type']}")
            print(f"    {doc['title'][:65]}...")
    
    if med_score:
        print(f"\n📌 中等相关度 ({len(med_score)} 个):")
        for i, doc in enumerate(med_score, len(high_score) + 1):
            score_str = f"{doc['score']:.3f}"
            method_icon = "🔤" if doc['method'] == 'fts5' else "🧠" if doc['method'] == 'faiss' else "⚡"
            print(f"{i:2d}. [{score_str}] {method_icon} {doc['vendor']}/{doc['doc_type']}")
            print(f"    {doc['title'][:65]}...")
    
    if low_score:
        print(f"\n💡 参考文档 ({len(low_score)} 个):")
        for i, doc in enumerate(low_score, len(high_score) + len(med_score) + 1):
            score_str = f"{doc['score']:.3f}"
            print(f"{i:2d}. [{score_str}] {doc['vendor']}/{doc['doc_type']} - {doc['title'][:50]}...")
    
    print(f"\n{'='*70}")
    print("图例: 🔤=关键词匹配 🧠=语义相似 ⚡=混合验证")
    
    # 确认打包
    print(f"\n{'='*70}")
    confirm = input(f"打包这 {len(selected)} 个文件? (y/n): ").strip().lower()
    
    if confirm != 'y':
        print("❌ 取消打包")
        return
    
    # 清空输出目录（如果存在）
    if output_dir.exists():
        print(f"⚠️  目录已存在，将清空: {output_dir}")
        shutil.rmtree(output_dir)
    
    # 打包
    print(f"\n📦 打包中...")
    packed = pack_files(selected, base_dir, output_dir)
    
    print(f"\n✅ 成功打包 {len(packed)} 个文件")
    print(f"📁 输出目录: {output_dir.absolute()}")
    print(f"\n💡 下一步:")
    print(f"   1. 打开 NotebookLM")
    print(f"   2. 上传 {output_dir.absolute()} 目录中的所有文件")
    print(f"   3. 开始分析！")
    
    # 生成文件清单
    manifest = output_dir / "manifest.txt"
    lang = detect_language(query)  # 重新检测用于 manifest
    with open(manifest, 'w', encoding='utf-8') as f:
        f.write(f"查询: {query}\n")
        f.write(f"语言: {'中文' if lang == 'zh' else '英文'}\n")
        f.write(f"打包时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"检索方法: FTS5关键词 + FAISS语义相似\n\n")
        f.write(f"文件清单 ({len(packed)} 个):\n")
        f.write("="*70 + "\n\n")
        
        # 按相关度分组
        high_score = [(i, doc) for i, doc in enumerate(selected, 1) if doc['score'] > 0.7]
        med_score = [(i, doc) for i, doc in enumerate(selected, 1) if 0.4 <= doc['score'] <= 0.7]
        low_score = [(i, doc) for i, doc in enumerate(selected, 1) if doc['score'] < 0.4]
        
        if high_score:
            f.write("【高相关度文档】\n\n")
            for i, doc in high_score:
                f.write(f"{i:2d}. {doc['title']}\n")
                f.write(f"    厂商: {doc['vendor']} | 类型: {doc['doc_type']}\n")
                f.write(f"    相关度: {doc['score']:.3f} | 方法: {doc['method']}\n")
                f.write(f"    路径: {doc['path']}\n\n")
        
        if med_score:
            f.write("\n【中等相关度文档】\n\n")
            for i, doc in med_score:
                f.write(f"{i:2d}. {doc['title']}\n")
                f.write(f"    厂商: {doc['vendor']} | 类型: {doc['doc_type']}\n")
                f.write(f"    相关度: {doc['score']:.3f}\n\n")
        
        if low_score:
            f.write("\n【参考文档】\n\n")
            for i, doc in low_score:
                f.write(f"{i:2d}. {doc['title']}\n")
                f.write(f"    {doc['vendor']}/{doc['doc_type']} - 相关度: {doc['score']:.3f}\n\n")
        
        f.write("\n" + "="*70 + "\n")
        f.write("\nNotebookLM 使用建议:\n")
        f.write("1. 优先阅读高相关度文档\n")
        f.write("2. 关注混合验证(⚡)的文档，这些同时满足关键词和语义匹配\n")
        f.write("3. 使用原始查询作为初始问题\n")
        f.write("4. 在NotebookLM中可以进一步细化问题\n")
    
    print(f"📋 文件清单: {manifest}")


if __name__ == "__main__":
    main()
