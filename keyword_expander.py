#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
关键词扩展器 — 从用户查询生成多样化 DDG 搜索关键词
无需 API / 浏览器，纯本地规则引擎。

策略 (v2 — DDG API 兼容):
  搜索时 **不使用** filetype:pdf / site: 等操作符 (DDG API 解析不稳定),
  改为在搜索词中自然包含 "pdf" / "datasheet" + 厂商名 等标记词,
  由下载阶段通过 URL 模式 + Content-Type + 魔数三重验证来筛选 PDF。

作者: AlaiDocs
版本: 2.0.0
"""

from typing import List, Set

# ============================================================================
# DC-DC 领域知识库
# ============================================================================

TOP_VENDORS = [
    "ti.com",
    "analog.com",
    "infineon.com",
    "st.com",
    "onsemi.com",
    "renesas.com",
    "nxp.com",
    "microchip.com",
    "monolithicpower.com",
    "rohm.com",
    "diodes.com",
    "richtek.com",
]

DOC_TYPE_MARKERS = [
    "datasheet pdf",
    "application note pdf",
    "design guide pdf",
    "reference design pdf",
    "evaluation board pdf",
    "white paper pdf",
    "technical article",
]

TECH_ASPECTS = [
    "design",
    "control loop",
    "efficiency",
    "EMI",
    "thermal",
    "PCB layout",
    "gate driver",
    "compensation",
]

TOPOLOGY_SYNONYMS = {
    "buck": ["step-down converter", "synchronous buck"],
    "boost": ["step-up converter", "boost converter"],
    "buck-boost": ["4-switch buck-boost", "non-inverting buck-boost",
                   "inverting converter"],
    "flyback": ["isolated flyback converter"],
    "llc": ["LLC resonant converter"],
    "bidirectional": ["bidirectional DC-DC", "bidirectional power converter"],
    "half-bridge": ["half bridge converter"],
    "full-bridge": ["phase-shifted full bridge"],
    "sepic": ["SEPIC converter"],
    "charge pump": ["switched capacitor converter"],
}


# ============================================================================
# 核心扩展函数
# ============================================================================

def expand_query(query: str, max_keywords: int = 50) -> List[str]:
    """
    从用户查询生成多样化搜索关键词列表。

    **重要**: 不使用 filetype:pdf 操作符 (DDG API 不支持).
    而是在搜索词中自然包含 "pdf" / "datasheet" 等词汇,
    下载阶段通过 URL 过滤 + Content-Type + 魔数验证确保得到 PDF。
    """
    keywords: List[str] = []

    # ── 层 1: 直接搜索 ────────────────────────────────────────
    keywords.append(f"{query} pdf")
    keywords.append(f"{query} datasheet")
    keywords.append(f"{query} application note")

    # ── 层 2: 查询 × 文档类型 ──────────────────────────────────
    for marker in DOC_TYPE_MARKERS:
        keywords.append(f"{query} {marker}")

    # ── 层 3: 厂商名 + 查询 (自然语言,不用 site:) ─────────────
    for domain in TOP_VENDORS:
        vendor = domain.split(".")[0]
        keywords.append(f"{vendor} {query} datasheet pdf")

    # ── 层 4: 查询 × 技术维度 ──────────────────────────────────
    for aspect in TECH_ASPECTS:
        keywords.append(f"{query} {aspect} pdf")

    # ── 层 5: 拓扑同义词展开 ──────────────────────────────────
    query_lower = query.lower()
    matched_bases: Set[str] = set()
    for base in sorted(TOPOLOGY_SYNONYMS, key=len, reverse=True):
        if base in query_lower:
            if any(base in mb and base != mb for mb in matched_bases):
                continue
            matched_bases.add(base)
            for syn in TOPOLOGY_SYNONYMS[base][:2]:
                if syn.lower() != query_lower:
                    keywords.append(f"{syn} pdf")
                    keywords.append(f"{syn} datasheet")

    # ── 去重 ──────────────────────────────────────────────────
    seen: Set[str] = set()
    unique: List[str] = []
    for kw in keywords:
        key = kw.lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(kw)

    return unique[:max_keywords]


def expand_with_gemini_keywords(
    query: str,
    gemini_keywords: List[str],
    max_keywords: int = 60,
) -> List[str]:
    """合并本地扩展 + Gemini 生成的关键词。"""
    local = expand_query(query, max_keywords=max_keywords)
    seen = {kw.lower().strip() for kw in local}
    merged = []
    for kw in gemini_keywords:
        key = kw.lower().strip()
        if key not in seen:
            seen.add(key)
            merged.append(kw)
    return (merged + local)[:max_keywords]


# ============================================================================
if __name__ == "__main__":
    import sys
    topic = " ".join(sys.argv[1:]) or "bidirectional buck-boost"
    kw_list = expand_query(topic)
    print(f"\n关键词扩展: \"{topic}\" → {len(kw_list)} 个搜索词\n")
    for i, kw in enumerate(kw_list, 1):
        print(f"  {i:2d}. {kw}")
