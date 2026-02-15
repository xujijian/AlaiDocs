# Google 搜索引擎使用指南

## 📝 概述

已将搜索引擎从 DuckDuckGo 切换到 Google。Google 搜索通常能提供更准确、更全面的技术文档搜索结果。

## 🔧 安装依赖

首先需要安装 `googlesearch-python` 库：

```bash
pip install googlesearch-python
```

或者使用项目虚拟环境：

```bash
.\.venv\Scripts\Activate.ps1
pip install googlesearch-python
```

## 📁 新增文件

1. **google_fetcher.py** - Google 搜索引擎适配器
   - 实现了与 `ddg_fetcher_browser.py` 相同的接口
   - 支持自动搜索、下载、供应商分类
   - 使用 Chrome 浏览器自动化下载

2. **test_google_fetcher.py** - 测试脚本
   - 快速验证 Google 搜索功能

## 🔄 修改的文件

### 1. continuous_searcher.py

- 优先使用 `GoogleFetcher`，如果不可用则回退到 `DDGFetcher`
- 修改了导入逻辑，支持多搜索引擎
- 更新了 `_process_single_keyword()` 方法

```python
# 优先级: Google > DuckDuckGo Browser > DuckDuckGo
try:
    from google_fetcher import GoogleFetcher
    USE_GOOGLE = True
except ImportError:
    USE_GOOGLE = False
    # 回退到 DuckDuckGo
```

### 2. continuous_search_config.json

添加了搜索引擎配置项：

```json
{
    "search_engine": {
        "type": "google",
        "comment": "搜索引擎类型: google 或 duckduckgo"
    }
}
```

## 🚀 使用方法

### 方式 1: 直接运行持续搜索器（推荐）

```bash
python continuous_searcher.py
```

系统会自动使用 Google 搜索引擎。

### 方式 2: 使用批处理脚本

```bash
.\start_continuous.bat
```

### 方式 3: 测试 Google 搜索功能

```bash
python test_google_fetcher.py
```

### 方式 4: 命令行直接使用 Google 搜索

```bash
python google_fetcher.py "TPS54620 datasheet filetype:pdf" -o ./downloads -r 20 -d 10
```

参数说明：
- `-o, --output`: 输出目录
- `-r, --results`: 搜索结果数量
- `-d, --downloads`: 下载数量限制
- `--visible`: 显示浏览器窗口（调试用）
- `--debug`: 调试模式

## 📊 功能特性

### Google 搜索优势

1. **更准确的结果** - Google 的搜索算法更成熟
2. **更全面的索引** - 覆盖更多技术文档网站
3. **更好的 PDF 过滤** - `filetype:pdf` 支持良好
4. **支持 site: 操作符** - 可以限定供应商域名搜索

### 已实现功能

- ✅ Google 搜索 API 集成（通过 googlesearch-python）
- ✅ 自动化浏览器下载（Chrome WebDriver）
- ✅ 供应商域名白名单过滤
- ✅ 自动文件分类（按供应商）
- ✅ 下载统计和报告
- ✅ 错误处理和重试
- ✅ 上下文管理器支持

## ⚠️ 注意事项

### 1. 搜索频率限制

Google 可能会限制频繁搜索，建议：
- 在配置中设置合理的 `round_interval`（轮次间隔）
- 默认每次搜索间隔 2 秒
- 避免短时间内大量查询

### 2. 网络访问

确保可以访问 Google：
- 中国大陆用户可能需要配置代理
- 可以在环境变量或系统设置中配置代理

### 3. Chrome 浏览器

需要安装 Chrome 浏览器：
- 系统会自动下载匹配的 ChromeDriver
- 首次运行可能需要较长时间（下载驱动）

### 4. 无头模式

默认使用无头模式（`headless=true`）：
- 浏览器在后台运行，不显示窗口
- 调试时可以设置 `--visible` 参数查看浏览器操作

## 🔄 切换回 DuckDuckGo

如果需要切换回 DuckDuckGo：

### 方法 1: 卸载 googlesearch-python

```bash
pip uninstall googlesearch-python
```

系统会自动回退到 DuckDuckGo。

### 方法 2: 修改配置文件

在 `continuous_search_config.json` 中：

```json
{
    "search_engine": {
        "type": "duckduckgo"
    }
}
```

然后修改 `continuous_searcher.py` 的导入逻辑，强制使用 DDG。

## 📋 配置示例

### 完整配置（使用 Google）

```json
{
    "search_engine": {
        "type": "google"
    },
    "search": {
        "results_per_keyword": 20,
        "max_downloads_per_keyword": 10,
        "round_interval": 300
    },
    "gemini": {
        "headless": true,
        "response_timeout": 90
    }
}
```

## 🧪 测试结果验证

运行测试后，检查：

1. **测试输出目录**: `./test_google_downloads/`
2. **供应商分类**: 文件应该按供应商名称分类到子目录
3. **日志输出**: 确认搜索和下载过程正常

## 🐛 故障排除

### 问题 1: "googlesearch-python 库未安装"

```bash
pip install googlesearch-python
```

### 问题 2: Chrome 驱动下载失败

手动安装 ChromeDriver:
```bash
pip install --upgrade webdriver-manager
```

### 问题 3: 搜索结果为空

- 检查网络连接
- 确认可以访问 Google
- 尝试使用 `--visible` 参数查看浏览器操作
- 检查查询语法是否正确

### 问题 4: 下载失败

- 检查输出目录权限
- 确认 PDF URL 可访问
- 查看详细错误日志（使用 `--debug`）

## 📈 性能对比

| 特性 | Google | DuckDuckGo |
|------|--------|------------|
| 搜索准确性 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 索引覆盖 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| 搜索速度 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 反爬限制 | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| 无需代理 | ❌ (中国) | ✅ |

## 💡 最佳实践

1. **首次使用** - 使用 `test_google_fetcher.py` 验证功能
2. **生产环境** - 设置合理的 `round_interval` 避免被限制
3. **调试模式** - 使用 `--visible --debug` 查看详细过程
4. **定期检查** - 监控下载统计，调整搜索策略

## 📚 相关文档

- [Google 搜索运算符](https://support.google.com/websearch/answer/2466433)
- [googlesearch-python 文档](https://pypi.org/project/googlesearch-python/)
- [Selenium 文档](https://selenium-python.readthedocs.io/)

## 🔗 相关文件

- [google_fetcher.py](google_fetcher.py) - Google 搜索器实现
- [continuous_searcher.py](continuous_searcher.py) - 持续搜索主程序
- [continuous_search_config.json](continuous_search_config.json) - 配置文件
- [test_google_fetcher.py](test_google_fetcher.py) - 测试脚本

---

**更新日期**: 2026-01-27  
**版本**: 1.0.0
