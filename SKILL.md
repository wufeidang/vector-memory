---
name: vector-memory
description: "Semantic memory storage & retrieval with ChromaDB vector embeddings, hybrid search (vector + TF-IDF + reranker), multi-collection isolation, versioning, knowledge chains, backup/restore, automatic summarization, model hot-swap, and incremental backup."
version: "2.5.0"
---

# Vector-Memory

**向量记忆系统** — 语义级记忆存储与检索。基于 ChromaDB + BGE 中文嵌入模型，为 Hermes 提供专业知识库能力。

## 体系定位

| 维度 | Hermes 原生记忆 | Vector-Memory |
|------|----------------|---------------|
| 用途 | AI 记住你的偏好 | **你**存储专业知识 |
| 容量 | ~2,200 字符 | 无限（硬盘） |
| 搜索 | 关键词匹配 | 语义搜索（向量嵌入） |
| 谁控制 | AI 自动管理 | 双向（主动存储 + 自动搜索） |
| 自动注入 | 每次对话 | 对话中自动触发 |
| 文件支持 | ❌ | ✓ PDF/Word/Excel/PPT/图片等 |

**数据目录：** `~/.hermes/vector_store/`（ChromaDB 持久化）

## 依赖安装

```bash
# 1. 创建虚拟环境并安装依赖
cd ~/.hermes/skills/vector-memory
uv venv .venv
.venv/Scripts/python.exe -m ensurepip
.venv/Scripts/python.exe -m pip install chromadb

# 2. 安装 ML 依赖（~2GB，网速慢时需较长等待）
.venv/Scripts/python.exe -m pip install scikit-learn sentence-transformers

# 3. 下载嵌入模型（首次使用自动下载 ~400MB）
.venv/Scripts/python.exe scripts/vector_memory.py stats

# 4. （可选）预加载模型加速
.venv/Scripts/python.exe scripts/preload_models.py
```

> ⚠ **注意**：Windows 环境下 scikit-learn (~150MB)、sentence-transformers (含 torch ~800MB)、ChromaDB ONNX 模型 (~79MB) 以及 BGE 嵌入模型 (~400MB) 均为大规模下载。如果网络速度较慢（<100KB/s），建议在良好网络环境下一次性完成。所有核心集合管理功能（创建/切换/删除集合、关联、备份、导出）无需这些模型即可运行。

## API 参考

所有函数接收 **args 字典参数**（非关键字参数）。

### 添加记忆

| 函数 | 说明 |
|------|------|
| `add_memory({"text": "...", "metadata": {...}})` | 添加单条记忆（长文本自动分块+生成摘要） |
| `add_batch({"texts": [...], "metadatas": [...]})` | 批量添加（自动为长文本生成摘要） |
| `add_with_chunks({"text": "长文本...", "chunk_size": 500, "overlap": 50})` | 自动分块添加（保留父摘要引用） |

### 搜索（支持混合检索）

| 函数 | 说明 |
|------|------|
| `search_memories({"text": "关键词", "top_k": 5})` | 语义搜索（自动向量→TF-IDF→Reranker管道） |
| `search_memories({"text": "...", "use_rrf": True})` | 使用 RRF 融合排序替代线性加权 |
| `search_related({"doc_id": "id1", "limit": 5})` | 查询关联记忆 |
| `rerank_results(query, docs_scores, top_k=5)` | 手动重排序 |

搜索返回格式：`{"success": True, "results": [...], "count": N, "elapsed_ms": X}`，每条 result 含 `id, text, metadata, score, relevance_score`。

### ✨ 混合检索权重配置

默认权重：`vec=0.7, tfidf=0.3`（线性加权），可通过 API 或 CLI 动态调整：

```python
# 动态设置权重
set_hybrid_weights(vec_weight=0.6, tfidf_weight=0.4)

# 启用 RRF（Reciprocal Rank Fusion）替代线性加权
set_hybrid_weights(use_rrf=True)

# 查看当前配置
get_hybrid_weights()
```

**CLI：**
```bash
python vector_memory.py set-weights --vec=0.6 --tfidf=0.4
python vector_memory.py set-weights --rrf=true
```

### 集合管理

| 函数 | 说明 |
|------|------|
| `create_collection({"name": "项目X"})` | 创建集合（隔离记忆） |
| `list_collections()` | 列出所有集合（含记忆条数） |
| `switch_collection({"name": "项目X"})` | 切换当前集合 |
| `delete_collection({"name": "项目X"})` | 删除集合 |
| `get_current_collection()` | 查看当前集合名 |

