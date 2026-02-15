# 整合下载分类系统使用指南

**日期**: 2026-01-27  
**版本**: 1.0.0

## 📋 系统概述

整合了两个强大的系统：
1. **智能下载器** - 自动生成关键词、搜索、下载PDF
2. **智能分类器** - 4维度自动分类PDF文档

### 🔄 工作流程

```
Gemini生成关键词 → Google搜索 → 下载PDF → 自动分类 → 归档
     ↑                                              ↓
     └──────────────── 循环 ────────────────────────┘
```

## 🚀 快速开始

### 方式一：整合模式（推荐）

自动下载并分类：

```bash
.\start_integrated.bat
```

### 方式二：仅分类现有文件

对 `downloads_continuous` 目录中已有的文件进行分类：

```bash
.\classify_existing.bat
```

### 方式三：命令行完全控制

```bash
python integrated_downloader_classifier.py \
    --download-dir "./downloads_temp" \
    --classified-dir "./downloads_classified" \
    --keyword-db "./keywords.json" \
    --mode integrated
```

## 📁 目录结构

### 输入/输出目录

```
axdcdcpdf/
├── downloads_temp/           # 临时下载目录（自动清空）
│   ├── ti/
│   ├── st/
│   └── ...
│
├── downloads_classified/     # 分类后的归档目录
│   ├── TI/
│   │   ├── datasheet/
│   │   │   ├── power_ic/
│   │   │   │   ├── buck/
│   │   │   │   │   ├── TPS54620.pdf
│   │   │   │   │   └── LM5164.pdf
│   │   │   │   └── boost/
│   │   │   └── control_loop/
│   │   └── application_note/
│   ├── ST/
│   └── Unknown/
│       ├── LowConfidence/
│       └── ErrorFiles/
│
└── downloads_continuous/     # 原连续下载目录（可选）
```

### 分类维度

分类器使用 **4个维度** 对PDF进行智能分类：

#### 1️⃣ Vendor（厂商）
- TI, ST, ADI, Infineon, Microchip, ROHM, NXP, MPS, 等
- 基于文件内容和文件名识别

#### 2️⃣ Doc Type（文档类型）⭐最重要
- `datasheet` - 数据手册
- `application_note` - 应用笔记
- `reference_design` - 参考设计
- `eval_user_guide` - 评估板指南
- `whitepaper` - 白皮书
- `standard` - 标准文档

#### 3️⃣ Topic（主题）
- `power_ic` - 电源IC
- `power_stage` - 功率级
- `magnetics` - 磁性元件
- `emi_emc` - EMI/EMC
- `control_loop` - 控制环路
- `thermal` - 热管理

#### 4️⃣ Topology（拓扑）
- `buck` - 降压
- `boost` - 升压
- `buck_boost` - 升降压
- `flyback` - 反激
- `llc` - LLC谐振
- 等...

### 路径示例

```
downloads_classified/TI/datasheet/power_ic/buck/TPS54620.pdf
                     ↑   ↑          ↑        ↑    ↑
                 Vendor DocType   Topic   Topology  文件
```

## ⚙️ 配置说明

编辑 `integrated_config.json`:

### 下载器配置

```json
{
    "downloader": {
        "chatgpt_headless": false,      // Gemini无头模式
        "keywords_per_round": 10,        // 每轮生成关键词数
        "results_per_keyword": 20,       // 每个关键词搜索结果数
        "max_downloads_per_keyword": 10, // 每个关键词最大下载数
        "round_interval": 300,           // 轮次间隔（秒）
        "total_size_limit_gb": 100,      // 总大小限制
        "focus_areas": [                 // 重点领域
            "DC-DC converter",
            "buck converter"
        ]
    }
}
```

### 分类器配置

```json
{
    "classifier": {
        "head_pages": 3,              // 提取PDF前N页
        "min_stable_seconds": 15,     // 文件稳定时间
        "scan_interval": 30           // 扫描间隔（秒）
    }
}
```

## 📊 输出文件

### 1. metadata.jsonl

记录每个PDF的详细分类信息：

```json
{
  "doc_id": "7f3a8bc...",
  "src_path": "downloads_temp/ti/TPS54620.pdf",
  "dst_path": "downloads_classified/TI/datasheet/power_ic/buck/TPS54620.pdf",
  "vendor": "TI",
  "doc_type": "datasheet",
  "topic": "power_ic",
  "topology": "buck",
  "confidence": 0.89,
  "matched_keywords": {
    "vendor": ["TI", "Texas Instruments"],
    "doc_type": ["Electrical Characteristics"],
    "topic": ["DC-DC", "buck converter"]
  },
  "title_guess": "TPS54620 Datasheet",
  "page_count": 45,
  "processed_time": "2026-01-27T10:30:45"
}
```

### 2. classified_files.db

SQLite数据库，记录已分类文件，防止重复处理。

