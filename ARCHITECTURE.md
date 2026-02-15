# DC-DC Datasheet 下载工具 - 系统架构

## 系统架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                     DC-DC Datasheet Fetcher                          │
│                     命令行入口 (CLI)                                  │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     参数解析 (argparse)                               │
│  • 输入选项: --query, --queries, --vendor, --keywords                │
│  • 过滤选项: --filetypes, --only-whitelist, --max-results           │
│  • 行为选项: --sleep, --timeout, --debug                            │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     主控制器 (DDGFetcher)                            │
│  • 构建查询列表                                                       │
│  • 协调搜索、过滤、下载                                               │
│  • 状态跟踪与去重                                                     │
│  • 结果汇总与统计                                                     │
└───────────┬─────────────┬─────────────┬──────────────────────────────┘
            │             │             │
            ▼             ▼             ▼
    ┌───────────┐ ┌───────────┐ ┌──────────────┐
    │ 搜索器    │ │ 下载器    │ │ 输出管理器    │
    │ Searcher  │ │ Downloader│ │ Output       │
    └─────┬─────┘ └─────┬─────┘ └──────┬───────┘
          │             │               │
          ▼             ▼               ▼
    ┌──────────┐  ┌──────────┐  ┌─────────────┐
    │ DDG API  │  │ HTTP     │  │ 文件系统    │
    │          │  │ Session  │  │             │
    └──────────┘  └──────────┘  └─────────────┘
```

## 数据流图

```
用户输入
   │
   ├─ --query "..."
   ├─ --queries file.txt
   └─ --vendor + --keywords
   │
   ▼
查询构建
   │
   ├─ 单条查询
   ├─ 多条查询（文件）
   └─ 自动生成（site: + keywords）
   │
   ▼
搜索阶段 (DDGSearcher)
   │
   ├─ 调用 DuckDuckGo API
   ├─ 解析搜索结果
   └─ 返回 [{title, url, body}, ...]
   │
   ▼
过滤阶段 (DDGFetcher.filter_url)
   │
   ├─ 域名白名单检查
   ├─ URL 去重检查
   ├─ 文件类型判断
   └─ 返回 (保留?, 类型, 原因)
   │
   ▼
下载阶段 (Downloader)
   │
   ├─ HEAD 请求预检
   │   ├─ Content-Type 检查
   │   └─ Content-Length 检查
   │
   ├─ GET 请求下载
   │   ├─ 流式写入文件
   │   ├─ 重试机制（指数退避）
   │   └─ 超时保护
   │
   └─ 文件验证
       ├─ 大小检查
       └─ 魔数检查
   │
   ▼
归档阶段
   │
   ├─ 生成文件路径
   │   ├─ 识别供应商（从域名）
   │   ├─ 生成安全文件名
   │   └─ 处理文件名冲突
   │
   ├─ 保存文件
   │   └─ downloads/vendor/filename.pdf
   │
   └─ 记录日志
       ├─ JSONL 追加写入
       └─ CSV 汇总
   │
   ▼
输出结果
   │
   ├─ 控制台统计
   ├─ results.jsonl（详细日志）
   └─ summary.csv（汇总表）
```

## 类图

```
┌─────────────────────────────────────────────────┐
│              DDGSearcher                         │
├─────────────────────────────────────────────────┤
│ - logger: Logger                                 │
│ - sleep_interval: float                          │
├─────────────────────────────────────────────────┤
│ + search(query, max_results) → List[Dict]       │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│              Downloader                          │
├─────────────────────────────────────────────────┤
│ - logger: Logger                                 │
│ - timeout: int                                   │
│ - session: requests.Session                      │
├─────────────────────────────────────────────────┤
│ + head_request(url) → Response                   │
│ + download_file(url, path, type) → (bool, str)  │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│              DDGFetcher                          │
├─────────────────────────────────────────────────┤
│ - args: Namespace                                │
│ - logger: Logger                                 │
│ - searcher: DDGSearcher                          │
│ - downloader: Downloader                         │
│ - downloaded_urls: Set[str]                      │
│ - downloaded_files: Set[Path]                    │
│ - results: List[Dict]                            │
├─────────────────────────────────────────────────┤
│ + build_queries() → List[str]                    │
│ + filter_url(url) → (bool, str, str)            │
│ + generate_filepath(...) → Path                  │
│ + process_search_result(...)                     │
│ + run() → int                                    │
│ + print_statistics()                             │
└─────────────────────────────────────────────────┘
```

## 状态机图

```
[开始]
   │
   ▼