### 记忆管理

| 函数 | 说明 |
|------|------|
| `list_memories({"limit": 20})` | 列出当前集合记忆 |
| `clear_memories()` | 清空当前集合 |
| `dedupe_memories()` | 去重 |
| `import_from_memory_md()` | 从 Hermes 原生记忆 MEMORY.md 导入 |

### ✨ 记忆摘要（自动生成）

长文本（>500字符）添加时自动提取关键信息作为摘要，存入 `metadata.summary` 字段：

```python
# 添加长文档 → 自动生成摘要
add_memory({"text": "很长的技术文档..."})
# metadata 自动包含: {"summary": "关键句子1。关键句子2。关键句子3。", ...}

# 批量模式也自动生成摘要
add_batch({"texts": [长文本1, 长文本2], "metadatas": [...]})
```

**CLI：**
```bash
# 预览文本摘要
python vector_memory.py summary --text="很长的技术文档..."
python vector_memory.py summary --text="很长的技术文档..." --max_sentences=5
```

### ✨ 嵌入模型热切换

运行时更换嵌入模型并自动触发全量 reindex（重建所有向量）：

```python
# 切换到新模型（自动 reindex 所有集合）
switch_model("BAAI/bge-m3")

# 只 reindex 特定集合
switch_model("BAAI/bge-m3", collection_name="my_knowledge")

# 查看当前模型信息
get_model_info()
```

**CLI：**
```bash
# 查看当前模型
python vector_memory.py model-info

# 切换模型 + 全量 reindex
python vector_memory.py switch-model --model=BAAI/bge-m3

# 切换模型 + 只 reindex 指定集合
python vector_memory.py switch-model --model=BAAI/bge-m3 --collection=my_knowledge
```

**注意事项：**
- 切换过程中旧模型会被安全卸载
- 如果新模型加载失败，自动回退到旧模型
- reindex 逐集合进行，内存友好

### 关联（知识链）

| 函数 | 说明 |
|------|------|
| `link_memory({"from_id": "id1", "to_id": "id2", "relation": "depends_on"})` | 建立关联 |
| `unlink_memory({"from_id": "id1", "to_id": "id2"})` | 移除关联 |
| `get_knowledge_chain({"doc_id": "id1", "depth": 1})` | 获取知识链 |

### 版本 & 过期

| 函数 | 说明 |
|------|------|
| `rollback_memory({"category": "tech", "device": "pc", "version": 0})` | 回滚到指定版本 |
| `get_expired_memories({"half_life_days": 30, "threshold": 0.5})` | 查看过期记忆 |
| `prune_expired_memories({"half_life_days": 30, "threshold": 0.5})` | 清理过期记忆 |

### 备份 & 导出

| 函数 | 说明 |
|------|------|
| `backup_memories()` | 完整向量库备份（自动创建 manifest） |
| `restore_memories({"backup_dir": "path", "dry_run": False})` | 恢复备份（默认 dry_run=True！） |
| `export_memories({"format": "markdown"})` | 导出为 Markdown |
| `list_backups()` | 列出所有备份 |
| `get_stats()` | 系统统计信息 |

### 文件存储

| 函数 | 说明 |
|------|------|
| `store_file({"file_path": "...", "description": "..."})` | 存储文件，自动提取文本 + 语义索引 |
| `list_files({"file_type": "image"})` | 列出文件 |
| `get_file({"file_id": "xxx"})` | 获取文件详情 |
| `delete_file({"file_id": "xxx"})` | 删除文件及索引 |
| `search_files({"text": "关键词"})` | 在文件索引中语义搜索 |
| `get_file_stats()` | 文件存储统计 |

支持 txt/md/csv/pdf/docx/xlsx/pptx 等文档及 png/jpg/gif/bmp/webp 图片。
物理存储：`~/.hermes/files/<collection>/<file_id>/original.ext`
ChromaDB 集合：`files`

### 命令行

基于内容哈希的版本号增量备份，仅备份新增/变更的文档：

