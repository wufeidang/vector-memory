# Vector-Memory

**语义级知识库系统** — 为 Hermes Agent 提供 ChromaDB + BGE 中文嵌入的专业知识管理能力。

> 与 Hermes 原生记忆（MEMORY.md，~2200字符关键词匹配）互补：原生记忆记你的偏好，Vector-Memory 存专业知识。

---

## 功能

| 功能 | 说明 |
|------|------|
| 语义搜索 | BGE 中文嵌入 → 向量检索 → TF-IDF 后排序 → Reranker 重排序 |
| 多集合隔离 | 按项目/类别创建独立知识库，`create/switch/list/delete` |
| 关联知识链 | 记忆之间建立 `link/unlink` 关系，形成知识图谱 |
| 版本管理 | 自动保存版本历史，支持 `rollback` 回滚 |
| 记忆衰减 | 指数衰减（30天半衰期），长期未访问自动降权 |
| 导出备份 | JSON/Markdown 导出，完整 ChromaDB 备份与恢复 |
| Web UI | Flask 搜索界面（v4.0），预加载后 0.5s 响应 |
| 文件存储 | 支持 txt/md/pdf/docx/xlsx/pptx 等文档和 png/jpg 图片，自动提取文本+语义索引 |
| Hermes 集成 | 对话中自动触发搜索，无需手动查询 |

## 架构

```
scripts/
├── core.py          配置 / 模型单例 / TF-IDF / Reranker（线程安全锁）
├── storage.py       集合管理 / 记忆 CRUD（add/list/clear/dedupe）
├── search.py        搜索管道：向量 → 增量 TF-IDF → Reranker
├── management.py    关联 / 版本 / 过期 / 备份 / 导出
├── file_storage.py  文件/图片存储、文本提取、语义索引（PDF/Word/Excel/PPT/图片）
└── vector_memory.py 主入口（导入5模块 + 命令行接口）
```

**依赖模型**：
- `AI-ModelScope/bge-base-zh-v1.5` — 中文嵌入（768维，~390MB）
- `AI-ModelScope/bge-reranker-v2-m3` — 重排序（可选）

## 快速开始

### 安装

```bash
git clone https://github.com/wufeidang/vector-memory.git
cd vector-memory

# 创建虚拟环境
uv venv .venv
.venv/Scripts/python.exe -m ensurepip

# 安装依赖（~2GB，耗时受网络影响）
.venv/Scripts/python.exe -m pip install --break-system-packages scikit-learn
.venv/Scripts/python.exe -m pip install --break-system-packages sentence-transformers
.venv/Scripts/python.exe -m pip install --break-system-packages modelscope chromadb
```

### 验证

```bash
# 首次运行自动下载 BGE 嵌入模型（~390MB）
.venv/Scripts/python.exe scripts/vector_memory.py stats

# 搜索测试
.venv/Scripts/python.exe scripts/vector_memory.py search "摄像头故障"

# 添加记忆
.venv/Scripts/python.exe scripts/vector_memory.py add "海康DS-2CD系列画面闪烁，检查电源适配器12V输出"

# 运行测试套件
.venv/Scripts/python.exe -m pytest scripts/test_vector_memory.py -v
```

### 作为 Hermes 技能使用

```bash
# 1. 安装到 Hermes 技能目录
ln -s ~/vector-memory ~/.hermes/skills/vector-memory

# 2. 启动 Hermes 后加载技能
/skill vector-memory

# 3. 对话中自动触发
#    提到设备型号/故障现象/技术参数 → 自动搜索知识库
#    分享经验/参数 → 提示是否保存
```

## API

所有函数接收 **args 字典**参数（非关键字参数），返回 `{"success": bool, ...}`。

### 添加记忆

```python
# 单条
add_memory({"text": "内容", "metadata": {"category": "tech"}})

# 批量
add_batch({"texts": ["a", "b"], "metadatas": [{}, {}]})

# 长文分块
add_with_chunks({"text": "长文本...", "chunk_size": 500, "overlap": 50})
```

### 搜索

```python
search_memories({"text": "关键词", "top_k": 5, "where": {"category": "tech"}})

# 返回: {"success": True, "results": [{"text":"...", "score":0.78, "relevance_score":83}], "count": N}
```

### 集合管理

```python
create_collection({"name": "项目X"})    # 创建
list_collections()                      # 列出（含计数）
switch_collection({"name": "项目X"})    # 切换
delete_collection({"name": "项目X"})    # 删除
```

### 关联

```python
link_memory({"from_id": "id1", "to_id": "id2", "relation": "depends_on"})
get_knowledge_chain({"doc_id": "id1", "depth": 1})
unlink_memory({"from_id": "id1", "to_id": "id2"})
```

### 备份

```python
backup_memories()                    # 完整备份
restore_memories({"backup_dir": "...", "dry_run": False})  # 恢复（默认只预览！）
export_memories({"format": "markdown"})    # 导出 Markdown
```

### 命令行

```bash
python vector_memory.py search 关键词
python vector_memory.py search text="POE供电距离" top_k=10
python vector_memory.py stats
python vector_memory.py add "新知识..."
python vector_memory.py backup
python vector_memory.py create name=新集合
```

## 已知陷阱

| 陷阱 | 说明 | 正确用法 |
|------|------|---------|
| 字段名 | `content` → **`text`** | 读取 `result["text"]` |
| restore dry_run | 默认 `True`，只预览不恢复 | `restore_memories({..., "dry_run": False})` |
| 备份 manifest | 备份自动创建 manifest，**不要手动覆盖** | 直接读取已创建的 |
| ChromaDB ONNX | 默认 embedding 触发 ~79MB 下载 | 提供显式嵌入 `collection.add(embeddings=...)` |
| Windows 路径 | `~/.hermes` 可能含混合分隔符 | `os.path.abspath()` 归一化 |

## 在 Hermes 中的定位

| 维度 | Hermes 原生记忆 | Vector-Memory |
|------|----------------|---------------|
| 用途 | AI 记关于你的事 | **你**记专业知识 |
| 容量 | ~2,200 字符 | 无限（硬盘） |
| 搜索 | 关键词匹配 | 语义搜索（向量嵌入） |
| 谁控制 | AI 自动管理 | **你**主动控制 |
| 自动注入 | 每次对话 | 对话中自动触发 |

典型场景：故障知识库、SOP 文档库、巡检日志库、设备参数库、技术教程全文。

## License

MIT
