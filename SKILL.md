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

## 自动集成规则（Hermes 对话自动调用）

当对话涉及以下话题时，**自动搜索 Vector-Memory** 获取相关上下文，无需用户显式要求：

### 🔍 自动搜索触发条件

| 用户提到 | 自动执行 | 示例 |
|---------|---------|------|
| 设备型号、品牌 | `search_memories({"text": "型号"})` | "海康摄像机老是掉线" → 搜相关故障记录 |
| 故障现象 | `search_memories({"text": "现象"})` | "画面一直卡顿" → 搜网络/录像相关 |
| 维修经验 | `search_memories({"text": "关键词"})` | "之前那个消防泵问题" → 搜消防相关 |
| 技术参数 | `search_memories({"text": "参数"})` | "POE供电距离" → 搜供电相关 |
| 项目名称 | 对应集合搜索 | "监控项目/消防项目" → 切集合后搜 |

### 📝 自动保存触发条件

| 用户说 | 自动执行 | 示例 |
|-------|---------|------|
| 分享故障处理步骤 | `add_memory({"text": "步骤"})` | "上次换硬盘的方法是..." |
| 提到具体参数 | `add_memory({"text": "参数"})` | "这个型号支持POE+" |
| 经验总结 | `add_memory({"text": "经验"})` | "注意POE网线不能超过100米" |

### 💡 搜索结果呈现方式

搜索结果自动融入对话，**不打断流畅性**：

```
用户：海康摄像头画面一直闪怎么办？
助手（自动搜索后）：我之前记过一条类似记录：海康DS-2CD系列画面闪烁，
检查电源适配器输出是否稳定，常见原因是12V电源老化导致纹波过大。
```

### 🔗 自动关联

当发现当前讨论与已存记忆相关时，自动提示关联：

```
助手：这条记录我帮你关联到之前那篇「POE供电故障排查」的文章，
方便以后一起查到。
```

---

## 性能优化

1. **模型预加载**：修改 Hermes_Gateway.cmd，启动前调用 `~/.hermes/scripts/preload_models.py`。搜索速度：首次~2.5s → 后续 **0.4-0.6s**。

2. **Web UI**：`scripts/memory_web/app.py` 已优化为直接导入模块 + 模型预加载。启动后访问 `http://localhost:5000/search`。

3. **增量 TF-IDF**：内置 `_rebuild_tfidf_if_needed()` 自动管理，无需手动触发。

## ⚠️ 常见陷阱（精简）

### 0. CI/CD 推送
`~/.hermes/skills/vector_memory/` 已初始化为 git 仓库。推送至 GitHub 见 `references/cicd-setup.md`。

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

## GPU 加速要求

当前系统 **纯 CPU 运行**，搜索 ~400ms。如需 GPU 加速：

| 要求 | 最低配置 | 推荐配置 |
|------|---------|---------|
| GPU | GTX 1060 以上 | RTX 2060+ |
| 显存 | >2GB | >6GB |
| CUDA 驱动 | ≥11.0 | ≥12.x |

低于 GTX 1060（如 GT 430 / 1GB VRAM）**不建议开启 GPU**，数据传输开销 > 计算加速收益。

启用：`pip install torch --index-url https://download.pytorch.org/whl/cu118`（替换 CPU 版 PyTorch）

## 打包分享（pip 包）

可将此系统打包为 pip 安装包，分享给同事：

```
vector_memory/
├── src/vector_memory/
│   ├── __init__.py      # 暴露所有 API
│   ├── __main__.py      # python -m vector_memory
│   ├── cli.py           # 命令行入口
│   ├── core.py / storage.py / search.py / management.py
├── tests/
├── pyproject.toml       # 打包配置
└── README.md
```

安装方式：
```bash
# 直接装
pip install git+https://github.com/wufeidang/vector-memory.git

# 本地开发
cd vector_memory && pip install -e .
```

装好后别人就能用：
```bash
vector-memory add "消防泵启动压力0.6MPa" --category fire
vector-memory search 消防
```

Python 调用：
```python
from vector_memory import add_memory, search_memories
add_memory({"text": "NVR硬盘故障记录"})
```

## 典型使用场景

| 场景 | 说明 | 示例 |
|------|------|------|
| 故障知识库 | 记录设备故障及解决方案，按意思搜索 | `search 画面暗` → "调整红外灯亮度到80%" |
| SOP 文档库 | 存操作规程，搜流程 | `search 困人救援` → 电梯救援步骤 |
| 巡检日志库 | 每日记录异常，月末回顾 | `search 消防栓` → 近30天记录 |
| 多项目隔离 | 用集合区分项目 | `--collection monitor` / `--collection fire` |

## 与 Hermes 原生记忆的区别

| 维度 | Hermes 原生记忆 | Vector-Memory |
|------|----------------|---------------|
| 用途 | AI 记关于你的事 | **你自己**记专业知识 |
| 容量 | ~2,200 字符 | 无限（硬盘） |
| 搜索 | 关键词匹配 | 语义搜索 |
| 谁控制 | AI 自动管理 | **你**主动控制 |
| 可分享 | ❌ 绑死 Hermes | ✅ pip 包分享 |
| 自动注入 | ✅ 每次对话 | ❌ 需主动查询 |

**最佳搭配**：Hermes 记忆存「你的偏好」（10+条），Vector-Memory 存「你的专业知识」（几百上千条）。

## 性能指标

| 操作 | 耗时 |
|------|------|
| 首次搜索（加载模型） | ~2,500ms |
| 后续搜索（模型缓存） | ~400ms |
| 预加载后（模型在内存） | ~400ms |
| 批量添加 10 条 | <1s |
| 导出 100 条 | <0.5s |