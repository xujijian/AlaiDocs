# 关键词和厂商探索器使用说明

## 新的工作流程

### 第一步：探索关键词和厂商
运行 `start_download_only.bat`，它会启动 Gemini 探索器：

```bash
.\start_download_only.bat
```

程序会询问：
1. **探索模式**：选择探索关键词、厂商或全部
2. **无头模式**：首次使用建议选 `n`（可见浏览器），后续可用 `y`

Gemini 会自动生成：
- **50+ 搜索关键词**：各种电源拓扑、技术参数、应用场景
- **30+ 厂商网站**：全球主要电源芯片厂商，包括中国、日本、韩国厂商

生成的文件：
- `downloads_continuous/explored_keywords.json` - 探索的关键词
- `downloads_continuous/explored_vendors.json` - 探索的厂商

### 第二步：批量下载
在 **3个终端** 同时运行，使用探索得到的关键词和厂商：

**终端1**：
```bash
.\start_vendor_batch1.bat
```

**终端2**：
```bash
.\start_vendor_batch2.bat
```

**终端3**：
```bash
.\start_vendor_batch3.bat
```

这三个批处理会：
1. 自动加载 Gemini 探索的关键词和厂商
2. 分工下载不同厂商（避免重复）
3. 使用扩展后的关键词列表（50+ 个而非原来的10个）

## 优势

### 智能探索
- **动态关键词**：Gemini 根据最新技术趋势生成关键词
- **厂商扩展**：自动发现新厂商和中国本土品牌
- **持续优化**：可以定期重新探索，获取新关键词

### 高效下载
- **3倍速度**：3个终端并行下载
- **不重复**：每个终端负责不同厂商
- **自动适应**：使用探索的数据，如果没有则使用默认配置

## 示例输出

### 关键词探索
```
high voltage buck converter
automotive grade power management
battery charging controller
synchronous rectification
soft start power supply
current mode control
digital power management
...（共50+个）
```

### 厂商探索
```
圣邦微: sgmicro.com
矽力杰: silergy.com
芯朋微: chipown.com.cn
立锜: richtek.com
Torex: torexsemi.com
...（共30+个）
```

## 注意事项

1. **首次探索**：建议使用可见浏览器模式（不选无头），以便登录 Gemini
2. **探索时间**：每次探索约需 2-5 分钟
3. **文件保留**：探索文件会被保存，下次启动自动加载
4. **重新探索**：可以随时重新运行 `start_download_only.bat` 更新关键词和厂商
