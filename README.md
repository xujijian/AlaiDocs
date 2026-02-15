# AlaiDocs — DC-DC 技术知识库自动化系统 🚀

<div align="center">

**一句话建立专业的 DC-DC 技术知识库**

Gemini 关键词生成 → DuckDuckGo 搜索 → PDF 下载 → 4D 分类归档 → NotebookLM 打包

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)]()

</div>

---

## 📦 30 秒上手

```bash
# 1. 克隆项目
git clone https://github.com/YOUR_ORG/AlaiDocs.git
cd AlaiDocs

# 2. 创建虚拟环境
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt
pip install -r requirements_browser.txt  # 浏览器采集需要

# 4. 初始化项目 (创建 data/ 目录结构)
python alaidocs.py init

# 5. 开始使用!
python alaidocs.py              # 交互模式
python alaidocs.py status       # 查看状态
```

初始化后的目录结构：
```
AlaiDocs/
├── alaidocs.py                 # ← 统一入口
├── integrated_config.json      # 模板配置 (入 Git)
├── alaidocs_config.json        # 用户配置 (不入 Git, init 自动生成)
├── data/                       # 运行时数据 (不入 Git)
│   ├── downloads/              # 采集缓冲区
│   ├── classified/             # 4D 分类归档
│   │   └── TI/datasheet/power_ic/buck/xxx.pdf
│   ├── kb/                     # 知识库
│   │   ├── kb.sqlite
│   │   └── kb.faiss
│   ├── packed/                 # NotebookLM 打包输出
│   └── keywords.json           # 关键词库
└── ...
```

---

## 🎯 核心命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `init` | 首次初始化 | `python alaidocs.py init` |
| `collect` | 一键采集 | `python alaidocs.py collect --rounds 3` |
| `classify` | 4D 自动分类 | `python alaidocs.py classify` |
| `pack` | 检索打包 (支持中文) | `python alaidocs.py pack "降压变换器热管理"` |
| `run` | 全流程一句话完成 | `python alaidocs.py run "GaN效率优化"` |
| `status` | 系统状态 | `python alaidocs.py status` |

### 高置信度筛选

```bash
# 只取 score ≥ 0.6 的高价值文档，最多 15 篇
python alaidocs.py pack "automotive EMC design" --top 15 --min-score 0.6

# 全流程 + 筛选
python alaidocs.py run "LLC谐振变换器" --rounds 2 --top 10 --min-score 0.5

# 跳过确认直接打包
python alaidocs.py pack "bidirectional buck-boost" --min-score 0.7 -y
```

### 一键启动脚本

```bash
# Windows
alaidocs.bat

# macOS / Linux
chmod +x alaidocs.sh
./alaidocs.sh
```

### 交互模式

```
alaidocs> 检索 降压变换器EMI设计
alaidocs> pack GaN efficiency --top 10 --min-score 0.6
alaidocs> 开始更新资料
alaidocs> 状态
```

---

## 🏗️ 系统架构

```
                    alaidocs.py (统一 CLI 入口)
                         │
          ┌──────────────┼──────────────┐
          │              │              │
      collect        classify         pack
          │              │              │
          ▼              ▼              ▼
  ┌─────────────┐ ┌──────────────┐ ┌────────────┐
  │ Gemini AI   │ │ 4D 分类器    │ │ 混合检索   │
  │ 关键词生成  │ │ 厂商/类型/   │ │ FTS5+FAISS │
  │      ↓      │ │ 主题/拓扑    │ │ 高置信筛选 │
  │ DuckDuckGo  │ │      ↓       │ │     ↓      │
  │ 搜索+下载   │ │ vendor/      │ │ NotebookLM │
  │      ↓      │ │ doc_type/    │ │ Source打包  │
  │ data/       │ │ topic/       │ │ + manifest  │
  │ downloads/  │ │ topology/    │ │            │
  └─────────────┘ └──────────────┘ └────────────┘
```

### 4D 分类逻辑

每个 PDF 文件通过提取前 3 页文本，在以下 4 个维度独立打分归档：

| 维度 | 说明 | 示例值 |
|------|------|--------|
| **厂商 (Vendor)** | 识别文档来源 | TI, ADI, Infineon, ST, ... |
| **类型 (Type)** | 文档类别 | datasheet, application_note, reference_design |
| **主题 (Topic)** | 技术领域 | power_ic, emi_emc, thermal, control_loop |
| **拓扑 (Topology)** | 电路拓扑 | buck, boost, buck_boost, llc, dab |

置信度 < 0.6 的文档自动归入 `Unknown/LowConfidence/`。

---

## ⚙️ 配置

### 配置优先级

```
内置默认 → integrated_config.json (模板) → alaidocs_config.json (用户)
```

- `integrated_config.json` — 项目级模板，入 Git，所有人共享
- `alaidocs_config.json` — 用户级覆盖，**不入 Git**，`init` 自动生成

### 自定义路径

编辑 `alaidocs_config.json`：

```json
{
  "paths": {
    "download_dir":   "data/downloads",
    "classified_dir": "data/classified",
    "kb_dir":         "data/kb",
    "pack_output":    "data/packed",
    "keywords_db":    "data/keywords.json"
  }
}
```

也支持绝对路径（例如指向已有的 PDF 库）：

```json
{
  "paths": {
    "classified_dir": "/mnt/nas/dc-dc-pdfs",
    "kb_dir": "/mnt/nas/knowledge-base"
  }
}
```

### 采集参数

在 `integrated_config.json` 中调整：

```json
{
  "downloader": {
    "keywords_per_round": 10,
    "results_per_keyword": 20,
    "total_size_limit_gb": 100,
    "total_files_limit": 10000,
    "domain_whitelist": ["ti.com", "analog.com", "infineon.com", ...]
  }
}
```

---

## 📋 依赖

### 核心依赖 (requirements.txt)
```
requests, ddgs/duckduckgo-search, tqdm, pypdf
```

### 浏览器采集 (requirements_browser.txt)
```
selenium, webdriver-manager
```

### 检索打包 (可选)
```
pip install sentence-transformers faiss-cpu deep-translator
```

---

## 🤝 支持的厂商 (20+)

TI · ADI · ST · Infineon · ON Semi · Renesas · Microchip · ROHM · NXP · MPS ·
Power Integrations · Vicor · Vishay · Littelfuse · Bourns · Nexperia ·
Murata · TDK · Würth Elektronik · Kemet · Semtech

可在 `integrated_config.json → downloader.domain_whitelist` 中添加更多。

---

## 📖 进阶文档

- [系统架构详解](ARCHITECTURE.md)
- [功能说明](功能说明.md)
- [智能打包指南](SMART_PACK_GUIDE.md)
- [Google 搜索迁移](GOOGLE_MIGRATION.md)

---

## 📄 License

MIT
