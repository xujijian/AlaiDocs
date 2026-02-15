# 智能文件打包器 - 快速开始

## 安装依赖

```powershell
# 在 axis-SQLite 环境中安装
cd D:\E-BOOK\axis-SQLite
.\.venv\Scripts\activate
pip install deep-translator
```

如果已有 sentence-transformers 和 faiss-cpu，跳过此步。

---

## 使用方法

### 方式1: 双击运行
```
双击 smart_pack.bat
```

### 方式2: 命令行
```powershell
cd D:\E-BOOK\axdcdcpdf
.\smart_pack.bat
```

---

## 使用示例

### 示例1: 中文查询（自动翻译）
```
> 降压转换器的热管理设计

🔍 检测语言: 中文
🌐 翻译: 降压转换器的热管理设计 → buck converter thermal management design
📚 关键词搜索... 找到 45 个结果
🧠 语义搜索... 找到 38 个结果

✅ 找到 58 个相关文档
📦 智能选择了 20 个文档

打包这 20 个文件到 NotebookLM 目录? (y/n): y

✅ 成功打包 20 个文件
📁 输出目录: D:\E-BOOK\axdcdcpdf\packed_for_notebooklm
```

### 示例2: 英文查询
```
> GaN power stage efficiency optimization

🔍 检测语言: 英文
📚 关键词搜索... 找到 32 个结果
🧠 语义搜索... 找到 28 个结果

✅ 找到 45 个相关文档
📦 智能选择了 20 个文档
```

---

## 输出说明

打包后会生成：
- `packed_for_notebooklm/` 目录
  - `01_xxx.pdf` - 按相关度排序的文件
  - `02_xxx.pdf`
  - ...
  - `20_xxx.pdf`
  - `manifest.txt` - 文件清单（包含查询、来源、相关度）

---

## 特性

### 1. 自动翻译
- ✅ 检测中文查询
- ✅ 自动翻译成英文
- ✅ 使用 Google Translate API（免费）

### 2. 混合检索
- ✅ 关键词精确匹配（FTS5）
- ✅ 语义相似搜索（FAISS）
- ✅ 结果合并和去重

### 3. 智能选择
- ✅ 按相关度排序
- ✅ 多样性保证（不同厂商/类型）
- ✅ 自动去重
- ✅ 限制20个文件（NotebookLM友好）

### 4. 便捷打包
- ✅ 文件序号命名
- ✅ 生成清单文件
- ✅ 一键复制所有文件

---

## 常见问题

### Q: 翻译失败怎么办？
A: 会自动使用原文查询，不影响使用。可能需要科学上网。

### Q: 没有FAISS怎么办？
A: 自动降级为纯关键词搜索，效果稍差但可用。

### Q: 能改变文件数量吗？
A: 修改 `smart_pack.py` 中的 `max_docs = 20` 参数。

### Q: 输出目录在哪？
A: `D:\E-BOOK\axdcdcpdf\packed_for_notebooklm\`

---

## 下一步

打包完成后：
1. 打开 [NotebookLM](https://notebooklm.google.com)
2. 创建新笔记本
3. 上传 `packed_for_notebooklm` 目录中的所有PDF
4. 开始分析！

---

## 高级用法

### 调整相关度阈值
编辑 `smart_pack.py`，修改：
```python
# 只保留相关度 > 0.5 的文档
selected = [r for r in results if r['score'] > 0.5]
```

### 自定义输出目录
```python
output_dir = Path(r"D:\MyNotebookLM\{query}")
```

### 批量查询
创建 `queries.txt`，每行一个查询，修改脚本循环处理。
