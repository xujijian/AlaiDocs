# 搜索引擎切换到 Google - 更新说明

**日期**: 2026-01-27  
**版本**: v2.1.0

## 🎯 主要更新

已成功将搜索引擎从 **DuckDuckGo** 切换到 **Google**。

## 📦 新增文件

1. **google_fetcher.py** - Google 搜索引擎适配器
2. **test_google_fetcher.py** - Google 搜索测试脚本
3. **GOOGLE_SEARCH_GUIDE.md** - 详细使用指南
4. **setup_google.bat** - 快速设置脚本

## 🔧 修改文件

1. **continuous_searcher.py** - 集成 Google 搜索引擎
2. **continuous_search_config.json** - 添加搜索引擎配置
3. **requirements.txt** - 添加 googlesearch-python 依赖

## 🚀 快速开始

### 步骤 1: 安装依赖

```bash
# 方式 1: 使用快速设置脚本（推荐）
.\setup_google.bat

# 方式 2: 手动安装
pip install googlesearch-python
```

### 步骤 2: 测试功能

```bash
python test_google_fetcher.py
```

### 步骤 3: 正常使用

```bash
python continuous_searcher.py
# 或
.\start_continuous.bat
```

## ⚙️ 配置说明

在 `continuous_search_config.json` 中已添加：

```json
{
    "search_engine": {
        "type": "google",
        "comment": "搜索引擎类型: google 或 duckduckgo"
    }
}
```

## 🔄 回退方案

如果需要切换回 DuckDuckGo：

```bash
pip uninstall googlesearch-python
```

系统会自动回退到 DuckDuckGo。

## ⚠️ 注意事项

1. **网络访问**: 需要能访问 Google（中国大陆可能需要代理）
2. **搜索限制**: Google 可能限制频繁搜索，建议设置合理的间隔
3. **Chrome 浏览器**: 需要安装 Chrome（系统会自动下载驱动）

## 📚 详细文档

请查看 [GOOGLE_SEARCH_GUIDE.md](GOOGLE_SEARCH_GUIDE.md) 获取：
- 完整使用说明
- 配置选项
- 故障排除
- 性能对比

## ✅ 测试验证

已测试的功能：
- ✅ Google 搜索 API 集成
- ✅ 自动浏览器下载
- ✅ 供应商域名过滤
- ✅ 文件自动分类
- ✅ 错误处理

## 💡 优势

相比 DuckDuckGo，Google 搜索提供：
- 更准确的搜索结果
- 更全面的索引覆盖
- 更好的技术文档支持
- 更强大的搜索运算符

---

如有问题，请查看 [GOOGLE_SEARCH_GUIDE.md](GOOGLE_SEARCH_GUIDE.md) 或查看日志输出。
