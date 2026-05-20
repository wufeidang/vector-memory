---
name: vector_memory
description: Semantic memory storage & retrieval with vector embedding, hybrid search, multi-collection, backup/restore.
category: memory
---

## 功能概览

| 功能 | 说明 |
|------|------|
| 向量搜索 + TF-IDF 混排 | bge-base-zh-v1.5 嵌入 → TF-IDF 后排序 → bge-reranker-v2-m3 重排序 |
| 多集合隔离 | create/switch/delete/list 集合 |
| 版本管理 / 回滚 | 基于 category+device 匹配，自动保留版本历史 |
| 记忆过期衰减 | 指数衰减（30天半衰期），长期未访问降权 |
| 知识链（关联） | link/unlink/get_knowledge_chain/search_related，独立 JSON 存储 |
| 导出/备份/恢复 | JSON/Markdown 导出，完整向量库备份与恢复 |
| 0-100 相关性评分 | sigmoid 映射 |
| 增量 TF-IDF | 文档增长 >50% 时全量重训练，日常仅 transform |
| 模型预加载 | 可选在 Hermes 启动时加载模型到内存（preload_models.py） |
| Web UI | Flask 搜索界面，模型预加载后搜索 0.5-0.7s |

## 架构

```
scripts/
├── core.py          ← 配置 / 模型单例 / TF-IDF / Reranker（线程安全锁）
├── storage.py       ← 集合管理 / 记忆 CRUD（add/list/clear/dedupe）
├── search.py        ← 搜索管道：向量 → 增量 TF-IDF → Reranker
├── management.py    ← 关联 / 版本 / 过期 / 备份 / 导出
└── vector_memory.py ← 主入口（导入4模块 + 命令行接口）
```

所有日志输出到 **stderr**，stdout 仅返回搜索结果。

## 依赖模型

| 模型 | 用途 | 来源 |
|------|------|------|
| AI-ModelScope/bge-base-zh-v1.5 | 嵌入（768维） | ModelScope |
| AI-ModelScope/bge-reranker-v2-m3 | 重排序 | ModelScope |

安装：`pip install chromadb sentence-transformers torch numpy scikit-learn modelscope watchdog flask`

## API 速查

```python
# 添加
add_memory({"text": "...", "metadata": {"category": "tech"}})
add_batch({"texts": ["a","b"], "metadatas": [{"k":"v"}, {}]})
add_with_chunks({"text": "长文本...", "chunk_size": 500, "overlap": 50})

# 搜索
search_memories({"text": "关键词", "top_k": 5, "where": {"category": "tech"}})

# 管理
create_collection({"name": "project-x"})
switch_collection({"name": "project-x"})
list_collections()
get_stats()

# 关联
link_memory({"from_id": "id1", "to_id": "id2", "relation": "depends_on"})
get_knowledge_chain({"doc_id": "id1", "depth": 1})

# 版本/过期
rollback_memory({"category": "tech", "device": "pc", "version": 0})
get_expired_memories({"half_life_days": 30, "threshold": 0.5})

# 备份/导出
backup_memories()
restore_memories({"backup": "backup_20260520_200000"})
export_memories({"format": "markdown"})
```

## 命令行

```bash
python vector_memory.py search 关键词
python vector_memory.py search text=特定查询 top_k=10
python vector_memory.py stats
python vector_memory.py list
python vector_memory.py backup
python vector_memory.py create name=新集合
python vector_memory.py restore backup=backup_20260520_200000
```

## 性能优化

1. **模型预加载**：修改 Hermes_Gateway.cmd，启动前调用 `~/.hermes/scripts/preload_models.py`。搜索速度：首次~2.5s → 后续 **0.4-0.6s**。

2. **Web UI**：`scripts/memory_web/app.py` 已优化为直接导入模块 + 模型预加载。启动后访问 `http://localhost:5000/search`。

3. **增量 TF-IDF**：内置 `_rebuild_tfidf_if_needed()` 自动管理，无需手动触发。

## ⚠️ 常见陷阱（精简）

### 1. 默认集合名
旧数据在 `memories`（带 s）集合中，core.py 的 `_current_collection_name` 必须一致。

### 2. ChromaDB 持久化
**必须使用** `PersistentClient(path=~/.hermes/vector_store)`。`Client()`（内存模式）退出后数据丢失。

### 3. 模型路径检测
`_check_local_model()` 遍历多个可能路径：`hub/AI-ModelScope/<name>`、`AI-ModelScope/<name>`、带下划线版本。

### 4. Web UI Windows 路径
`os.path.expanduser("~/.hermes")` 在 Windows 返回混合路径（`C:\\Users\\Nemo/.hermes`），需用 `os.path.abspath()` 归一化。

### 5. 模块导入路径
直接运行脚本时需添加 `scripts/` 目录到 `sys.path`。主入口已自动处理。

## 文件位置

| 路径 | 用途 |
|------|------|
| `~/.hermes/skills/vector_memory/scripts/` | 核心脚本 |
| `~/.hermes/vector_store/` | ChromaDB 持久化 + `relations.json` + `version_history.json` |
| `~/.hermes/backups/` | 备份目录 |
| `~/.hermes/exports/` | 导出目录 |
| `~/.hermes/memories/MEMORY.md` | 文本同步文件 |
| `~/.hermes/scripts/preload_models.py` | 模型预加载脚本 |
| `~/.hermes/scripts/memory_web/app.py` | Web UI |
| `~/.hermes/skills/vector_memory/SKILL.md` | 本文件 |

## 测试

```bash
pytest ~/.hermes/skills/vector_memory/scripts/test_vector_memory.py -v
```

覆盖：Core（版本/锁）→ Collections（创建/删除/重复）→ Memories（添加/批量/列表/清空）→ Search（搜索/评分）→ Management（统计/导出/备份）→ Relations（关联/解除关联）→ 增量 TF-IDF

## 性能指标

| 操作 | 耗时 |
|------|------|
| 首次搜索（加载模型） | ~2,500ms |
| 后续搜索（模型缓存） | ~400ms |
| 预加载后（模型在内存） | ~400ms |
| 批量添加 10 条 | <1s |
| 导出 100 条 | <0.5s |