### 3. integrated_system.log

系统运行日志：
- 下载进度
- 分类结果
- 错误信息

## 🔧 高级用法

### 批量分类现有文件

如果你已经有大量下载的PDF：

```bash
python integrated_downloader_classifier.py \
    --download-dir "./downloads_continuous" \
    --classified-dir "./downloads_classified" \
    --mode classify-only
```

### 仅下载不分类

使用原来的连续搜索器：

```bash
.\start_continuous.bat
```

### 调试模式

```bash
python integrated_downloader_classifier.py \
    --download-dir "./test_downloads" \
    --classified-dir "./test_classified" \
    --mode integrated \
    --debug
```

## 💡 使用场景

### 场景1：长期自动化收集

```bash
# 启动整合系统，24小时运行
.\start_integrated.bat

# 系统会：
# 1. 每5分钟生成新关键词
# 2. 搜索并下载PDF
# 3. 自动分类到目标目录
# 4. 清空临时目录
```

### 场景2：整理已有文档

```bash
# 将 downloads_continuous 目录中的所有PDF分类
.\classify_existing.bat

# 结果：
# - 所有PDF按4维度分类
# - 生成 metadata.jsonl 元数据
# - 原文件保持不变（或移动）
```

### 场景3：测试特定领域

修改 `integrated_config.json`:

```json
{
    "downloader": {
        "keywords_per_round": 5,
        "max_downloads_per_keyword": 3,
        "focus_areas": ["flyback converter", "LLC resonant"]
    }
}
```

## 📈 监控与统计

### 查看实时日志

```bash
# Windows PowerShell
Get-Content integrated_system.log -Wait -Tail 50

# CMD
tail -f integrated_system.log
```

### 查看分类统计

```bash
# 查看已分类文件数
sqlite3 classified_files.db "SELECT COUNT(*) FROM processed_files;"

# 按厂商统计
python -c "
import json
from pathlib import Path
vendors = {}
for line in open('metadata.jsonl'):
    data = json.loads(line)
    v = data['vendor']
    vendors[v] = vendors.get(v, 0) + 1
print(vendors)
"
```

### 查看目录树

```bash
# Windows
tree /F downloads_classified

# 或使用 PowerShell
Get-ChildItem downloads_classified -Recurse | Select-Object FullName
```

## ⚠️ 注意事项

### 1. 磁盘空间

- 临时目录会在分类后自动清空
- 确保分类目录有足够空间（建议 100GB+）

### 2. 文件稳定性

- 系统会等待文件下载完成后再分类
- 默认等待15秒，可通过 `min_stable_seconds` 调整

### 3. 分类准确性

- 前3页内容决定分类结果
- 置信度低于0.6的归入 `Unknown/LowConfidence/`
- 无法提取文本的PDF仍会基于文件名分类

### 4. 性能优化

- 调整 `head_pages` 减少处理时间（但可能降低准确性）
- 增加 `scan_interval` 减少CPU占用

## 🐛 故障排除

### 问题1：分类到 Unknown/LowConfidence

**原因**：PDF内容不够明确或损坏

**解决**：
- 检查 `metadata.jsonl` 中的 `matched_keywords`
- 增加 `head_pages` 提取更多页
- 手动查看PDF内容

### 问题2：下载很多但分类很少

**原因**：文件未稳定或路径配置错误

**解决**：
- 增加 `min_stable_seconds`
- 检查 `download_dir` 是否正确
- 查看 `integrated_system.log`

### 问题3：内存占用过高

**原因**：同时处理大量PDF

**解决**：
- 减少 `keywords_per_round`
- 减少 `max_downloads_per_keyword`
- 增加 `round_interval`

## 📚 相关文档

- [integrated_downloader_classifier.py](integrated_downloader_classifier.py) - 主程序
- [pdf_classifier.py](pdf_classifier.py) - 分类器模块
- [continuous_searcher.py](continuous_searcher.py) - 下载器模块
- [integrated_config.json](integrated_config.json) - 配置文件

## 🎯 最佳实践

1. **首次运行** - 使用小的配置值测试
   ```json
   {
       "keywords_per_round": 3,
       "max_downloads_per_keyword": 2
   }
   ```

2. **生产环境** - 使用推荐配置
   ```json
   {
       "keywords_per_round": 10,
       "max_downloads_per_keyword": 10,
       "round_interval": 300
   }
   ```

3. **定期检查**
   - 每天查看 `metadata.jsonl` 统计
   - 每周清理 `Unknown/LowConfidence/` 目录
   - 定期备份分类目录

4. **优化分类**
   - 根据实际结果调整关键词权重
   - 在 `pdf_classifier.py` 中添加新的识别规则
   - 定期更新供应商列表

---

**更新日期**: 2026-01-27  
**版本**: 1.0.0  
**状态**: ✅ 已整合完成
