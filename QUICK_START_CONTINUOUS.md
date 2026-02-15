# 🚀 持续搜索系统 - 快速开始指南

## 30秒快速开始

### 1️⃣ 安装依赖

```bash
pip install selenium webdriver-manager duckduckgo-search
```

### 2️⃣ 运行测试

```bash
python test_continuous.py
```

### 3️⃣ 启动系统

**Windows:**
```bash
start_continuous.bat
```

**Linux/Mac:**
```bash
chmod +x start_continuous.sh
./start_continuous.sh
```

### 4️⃣ 首次登录 ChatGPT

程序会打开浏览器，按提示登录 ChatGPT，然后按 Enter 继续。

### 5️⃣ 自动运行

系统会自动循环：
```
生成关键词 → 搜索 → 下载 → 分析 → 生成新关键词 → ...
```

## 📁 文件说明

| 文件 | 说明 |
|------|------|
| `integrated_searcher.py` | ⭐ 主程序 |
| `chatgpt_keyword_generator.py` | ChatGPT 关键词生成器 |
| `keyword_manager.py` | 关键词管理和统计 |
| `continuous_search_config.json` | 配置文件 |
| `start_continuous.bat/sh` | 启动脚本 |
| `test_continuous.py` | 测试脚本 |

## ⚙️ 重要配置

编辑 `continuous_search_config.json`:

```json
{
  "keywords": {
    "per_round": 10,          // 每轮生成关键词数
    "focus_areas": [          // 关注领域（可修改）
      "DC-DC converter",
      "buck converter",
      ...
    ]
  },
  
  "loop_control": {
    "max_rounds": 0,          // 0 = 无限运行
    "round_interval_seconds": 300  // 轮次间隔5分钟
  },
  
  "limits": {
    "total_size_gb": 50,      // 下载50GB后自动停止
    "total_files": 5000       // 下载5000个文件后停止
  }
}
```

## 🎯 运行模式

### 无限运行（默认）
```bash
start_continuous.bat
```

### 运行指定轮数
```bash
start_continuous.bat --rounds 10
```

### 每轮生成更多关键词
```bash
start_continuous.bat --keywords-per-round 20
```

### 调试模式
```bash
start_continuous.bat --debug
```

## 📊 查看进度

### 实时显示
- 当前轮数
- 正在处理的关键词
- 下载进度
- 累计统计

### 文件位置
- **下载文件**: `downloads_continuous/`
- **关键词数据库**: `keywords.json`
- **运行状态**: `downloads_continuous/search_state.json`

### 统计信息
每5轮自动显示：
- 效果最好的关键词 Top 10
- 最近使用的关键词
- 总下载量统计

## ⏸️ 停止与恢复

### 停止
按 `Ctrl + C` 安全停止，状态会自动保存。

### 恢复
再次运行启动脚本，会从上次位置继续。

## 🎨 自定义关注领域

修改配置文件中的 `focus_areas`:

```json
"focus_areas": [
  "automotive DC-DC converter",
  "medical power supply",
  "USB PD controller",
  "wireless charging",
  "solar MPPT",
  "battery management",
  "motor driver IC",
  "LED driver",
  // ... 添加你感兴趣的领域
]
```

## 🔧 高级选项

### 使用自定义配置
```bash
python integrated_searcher.py --config my_config.json
```

### 指定输出目录
```bash
python integrated_searcher.py --output my_downloads
```

### 不使用浏览器版（更快但可能被限制）
```bash
python integrated_searcher.py --no-browser
```

## ❓ 常见问题

### Q: ChatGPT 要付费吗？
A: 免费账号即可，ChatGPT Plus会更快。

### Q: 需要一直开着浏览器吗？
A: 首次登录后，可以将配置改为 `"headless": true` 后台运行。

### Q: 会重复下载吗？
A: 不会，系统会自动：
- 去重已使用的关键词
- 跳过已存在的文件

### Q: 下载很慢怎么办？
A: 可以：
- 增加每轮关键词数
- 减少轮次间隔
- 使用多个实例并行运行

### Q: 如何添加新供应商？
A: 编辑 `ddg_fetcher.py` 或 `ddg_fetcher_browser.py` 中的 `VENDOR_DOMAINS`。

## 📈 效果优化建议

### 1. 初期快速积累
```json
{
  "keywords": {"per_round": 20},
  "loop_control": {"round_interval_seconds": 180}
}
```

### 2. 后期精细化
```json
{
  "keywords": {"per_round": 5},
  "loop_control": {"round_interval_seconds": 600}
}
```

### 3. 定向领域深挖
```json
{
  "focus_areas": [
    "TI buck converter",
    "Analog Devices LDO",
    "ST motor driver"
  ]
}
```

## 📚 更多文档

- `README_CONTINUOUS.md` - 完整文档
- `README_PROJECT.md` - 项目总览
- `USAGE_EXAMPLES.md` - 使用示例

## 🎉 开始使用

```bash
# 测试
python test_continuous.py

# 运行
start_continuous.bat
```

**就这么简单！系统会自动为你收集大量 DC-DC 资料。** 🚀