[初始化]
   │ 创建组件（Searcher, Downloader）
   │ 加载配置（白名单、参数）
   ▼
[构建查询]
   │ 单条查询 / 文件查询 / 自动生成
   ▼
[搜索循环] ◄─────┐
   │             │
   ├─ 执行搜索   │
   │             │
   ├─ 解析结果   │
   │             │
   └─ 下一个查询─┘
   │
   ▼
[处理结果] ◄─────┐
   │             │
   ├─ 过滤 URL   │
   │   ├─ 通过 → 下载
   │   └─ 拒绝 → 跳过
   │             │
   ├─ 下载文件   │
   │   ├─ 成功 → 归档
   │   └─ 失败 → 记录错误
   │             │
   └─ 下一个结果─┘
   │
   ▼
[保存结果]
   │ 写入 JSONL
   │ 写入 CSV
   ▼
[打印统计]
   │ 总计/成功/失败
   │ 失败原因分类
   ▼
[结束]
```

## 错误处理流程

```
网络请求
   │
   ├─ 超时？ ───────────┐
   ├─ DNS 失败？ ────────┤
   ├─ 连接拒绝？ ────────┤ → [重试] ──┐
   ├─ SSL 错误？ ────────┤            │
   └─ 其他异常？ ────────┘            │
                                      │
                    ┌─────────────────┘
                    │
                    ▼
               [指数退避]
                    │
                    ├─ 重试次数 < MAX？
                    │   └─ 是 → 等待 2^n 秒 → 重试
                    │
                    └─ 否 → 记录失败
                              │
                              ▼
                         [写入日志]
                              │
                              └─ 继续下一个
```

## 文件组织结构

```
downloads/
├── ti/                      # Texas Instruments
│   ├── LM2596_datasheet.pdf
│   ├── SLVA123_app_note.pdf
│   └── ...
├── st/                      # STMicroelectronics
│   ├── PM6673_eval_guide.pdf
│   └── ...
├── analog/                  # Analog Devices
│   ├── LTC3780_ref_design.zip
│   └── ...
├── unknown/                 # 未识别供应商
│   └── generic_datasheet.pdf
├── results.jsonl            # 详细日志
│   ├── {"timestamp": "...", "status": "success", ...}
│   ├── {"timestamp": "...", "status": "failed", ...}
│   └── ...
└── summary.csv              # 汇总表
    └── timestamp,query,title,url,status,...
```

## 配置数据结构

```python
# 域名白名单
VENDOR_DOMAINS = {
    "ti": ["ti.com", "www.ti.com"],
    "st": ["st.com", "www.st.com"],
    # ...
}

# 文件魔数
FILE_MAGIC_NUMBERS = {
    "pdf": [b"%PDF-1."],
    "zip": [b"PK\x03\x04", b"PK\x05\x06"],
}

# HTTP 配置
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 ...",
    "Accept": "...",
}

# 重试配置
MAX_RETRIES = 3
INITIAL_BACKOFF = 2
MAX_BACKOFF = 60

# 文件大小限制
MIN_FILE_SIZE = 1024         # 1KB
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB
```

## 日志记录结构

```json
{
  "timestamp": "2026-01-26 10:30:45",
  "query": "site:ti.com buck converter datasheet",
  "title": "LM2596 Step-Down Converter Datasheet",
  "url": "https://www.ti.com/lit/ds/symlink/lm2596.pdf",
  "filetype": "pdf",
  "filepath": "downloads/ti/LM2596_datasheet.pdf",
  "status": "success",
  "error": null
}
```

## 性能优化点

```
1. URL 去重 (Set)
   - 避免重复下载
   - O(1) 查找复杂度

2. 流式下载 (iter_content)
   - 内存占用小
   - 支持大文件

3. HEAD 预检
   - 提前检测 Content-Type
   - 避免下载错误文件

4. Session 复用
   - 连接池
   - 减少 SSL 握手

5. 即时写入 JSONL
   - 防止崩溃丢失数据
   - 支持实时监控
```

## 扩展点

```
1. 搜索引擎
   - 添加 GoogleSearcher
   - 添加 BingSearcher
   - 结果聚合去重

2. 下载器
   - 多线程下载
   - 代理池支持
   - 浏览器自动化

3. 过滤器
   - AI 相关性评分
   - 更多文件类型
   - 自定义规则

4. 存储
   - 数据库集成
   - 云存储支持
   - 元数据提取

5. 用户界面
   - Web 管理面板
   - API 服务
   - 进度条集成
```

---

**说明**: 本文档描述了系统的整体架构和设计思路，便于理解和扩展。
