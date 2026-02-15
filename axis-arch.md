# DC-DC 转换器知识库系统架构说明

> 自动化数据表采集与分类平台  
> 更新时间: 2026-01-28

---

## 📋 目录

- [系统概述](#系统概述)
- [架构层次](#架构层次)
- [组件详解](#组件详解)
- [完整工作流](#完整工作流)
- [文件说明](#文件说明)
- [资源分配](#资源分配)
- [数据安全](#数据安全)
- [当前状态](#当前状态)

---

## 系统概述

这是一个**多层次自动化 DC-DC 转换器数据表采集与分类平台**，具备以下特点：

- 🤖 **AI 驱动**：使用 Google Gemini 动态生成搜索关键词
- ⚡ **高并发**：3 个并行下载进程，同时处理 17 个厂商
- 🎯 **高质量**：直接从官网搜索，使用 DuckDuckGo 的 `site:` 限定符
- 🔄 **自维护**：关键词自动补充，批处理脚本自动循环
- 🛡️ **容错性**：文件去重、网络超时处理、自动恢复

---

## 架构层次

```
┌─────────────────────────────────────────────────────────────┐
│                    控制层 (手动启动)                          │
├─────────────────────────────────────────────────────────────┤
│  • start_download_only.bat  → 调用 keyword_explorer.py      │
│  • start_vendor_batch1/2/3.bat → 调用 vendor_downloader.py  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              AI 生成层 (Gemini 驱动)                          │
├─────────────────────────────────────────────────────────────┤
│  keyword_explorer.py                                         │
│  ├─ 启动 Chrome 浏览器访问 Gemini                            │
│  ├─ 发送提示词请求生成 50 个关键词                           │
│  ├─ parse_keywords() 清洗和验证响应                          │
│  ├─ 合并到 explored_keywords.json (44 → 94 个)              │
│  └─ 避免重复：读取 used_keywords.json 排除已用关键词         │
│                                                              │
│  chatgpt_keyword_generator.py (Selenium 驱动)               │
│  ├─ GeminiKeywordGenerator 类                               │
│  ├─ 浏览器反检测配置 (user-agent, disable-blink-features)   │
│  ├─ 登录检测和自动等待                                      │
│  └─ 多选择器策略提取响应                                    │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│           下载层 (3 并行进程)                                │
├─────────────────────────────────────────────────────────────┤
│  vendor_downloader.py  [3个实例同时运行]                    │
│                                                              │
│  批次1 (TI, ADI, ST, Infineon, onsemi)                      │
│  批次2 (NXP, Microchip, Renesas, MPS, ROHM)                 │
│  批次3 (Vishay, Diodes, PI, Navitas, Richtek, AOS, Vicor)   │
│                                                              │
│  工作流程：                                                  │
│  ┌─────────────────────────────────────────┐                │
│  │ for keyword in POWER_KEYWORDS:          │                │
│  │   for vendor in vendors_to_process:     │                │
│  │     query = f"site:{site} {keyword}"    │                │
│  │     results = DDG 搜索                  │                │
│  │     for url in results[:100]:           │                │
│  │       download_pdf(url, vendor_dir)     │                │
│  │   save_used_keyword(keyword) # 标记完成 │                │
│  └─────────────────────────────────────────┘                │
│                                                              │
│  依赖：                                                      │
│  • DuckDuckGo 搜索 API (DDGS)                               │
│  • requests 下载                                            │
│  • 文件名 hash 去重                                         │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              存储层 (文件系统)                                │
├─────────────────────────────────────────────────────────────┤
│  downloads_continuous/                                       │
│  ├─ ti/          → TI 公司 PDF                              │
│  ├─ adi/         → ADI 公司 PDF                             │
│  ├─ st/          → ST 公司 PDF                              │
│  ├─ ... (17个厂商目录)                                      │
│  │                                                           │
│  ├─ results.jsonl           → 下载日志 (追加模式)           │
│  ├─ explored_keywords.json  → 44 个关键词池                │
│  ├─ used_keywords.json      → 已处理关键词追踪              │
│  ├─ explored_vendors.json   → 厂商域名映射                 │
│  └─ summary.csv             → 统计汇总                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 组件详解

### 1. 关键词生成模块 (keyword_explorer.py)

**职责**：动态生成搜索关键词，避免固定关键词枯竭

**输入**：
- Gemini AI (通过浏览器)
- used_keywords.json (避免重复)

**输出**：
- explored_keywords.json (新增 50 个关键词)

**核心技术**：
```python
# 1. Selenium 驱动 Chrome 访问 gemini.google.com
# 2. 构建英文提示词 (避免编码问题)
KEYWORD_PROMPT = """Generate 50 search keywords for power IC PDF documents.
Format: ONE per line, 2-5 words each, NO bullets, NO numbers"""

# 3. 多选择器策略提取响应
selectors = ['.message-content', '.model-response', '.markdown']

# 4. parse_keywords() 强力清洗
def parse_keywords(response_text: str) -> list:
    # 过滤 UI 文本："认识 Gemini"、"Would you like"
    # ASCII 占比验证：≥80%
    # 技术词验证：必须包含 buck/boost/converter 等
    # 长度限制：5-100 字符
    return clean_keywords
```

**关键特性**：
- 防 UI 文本污染：过滤 Gemini 界面提示
- 防编码错误：强制 ASCII 占比 ≥80%
- 防无效关键词：必须包含技术术语
- 防重复：自动排除 used_keywords.json 中的关键词

---

### 2. 并行下载模块 (vendor_downloader.py × 3)

**职责**：从 17 个厂商官网搜索并下载 PDF

**输入**：
- explored_keywords.json (44 个关键词)
- 命令行参数：`"TI,ADI,ST,Infineon,onsemi"`

**输出**：
- downloads_continuous/{vendor}/*.pdf
- results.jsonl (每次下载追加一行)
- used_keywords.json (关键词完成后标记)

**搜索策略**：
```python
query = f"site:{vendor_site} {keyword}"
# 示例: "site:ti.com buck converter datasheet"
results = DDGS().text(query, max_results=150)
```

**两层循环**：
```python
# 外层：关键词 (44个)
for keyword in POWER_KEYWORDS:
    # 内层：厂商 (batch1有5个, batch2有5个, batch3有7个)
    for vendor in vendors_to_process:
        搜索 → 下载 (最多100个) → 保存
    
    # 全部厂商完成后标记
    save_used_keyword(keyword)
```

**防滥用机制**：
- 随机延迟：0.3-0.5秒/文件, 1-2秒/厂商, 2-3秒/关键词
- User-Agent 模拟
- 3秒循环间隔

---

### 3. 浏览器驱动模块 (chatgpt_keyword_generator.py)

**职责**：使用 Selenium 自动化 Gemini 交互

**核心类**：
```python
class GeminiKeywordGenerator:
    def __init__(self, headless=False, response_timeout=120):
        # Chrome 反检测配置
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        
    def start(self):
        # 启动浏览器
        self.driver = webdriver.Chrome(service=service, options=options)
        
    def check_login_status(self) -> bool:
        # 检测是否需要登录
        
    def send_prompt(self, prompt: str) -> str:
        # 发送提示词，等待响应
        # 多选择器策略提取结果
```

**选择器策略**（从上到下尝试）：
1. `.message-content` - 标准消息容器
2. `.model-response` - 模型响应区域
3. `[data-message-author-role="model"]` - 作者角色属性
4. JavaScript 执行获取最后一条消息

---

### 4. 批处理脚本 (自动循环)

**start_vendor_batch1.bat**
```batch
@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ======================================
echo 厂商批次1: TI, ADI, ST, Infineon, onsemi
echo ======================================

call .venv\Scripts\activate.bat

:loop
python vendor_downloader.py "TI,ADI,ST,Infineon,onsemi"

echo 3秒后自动开始下一轮...
timeout /t 3 /nobreak >nul
goto loop
```

**作用**：
- ✅ 激活虚拟环境 (.venv)
- ✅ 无限循环下载
- ✅ 3秒间隔重启 (避免内存泄漏)
- ✅ Ctrl+C 停止

---

## 完整工作流

### 阶段 1: 关键词生成

```
用户运行: .\start_download_only.bat
    ↓
keyword_explorer.py 启动
    ↓
打开 Chrome 访问 gemini.google.com
    ↓
发送提示词: "Generate 50 keywords..."
    ↓
Gemini 返回响应
    ↓
parse_keywords() 清洗
    ├─ 过滤 UI 文本
    ├─ ASCII 验证
    ├─ 技术词验证
    └─ 长度验证
    ↓
合并到 explored_keywords.json (44 → 94 个)
    ↓
完成！
```

### 阶段 2: 并行下载

```
用户同时运行三个终端:
  终端1: .\start_vendor_batch1.bat
  终端2: .\start_vendor_batch2.bat
  终端3: .\start_vendor_batch3.bat

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
批次1 (5厂商)          批次2 (5厂商)          批次3 (7厂商)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

读取 explored_keywords.json
    ↓
关键词 1/44: "buck converter datasheet"
    ├─ TI          ├─ NXP         ├─ Vishay
    ├─ ADI         ├─ Microchip   ├─ Diodes
    ├─ ST          ├─ Renesas     ├─ PI
    ├─ Infineon    ├─ MPS         ├─ Navitas
    └─ onsemi      └─ ROHM        ├─ Richtek
                                   ├─ AOS
                                   └─ Vicor
    ↓
搜索: "site:ti.com buck converter datasheet"
    ↓
下载 PDF → downloads_continuous/ti/
    ↓
追加日志 → results.jsonl
    ↓
关键词 2/44: "boost regulator"
    ...
    ↓
44 个关键词全部完成
    ↓
标记到 used_keywords.json
    ↓
3秒后自动重启，等待新关键词
```

### 阶段 3: 关键词补充 (循环)

```
当 used_keywords.json = 44 (全部用完)
    ↓
用户再次运行: .\start_download_only.bat
    ↓
keyword_explorer.py 生成新的 50 个关键词
    ↓
explored_keywords.json: 44 + 50 = 94 个
    ↓
下载批次自动使用新关键词
    ↓
持续循环...
```

---

## 文件说明

### 配置文件

| 文件 | 作用 | 格式 | 更新时机 |
|------|------|------|----------|
| `explored_keywords.json` | 关键词池 | JSON | keyword_explorer.py 运行后 |
| `used_keywords.json` | 已处理关键词 | JSON | 每个关键词完成所有厂商后 |
| `explored_vendors.json` | 厂商域名映射 | JSON | Gemini 生成厂商时 |

**explored_keywords.json 结构**：
```json
{
  "timestamp": "2026-01-28 13:25:29",
  "keywords": [
    "buck converter datasheet",
    "boost regulator",
    "flyback design guide",
    ...
  ],
  "count": 44,
  "new_added": 0
}
```

**used_keywords.json 结构**：
```json
{
  "timestamp": "2026-01-28 13:30:00",
  "used": [
    "buck converter datasheet",
    "boost regulator"
  ],
  "count": 2
}
```

### 日志文件

| 文件 | 作用 | 格式 | 示例 |
|------|------|------|------|
| `results.jsonl` | 下载日志 | JSONL | 每行一个 JSON 对象 |
| `summary.csv` | 统计汇总 | CSV | 可选生成 |

**results.jsonl 示例**：
```json
{"timestamp": "2026-01-28 14:00:00", "vendor": "TI", "title": "LM5176 Datasheet", "url": "https://ti.com/...", "status": "success", "filepath": "downloads_continuous/ti/lm5176.pdf"}
{"timestamp": "2026-01-28 14:00:05", "vendor": "ADI", "title": "LT8312 Datasheet", "url": "https://analog.com/...", "status": "success", "filepath": "downloads_continuous/adi/lt8312.pdf"}
```

### 目录结构

```
downloads_continuous/
├── ti/           # Texas Instruments
├── adi/          # Analog Devices
├── st/           # STMicroelectronics
├── infineon/     # Infineon
├── onsemi/       # ON Semiconductor
├── nxp/          # NXP
├── microchip/    # Microchip
├── renesas/      # Renesas
├── mps/          # Monolithic Power Systems
├── rohm/         # ROHM
├── vishay/       # Vishay
├── diodes/       # Diodes Inc.
├── pi/           # Power Integrations
├── navitas/      # Navitas
├── richtek/      # Richtek
├── aos/          # Alpha & Omega
└── vicor/        # Vicor (未包含在批次中)
```

---

## 资源分配

### 进程分布

| 组件 | 进程数 | 厂商数 | 并发模式 |
|------|--------|--------|----------|
| keyword_explorer.py | 1 | - | 按需运行 |
| batch1 | 1 | 5 | 串行 (关键词→厂商) |
| batch2 | 1 | 5 | 串行 |
| batch3 | 1 | 7 | 串行 |
| **总计** | **3-4** | **17** | **3个进程并行** |

### 厂商分组

**批次 1** (5 个厂商)
- TI (ti.com)
- ADI (analog.com)
- ST (st.com)
- Infineon (infineon.com)
- onsemi (onsemi.com)

**批次 2** (5 个厂商)
- NXP (nxp.com)
- Microchip (microchip.com)
- Renesas (renesas.com)
- MPS (monolithicpower.com)
- ROHM (rohm.com)

**批次 3** (7 个厂商)
- Vishay (vishay.com)
- Diodes (diodes.com)
- PI (power.com)
- Navitas (navitassemi.com)
- Richtek (richtek.com)
- AOS (aosmd.com)
- Vicor (vicorpower.com)

---

## 数据安全

### 1. 去重机制

**文件名 Hash**：
```python
import hashlib
filename_hash = hashlib.md5(filename.encode()).hexdigest()
if os.path.exists(filepath):
    print(f"文件已存在，跳过: {filename}")
    continue
```

**关键词去重**：
```python
# 加载时自动过滤
used_keywords = load_used_keywords()
keywords = [k for k in keywords if k not in used_keywords]
```

### 2. 容错机制

**网络超时**：
```python
try:
    response = requests.get(url, timeout=30)
except requests.Timeout:
    print(f"下载超时: {url}")
    continue
```

**下载失败记录**：
```python
save_result({
    'status': 'failed',
    'error': str(e)
})
```

**自动重启**：
```batch
:loop
python vendor_downloader.py "TI,ADI,ST"
timeout /t 3 /nobreak >nul
goto loop
```

### 3. 备份策略

**自动备份**：
```python
# clean_keywords.py
backup_path = file_path.with_suffix('.json.backup')
with open(backup_path, 'w') as f:
    json.dump(data, f)
```

**手动备份**：
- explored_keywords.json.backup
- used_keywords_backup.json (可选)

---

## 当前状态

### 系统参数

| 指标 | 当前值 | 说明 |
|------|--------|------|
| **关键词池** | 44 个 | 已清理（从 74→44） |
| **已用关键词** | 0 个 | 已清空 |
| **可运行轮次** | 44 轮 | 每轮处理 17 个厂商 |
| **累计下载** | 数千个 | 从文件列表估算 |
| **厂商覆盖** | 17 个 | 全球主流电源 IC 厂商 |

### 文件统计

```
downloads_continuous/ 目录包含:
- 17 个厂商子目录
- 数千个 PDF 文件
- 文件命名包含: 型号、datasheet、application note 等
```

### 性能预估

**单轮时间** (1个关键词 × 17个厂商)：
- 搜索时间: ~3-5秒/厂商 = 51-85秒
- 下载时间: ~0.5秒/PDF × 平均20个 = 10秒/厂商 = 170秒
- 延迟时间: ~2秒/厂商 = 34秒
- **总计**: ~255-289秒 ≈ **4-5分钟/关键词**

**44个关键词完成时间**：
- 44 × 5分钟 = 220分钟 ≈ **3.7小时**

**预期下载量**（理想情况）：
- 44 关键词 × 17 厂商 × 平均20个PDF = **14,960 个 PDF**

---

## 优化建议

### 1. 并发度提升

**当前**：3个进程串行处理厂商
**可选**：每个进程内部并发下载（使用线程池）

```python
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=3) as executor:
    futures = [executor.submit(download_pdf, url) for url in urls[:100]]
```

### 2. 关键词质量

**监控指标**：
- 关键词有效率 = 有结果的搜索 / 总搜索次数
- 平均下载量 = 总下载数 / 关键词数

**优化方向**：
- 分析 results.jsonl，找出高产关键词
- 向 Gemini 反馈：要求更多类似关键词

### 3. 存储优化

**当前问题**：平铺式存储，单个目录文件过多
**改进方案**：
```python
# 按型号首字母分类
vendor_dir / 'L' / 'LM5176.pdf'
vendor_dir / 'T' / 'TPS54560.pdf'

# 或按月份归档
vendor_dir / '2026-01' / 'LM5176.pdf'
```

---

## 常见问题

### Q1: 为什么关键词会连在一起成为超长字符串?

**A**: 
- Gemini 有时会忽略"每行一个"的要求，返回空格分隔的长字符串
- parse_keywords() 已增强：自动检测超过100字符的行并分割
- 如果发现超长关键词，运行 `python reset_keywords.py` 重置到50个初始关键词

### Q2: 为什么不用多线程下载？

**A**: 
- DDG 搜索 API 有频率限制
- 厂商网站可能有反爬虫机制
- 当前设计已足够高效（3进程并行）

### Q2: 关键词用完怎么办？

**A**: 
- 批处理脚本会自动等待（3秒循环）
- 手动运行 `start_download_only.bat` 生成新关键词
- 可设置定时任务自动补充

### Q3: 如何避免下载重复文件？

**A**: 
- 文件名 hash 检查（MD5）
- used_keywords.json 避免重复搜索
- results.jsonl 记录所有下载

### Q4: 某个厂商网站不可用怎么办？

**A**: 
```python
# vendor_downloader.py
SKIP_VENDORS = {'MPS'}  # 添加到跳过列表
```

### Q5: 如何停止下载？

**A**: 
- 在对应终端按 `Ctrl+C`
- 停止所有批次：关闭所有 Python 终端

---

## 维护指南

### 日常操作

**启动下载**：
```powershell
# 终端 1
.\start_vendor_batch1.bat

# 终端 2
.\start_vendor_batch2.bat

# 终端 3
.\start_vendor_batch3.bat
```

**补充关键词**（当用完时）：
```powershell
.\start_download_only.bat
```

**检查进度**：
```powershell
# 查看已用关键词数
python -c "import json; print(len(json.load(open('downloads_continuous/used_keywords.json'))['used']))"

# 查看总关键词数
python -c "import json; print(len(json.load(open('downloads_continuous/explored_keywords.json'))['keywords']))"
```

### 定期维护

**每周**：
- 检查 results.jsonl 大小（可定期归档）
- 清理 Chrome 缓存和日志
- 备份 JSON 配置文件

**每月**：
- 统计下载量和覆盖率
- 分析高产关键词，优化生成策略
- 检查厂商网站是否有变更

### 故障排查

**关键词生成失败**：
1. 检查 Chrome 是否能访问 gemini.google.com
2. 检查 Google 账号登录状态
3. 查看 debug_response.html 和截图

**下载失败率高**：
1. 检查网络连接
2. 增加延迟时间（减少频率）
3. 检查 DDG API 是否正常

**系统卡死**：
1. Ctrl+C 停止所有批次
2. 清理 .venv 缓存
3. 重启批处理脚本

---

## 技术栈

| 组件 | 技术 | 版本 |
|------|------|------|
| Python | 核心语言 | 3.10+ |
| Selenium | 浏览器自动化 | 4.40.0 |
| webdriver-manager | ChromeDriver 管理 | 4.0.2 |
| duckduckgo_search | 搜索 API | - |
| requests | HTTP 下载 | - |
| Chrome | 浏览器 | Latest |

---

## 更新日志

### 2026-01-28
- ✅ 清理 explored_keywords.json (74→44个)
- ✅ 修复 parse_keywords() 过滤逻辑
- ✅ 添加 UI 文本过滤和 ASCII 验证
- ✅ 创建 clean_keywords.py 清理工具
- ✅ 完善系统架构文档

### 2026-01-27
- ✅ 创建 3 批次并行下载脚本
- ✅ 实现 Gemini 关键词生成
- ✅ 添加文件去重机制
- ✅ 配置自动循环批处理

---

## 致谢

本系统设计充分考虑了：
- 可持续性：AI 动态生成，永不枯竭
- 可扩展性：轻松添加新厂商和批次
- 可维护性：清晰的日志和状态追踪
- 可靠性：多层容错和自动恢复

---

**文档版本**: 1.0  
**最后更新**: 2026-01-28  
**维护者**: AI Assistant  
**授权**: 内部使用
