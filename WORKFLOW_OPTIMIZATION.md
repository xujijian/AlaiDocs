# 知识库工作流优化方案

## 当前流程
```
用户查询 → axis_pdf_tool.py 检索 → 手动选择文件 → NotebookLM 分析
```

## 痛点
1. 🔴 **手动操作多** - 需要手动复制文件到 NotebookLM
2. 🔴 **NotebookLM 限制** - 文件数量/大小有限制（通常 50 个文件）
3. 🔴 **跨语言检索弱** - 中文查询英文文档效果差
4. 🔴 **缺少上下文** - 每次都是独立查询，没有对话历史

---

## 优化方案

### 方案 A：本地 RAG 系统（推荐）
**原理：** 不依赖 NotebookLM，本地完成检索+分析

**优势：**
- ✅ 自动化：查询直接返回答案
- ✅ 无限制：可以检索整个知识库
- ✅ 对话式：支持多轮对话，有上下文
- ✅ 可定制：调整检索策略、提示词等

**实现：**
```python
# 工作流
查询 → 检索相关chunks → 送给Gemini生成答案
      ↓
    (自动翻译中文查询)
```

**所需：**
- Gemini API（你已有）
- 现有知识库（kb.sqlite + kb.faiss）
- 自动翻译模块（可选）

---

### 方案 B：智能文件打包器
**原理：** 自动筛选最相关的文件并打包，方便传给 NotebookLM

**优势：**
- ✅ 保留 NotebookLM 的优势（多源综合分析）
- ✅ 自动化选择：不需手动挑文件
- ✅ 智能去重：避免相似文档重复
- ✅ 优先级排序：最相关的文件优先

**实现：**
```python
# 工作流
查询 → 检索+打分+去重 → 生成文件清单 → 打包到临时目录
                        ↓
                    显示文件列表 + 打包路径
```

---

### 方案 C：混合模式
**原理：** 快速答案 + 深度分析

**流程：**
1. **快速回答**（本地 RAG）- 几秒内给出基本答案
2. **深度分析**（NotebookLM）- 如需要，自动打包文件供 NotebookLM 分析

**优势：**
- ✅ 效率高：大部分问题本地秒答
- ✅ 深度好：复杂问题可用 NotebookLM
- ✅ 灵活性：用户自主选择模式

---

## 具体改进点

### 1. 自动中英翻译
```python
# 检测查询语言，自动翻译
if is_chinese(query):
    en_query = translate_zh_to_en(query)  # Google Translate API
    results = search(en_query)
else:
    results = search(query)
```

### 2. 混合检索（提升准确度）
```python
# 结合关键词 + 语义向量
keyword_results = fts5_search(query)    # 精确匹配
vector_results = faiss_search(query)     # 语义相似
final_results = rerank(keyword_results + vector_results)
```

### 3. 智能文件选择
```python
# 去重 + 多样性
selected = []
for doc in ranked_docs:
    if not too_similar_to(doc, selected):  # 避免重复
        selected.append(doc)
        if len(selected) >= 20:  # 限制数量
            break
```

### 4. 自动生成摘要
```python
# 为每个文档生成摘要，加速理解
for doc in selected_docs:
    summary = summarize(doc.chunks[:5])  # 前5段
    doc.summary = summary
```

---

## 推荐实施顺序

1. **立即实施**（1小时）
   - 添加自动翻译
   - 改进检索结果展示

2. **短期实施**（半天）
   - 实现方案B：智能文件打包器
   - 集成到现有 axis_pdf_tool.py

3. **长期优化**（1-2天）
   - 实现方案A：完整的本地RAG系统
   - 添加对话历史、多轮问答

---

## 需要我实现哪个方案？

**最快见效：** 方案B（智能打包器）+ 自动翻译
**最强大：** 方案A（本地RAG系统）
**最实用：** 方案C（混合模式）

我可以根据你的需求实现任何一个方案。你倾向于哪个？