```python
# 首次调用自动创建全量备份作为基准
backup_memories_incremental()
# → {"added": 100, "modified": 0, "total": 100, "backup_name": "inc_backup_20260612_194100"}

# 后续调用只备份变更
backup_memories_incremental()
# → {"added": 5, "modified": 2, "total": 7, "backup_name": "inc_backup_20260612_200000"}

# 规划恢复链（全量 + 增量顺序）
restore_incremental()
# → 按顺序列出需要恢复的备份链
```

**CLI：**
```bash
# 增量备份
python vector_memory.py backup-inc

# 查看恢复链
python vector_memory.py restore-inc

# 查看备份状态（全量/增量统计）
python vector_memory.py backup-state
```

### 命令行速查

```bash
cd ~/.hermes/skills/vector-memory/scripts
python vector_memory.py search "海康摄像机掉线"
python vector_memory.py search text="POE供电距离" top_k=10
python vector_memory.py stats
python vector_memory.py list
python vector_memory.py add "今天发现海康DS-2CD系列供电问题..."
python vector_memory.py backup
python vector_memory.py create name=监控知识库
python vector_memory.py switch-model --model=BAAI/bge-m3
python vector_memory.py set-weights --vec=0.6 --tfidf=0.4 --rrf=true
python vector_memory.py summary --text="长文档内容..."
python vector_memory.py backup-inc
python vector_memory.py backup-state
```

### 对话自动调用

当对话涉及以下话题时，**自动执行向量搜索**获取相关上下文：

**触发模式：**
- 用户提到设备型号/品牌 → `search_memories({"text": "型号"})`
- 故障现象描述 → `search_memories({"text": "现象"})`
- 技术参数/经验总结 → 搜索 + 提示「是否保存为记忆？」

**自动保存：**
- 用户分享故障处理步骤 → `add_memory({"text": "步骤"})`
- 具体设备参数 → `add_memory({"text": "参数"})`
- 经验总结 → `add_memory({"text": "经验"})`

**搜索结果融入对话：**
```
用户：海康摄像头画面一直闪怎么办？
助手（自动搜索后）：之前记过类似记录：海康DS-2CD系列画面闪烁，
检查电源适配器输出是否稳定，12V电源老化导致纹波过大。
```

### 已知陷阱

| 陷阱 | 说明 | 正确用法 |
|------|------|---------|
| 字段名不同 | `content` → **`text`** | `result["text"]` |
| 集合名 `memories` 带 s | `_current_collection_name = "memories"` | 不匹配读不到旧数据 |
| ChromaDB 持久化 | 必须用 `PersistentClient` | 默认已用，不要改为内存模式 |
| restore dry_run 默认 True | 不显式传 `dry_run=False` 不会恢复 | `restore_memories({..., "dry_run": False})` |
| backup 自动建 manifest | 不要手动覆盖 manifest.json | 直接读取已创建的 |
| list_collections 返回格式 | 返回 `[{"name":..., "count":N}]` 非字符串列表 | `any(c["name"] == "x" for c in result)` |
| 模型路径检测 | Windows/ModelScope 路径变体 | `_find_downloaded_model()` 自动扫描 |
| Windows 路径归一化 | `~/.hermes` 可能含混合分隔符 | `os.path.abspath()` 自动处理 |
| 增量备份首次运行 | 首次 `backup-inc` 等效于全量备份 | 正常现象，后续才是真正增量 |
| 模型切换 reindex 耗时 | 百级以上文档集可能需数分钟 | 建议在低峰期操作 |

### 文件结构

```
~/.hermes/skills/vector-memory/
├── SKILL.md                    ← 本文件
├── requirements.txt
├── scripts/
├── core.py                 ← 配置 / 模型单例 / TF-IDF / Reranker（线程安全）
├── storage.py              ← 集合管理 / 记忆 CRUD
├── search.py               ← 搜索管道：向量 → TF-IDF → Reranker
├── management.py           ← 关联 / 版本 / 过期 / 备份 / 导出
├── file_storage.py         ← 文件/图片存储、文本提取、语义索引
├── vector_memory.py        ← 主入口 + CLI
│   ├── preload_models.py       ← 模型预加载
│   ├── backup_memory.py        ← 自动化备份脚本
│   ├── memory_monitor.py       ← 性能监控
│   ├── sync_memory_reliable.py ← 可靠同步
│   └── test_vector_memory.py   ← 单元测试
└── references/
    ├── memory-architecture-native-vs-vector.md
    ├── memory-system-architecture.md
    ├── automation-scripts.md
    └── integration-plan.md
```