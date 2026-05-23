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
list_collections(args=None)
get_stats()

# 关联
link_memory({"from_id": "id1", "to_id": "id2", "relation": "depends_on"})
get_knowledge_chain({"doc_id": "id1", "depth": 1})

# 版本/过期
rollback_memory({"category": "tech", "device": "pc", "version": 0})
get_expired_memories({"half_life_days": 30, "threshold": 0.5})

# 备份/导出
backup_memories({"backup_dir": "~/.hermes/backups/backup_xxx"})
restore_memories({"backup_dir": "~/.hermes/backups/backup_xxx"})
export_memories({"format": "markdown"})

# ⚠️ 重要：所有函数接收 args 字典参数，不是关键字参数！
# 详细参考：references/web-ui-v4-api-patterns.md
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

2. **Web UI v4.0**（2026-05-23 重构）：专业级完整重构版，解决v3.0所有已知bug。
   - 核心文件：`scripts/memory_web/app-v4.py`（28KB）
   - CSS：`scripts/memory_web/static/css/style-v4.css`（22KB，完整主题系统）
   - JS：`scripts/memory_web/static/js/app-v4.js`（6KB，async/await）
   - 模板：8个v4模板（base/index/search/memories/collections/backup/monitor/export）
   - 启动：`cd scripts/memory_web && python app-v4.py` → 访问 `http://localhost:5000`
   - 完整构建参考：`references/web-ui-v4-build.md`
   - **API 调用模式**：所有 vector_memory 函数接收 `args` 字典参数，非关键字参数！参考：`references/web-ui-v4-api-patterns.md`
   - 测试：使用 Flask `test_client()` 测试所有路由和API

   **v3.0 → v4.0 改进**：
   | 问题 | v3.0 | v4.0 修复 |
   |------|------|----------|
   | Toast容器 | 所有模板缺少 | base-v4.html 统一包含 |
   | CSS特性 | 缺少现代特性 | 完整CSS变量主题系统 |
   | JS语法 | 无async/await | 现代async/await + 错误处理 |
   | 模型管理 | 全局变量竞态 | ModelManager 类封装 |
   | 错误处理 | 不完善 | require_model + log_operation 装饰器 |
   | 代码结构 | 不够清晰 | 模块化 + 完整注释 |
   | **API参数** | **关键字参数** | **args 字典参数** |

3. **增量 TF-IDF**：内置 `_rebuild_tfidf_if_needed()` 自动管理，无需手动触发。

4. **测试模式**：使用 Flask `test_client()` 替代 HTTP 请求进行测试，无需启动服务器。参考：`references/flask-testing-pattern.md`。

## ⚠️ 常见陷阱（精简）

### 0. 字段名陷阱（2026-05-23 重要）

**`vector_memory` 返回的字段名与常见假设不同！**

| 假设字段 | 实际字段 | 影响范围 |
|---------|---------|---------|
| `content` | **`text`** | `list_memories`, `search_memories` 返回的记忆内容 |
| `memories` | **`results`** | `list_memories` 返回列表键 |
| `data` | **`content`** | `export_memories` 返回导出内容 |
| `created_at` | **`metadata.created_at`** | 时间戳埋在第2层 |
| `collection` | **`metadata.collection`** | 集合名埋在第2层 |

**修复模式**:
```python
# 模板中使用
{{ mem.text }}  {# 不是 mem.content #}
{{ mem.metadata.created_at }}  {# 不是 mem.created_at #}

# JS 中使用
const content = item.text;  {# 不是 item.content #}

# Web UI 兼容性处理
for m in memories:
    meta = m.get("metadata", {})
    m["content"] = m.get("text", "")           # 兼容旧模板
    m["created_at"] = meta.get("created_at", "") # metadata 中取出
```

详细对照：`references/web-ui-v4-api-patterns.md`（含6个排查清单）

### 0.0 模型加载失败陷阱（2026-05-23 重要）

**问题**: `_get_model()` 返回 `None` 时，后续调用 `model.encode()` 触发 `AttributeError: 'NoneType' object has no attribute 'parameters'`。

**根本原因**:
1. 模型路径查找失败（路径构造 bug、模型未下载）
2. 模型下载/加载时发生异常但未抛出
3. 存储函数未检查模型返回值

**修复模式**:
```python
# 在调用模型编码前检查
model = _get_model()
if model is None:
    return {"success": False, "message": "嵌入模型加载失败，请检查模型路径"}

# 或在使用前验证
try:
    embeddings = model.encode(texts).tolist()
except AttributeError as e:
    return {"success": False, "message": f"模型编码失败: {e}"}
```

**路径查找注意事项**:
- Windows/Linux 路径分隔符不同（`os.sep`）
- 模型名中的点可能被替换为下划线（`bge-base-zh-v1.5` → `bge-base-zh-v1_5`）
- ModelScope 下载路径可能有多种变体

**详细修复记录**: `references/ci-test-model-loading-fix-2026-05-23.md`

**间歇性错误诊断**: `references/ci-test-intermittent-model-loading-2026-05-23.md` — 偶发模型加载错误（竞争条件/磁盘I/O）的诊断与重试模式。

**CI 首次运行模型下载路径查找**（2026-05-23 第二次修复）：
- 问题：`snapshot_download` 下载后 `_get_preferred_model()` 仍找不到路径
- 原因：ModelScope 下载路径存在多种变体（带下划线、子目录等）
- 修复：新增 `_find_downloaded_model()` 函数，递归扫描 `~/.cache/modelscope` 目录查找实际路径
- 验证：19/19 测试通过 ✓

### 0.1 `list_collections()` 返回格式陷阱（2026-05-23 重要）

**问题**: `list_collections()` 返回的是**字典列表** `[{"name": "memories", "count": 564}]`，而非简单的字符串列表 `["memories"]`。

**常见错误**：
```python
# ❌ 错误：假设返回字符串列表
result = vm.list_collections()
assert "memories" in result.get("collections", [])  # 永远失败！

# ✅ 正确：检查字典中的 name 字段
result = vm.list_collections()
collections = result.get("collections", [])
assert any(c.get("name") == "memories" for c in collections)
```

**影响范围**：
- 测试断言（`test_vector_memory.py`）
- Web UI 集合存在性检查
- 任何需要判断集合是否存在的代码

**修复模式**：
```python
def collection_exists(collection_name: str) -> bool:
    """检查集合是否存在"""
    result = vm.list_collections()
    collections = result.get("collections", [])
    return any(c.get("name") == collection_name for c in collections)

def get_collection_count(collection_name: str) -> int:
    """获取集合记忆数量"""
    result = vm.list_collections()
    collections = result.get("collections", [])
    for c in collections:
        if c.get("name") == collection_name:
            return c.get("count", 0)
    return 0
```

**CI/CD 测试修复记录**：`references/ci-test-list-collections-fix-2026-05-23.md`

### 0.1.1 `list_collections()` 默认集合懒创建问题（2026-05-23 重要）

**问题**: 在干净环境中（无预置数据），`list_collections()` 返回空列表，因为 ChromaDB 集合采用**懒创建**机制。

**症状**:
```
GitHub Actions CI 测试失败:
AssertionError: assert any(c.get('name') == 'memories' for c in [])
```

**根本原因**:
- ChromaDB 集合只在首次写入数据时创建
- 测试环境是干净的，没有预置数据
- `list_collections()` 返回空列表

**修复方案**: 在 `storage.py` 的 `list_collections()` 函数中添加默认集合初始化逻辑:

```python
def list_collections(args=None):
    """列出所有集合及其记忆数量
    
    确保默认集合 'memories' 存在，避免测试失败。
    """
    client = _get_chroma_client()
    collections_info = []
    
    # 列出所有现有集合
    for collection in client.list_collections():
        count = collection.count()
        collections_info.append({
            "name": collection.name,
            "count": count
        })
    
    # 确保默认集合 'memories' 存在
    has_memories = any(c["name"] == "memories" for c in collections_info)
    if not has_memories:
        _get_collection("memories")  # 触发懒创建
        # 重新查询
        collections_info = []
        for collection in client.list_collections():
            count = collection.count()
            collections_info.append({
                "name": collection.name,
                "count": count
            })
    
    return {
        "success": True,
        "collections": collections_info,
        "count": len(collections_info)
    }
```

**影响范围**:
- GitHub Actions CI 测试
- 本地测试环境（干净环境）
- 首次初始化场景

**验证方法**:
```bash
pytest scripts/test_vector_memory.py::test_list_collections -v
# 应通过
```

**参考文档**: `references/ci-test-list-collections-fix-2026-05-23.md`

### 0.2 Jinja2 字典访问歧义陷阱（2026-05-23 重要）

**问题**: 在 Jinja2 模板中，`{{ dict.items }}` 可能被解析为字典的 `items()` 方法，而非 `items` 键的值。

**症状**: 备份列表显示 `built-in method items of dict object at 0x...` 而非实际数字。

**原因**: Jinja2 属性访问规则：
1. 首先尝试 `dict.items`（字典键或对象属性）
2. 如果失败，尝试 `dict.get("items")`
3. 如果仍然失败，尝试 `dict.items()`（调用方法）

对于字典对象，`items` 是内置方法名，会被优先解析为方法！

**修复**：始终使用字典访问语法：
```html
<!-- ❌ 错误：可能被解析为方法 -->
{{ backup.items or 0 }}

<!-- ✅ 正确：显式字典键访问 -->
{{ backup['items'] if backup['items'] is defined else 0 }}
```

详细调试记录：`references/web-ui-backup-list-items-debug-2026-05-23.md`

### 0.2 `list_collections()` 返回集合数量恒为 0（2026-05-23 重要）

**问题**: Web UI 集合管理页面显示所有集合记忆数量为 0，即使数据库中有大量数据。

**症状**:
```
记忆集合
➕ 新建集合
memories  0 条  ← 实际有 564 条
```

**原因**:
1. `storage.py` 的 `list_collections()` 只返回集合名称列表 `[\"memories\"]`，不包含计数
2. `app-v4.py` 将字符串集合名硬编码为 `count: 0`：
   ```python
   collections = [{"name": c, "count": 0} if isinstance(c, str) else c for c in raw]
   ```

**修复**: 修改 `storage.py` 的 `list_collections()`，查询每个集合的实际计数：
```python
def list_collections(args=None):
    """列出所有集合及其记忆数量"""
    client = _get_chroma_client()
    collections_info = []
    for collection in client.list_collections():
        count = collection.count()  # 获取实际记忆数量
        collections_info.append({
            "name": collection.name,
            "count": count
        })
    return {"success": True, "collections": collections_info, "count": len(collections_info)}
```

**验证方法**:
```python
import storage
result = storage.list_collections(None)
for coll in result["collections"]:
    print(f"{coll['name']}: {coll['count']} 条记忆")
```

**兼容性**: `app-v4.py` 的类型转换逻辑已兼容 dict 格式，无需修改。

详细调试记录：`references/web-ui-collection-count-fix-2026-05-23.md`

### 1. 多agent模式超时

`delegate_task` 子agent超时限制为 **600秒**。复杂重构任务（如Web UI完整重构）容易超时。

**解决方案**：
- 简单任务（<5步）：直接完成
- 中等任务（5-10步）：尝试多agent（2-3并发）
- 复杂任务（>10步）：直接完成或改用 cronjob

详细指南：`references/multi-agent-timeout-pattern.md`

### 2. `list_collections` 返回字符串列表（非字典）

**核心问题**：`list_collections()` 返回 `["default", "monitor"]` 而非 `[{"name": "default", "count": 5}]`。在模板中遍历 `c.get("count")` 会报 `AttributeError`。

**修复**：后端统一做类型转换：
```python
formatted = []
for c in raw:
    if isinstance(c, str):
        formatted.append({"name": c, "count": 0})
    elif isinstance(c, dict):
        formatted.append(c)
```

### 3. `get_stats` 计数需要手动遍历集合

因为集合是字符串，`c.get("count")` 恒为 0。**必须**逐集合调用 `list_memories({"collection": name, "limit": 0})` 并累加 `result.get("count", 0)`。

### 4. 搜索结果缺少 `collection` 字段

`search_memories` 的 results 不包含 collection 来源信息。**后端必须手动注入**：`r["collection"] = coll_name`。

### 5. backup_memories 自动创建备份目录（不需手动建）

**`backup_memories()` 内部已调用 `os.makedirs(backup_dir, exist_ok=True)` 自动创建目录**，调用前无需手动建目录。

```python
# ✅ 直接调用即可
result = vm.backup_memories({"backup_dir": "~/my_backup"})
# 目录由 backup_memories 内部自动创建
```

⚠️ 但 **Web UI 的 `app-v4.py` 中**，如需在备份目录写入额外文件，路径需用 `os.path.join(BACKUP_DIR, name)` 拼接，确保 `BACKUP_DIR` 已存在（在 app 初始化时已通过 `os.makedirs(BACKUP_DIR, exist_ok=True)` 创建）。

### 6. backup_memories 已自动创建 manifest.json，不要覆盖

**`backup_memories()` 执行成功后会在备份目录下自动创建 `manifest.json`（含实际 items 列表）**。Web UI 的 `api_backup_create` 中 **不应再新建 manifest 写入**，否则会覆盖真实数据为空。

**错误写法**（覆盖真实 manifest）：
```python
result = vm.backup_memories({"backup_dir": path})
if result.get("success"):
    # ❌ 与 backup_memories 自己创建的 manifest 冲突！items 会变成空列表
    manifest = {"items": result.get("items", [])}  # result["items"] 不存在！
    with open(manifest_path, "w") as f:
        json.dump(manifest, f)
```

**正确写法**（直接读取）：
```python
result = vm.backup_memories({"backup_dir": path})
if result.get("success"):
    manifest_path = os.path.join(path, "manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path, "r") as f:
            manifest = json.load(f)  # ← 直接读 backup_memories 已创建的
        items = manifest.get("items", [])
    else:
        # 容错：从 result 提取（但很少走到这）
        items = result.get("manifest", {}).get("items", [])
```

### 7. restore_memories 默认 dry_run=True，需显式请求实际恢复

**`restore_memories()` 的 `dry_run` 参数默认为 `True`**，即只预览恢复内容而不执行实际恢复。

**错误写法**（只预览不恢复）：
```python
result = vm.restore_memories({"backup_dir": path})
# result.success = True, 但没有任何文件被恢复！
```

**正确写法**：
```python
result = vm.restore_memories({"backup_dir": path, "dry_run": False})
```

### 8. Windows 上测试 Flask API 的可靠方式

git-bash 环境（terminal 工具）无法可靠地用 `&` 或 background 模式启动 Flask 服务器。**推荐使用 Python subprocess 启动**：

```python
import subprocess, sys, time, json, urllib.request

proc = subprocess.Popen(
    [sys.executable, "app-v4.py"],
    cwd=app_dir,
    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
)
time.sleep(10)  # 等待模型加载

# 用 urllib 测试 API
req = urllib.request.Request("http://localhost:5000/api/backup/create",
    data=b'{}', headers={'Content-Type': 'application/json'})
resp = urllib.request.urlopen(req, timeout=20)
result = json.loads(resp.read().decode())

proc.terminate()
proc.wait()
```

服务器退出后记得 cleanup，否则端口占用。

### 6. `list_memories` 不支持文本过滤

`list_memories({"collection": "x", "limit": 100})` 的 `query` 参数被忽略。过滤需在内存层做：`[m for m in results if keyword in m.get("text", "")]`。

### 1. CI/CD 推送
`~/.hermes/skills/vector_memory/` 已初始化为 git 仓库。推送至 GitHub 见 `references/cicd-setup.md`。

### 1. 默认集合名
旧数据在 `memories`（带 s）集合中，core.py 的 `_current_collection_name` 必须一致。

### 2. ChromaDB 持久化
**必须使用** `PersistentClient(path=~/.hermes/vector_store)`。`Client()`（内存模式）退出后数据丢失。

### 3. 模型路径检测
`_check_local_model()` 遍历多个可能路径：`hub/AI-ModelScope/<name>`、`AI-ModelScope/<name>`、带下划线版本。

### 4. Web UI Windows 路径
`os.path.expanduser("~/.hermes")` 在 Windows 返回混合路径（`C:\\\\Users\\\\Nemo/.hermes`），需用 `os.path.abspath()` 归一化。

### 5. 模块导入路径
直接运行脚本时需添加 `scripts/` 目录到 `sys.path`。主入口已自动处理。

### 6. 监控数据自动记录（修复后）

**问题**：`memory_monitor.py` 是独立模块，不会自动被搜索/备份操作调用，导致 Web UI 监控页面数据不更新。

**修复方案**：将监控记录直接集成到核心操作中：

| 操作 | 修改文件 | 集成方式 |
|------|----------|----------|
| 搜索记忆 | `search.py` → `search_memories()` | 函数末尾调用 `record_search()` |
| 创建备份 | `backup_memory.py` → `create_backup()` | 函数开头记录 `start_time`，末尾调用 `record_backup()` |

**详细文档**：`references/monitoring-integration-fix.md`

**代码模式**：
```python
# 搜索中记录监控
try:
    from memory_monitor import record_search
    record_search(query=text, results_count=len(results), elapsed_ms=elapsed_ms, source="vector_memory")
except Exception:
    pass  # 监控失败不影响主功能

# 备份中记录监控
start_time = time.time()  # 函数开头
# ... 备份操作 ...
try:
    from memory_monitor import record_backup
    record_backup(duration_ms=round((time.time() - start_time)*1000, 2), items_count=len(items), success=True)
except Exception:
    pass
```

**验证方法**：
```bash
python -c "from search import search_memories; search_memories({'text': '测试', 'top_k': 1})"
cat ~/.hermes/monitor_data/performance_log.json  # 应新增条目
```

### 7. 原生记忆空间上限

Hermes 原生记忆 `MEMORY.md` 容量上限约 **2,200 字符**。超过后新条目无法保存。

**解决方案**：
1. 定期审查并清理旧条目（使用 `memory_cli.py` 或手动编辑）
2. 将详细记录迁移到 Vector-Memory（容量无限）
3. 原生记忆仅保留关键偏好和状态摘要

### 8. Windows 大文件写入

在 Windows 环境下，`write_file` 工具写入大文件（>10KB）时可能超时失败。

**推荐模式**：使用 `execute_code` 中的 Python `open()` 函数：
```python
with open(path, 'w', encoding='utf-8') as f:
    f.write(content)  # 大文件稳定可靠
```

**详细参考**：`references/windows-large-file-write-pattern.md`

### 9. read_file 工具 Windows 路径问题（2026-05-23）

**问题**：`read_file` 工具在 Windows 环境下多次失败（File not found），改用 `execute_code` 中的 Python `open()` 函数成功读取文件。

**推荐模式**：
```python
# 读取文件
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 写入文件（大文件）
with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
```

**适用场景**：当 `read_file` 返回 `File not found` 错误时，优先改用 `execute_code`。

### 9. 记忆同步脚本格式兼容

`sync_memory.py` 脚本需同时支持 **§ 分隔格式** 和 **传统 `- [timestamp]` 格式** 的 MEMORY.md。

**§ 分隔格式**（当前使用）：
```
记忆内容 1
§
记忆内容 2
```

**传统格式**（兼容）：
```
- [2026-05-20 20:01:08] 记忆内容 {metadata}
```

**修复要点**：
- `parse_memory_file()` 需检测 `§` 并切换解析逻辑
- 时间戳优先从嵌入的 `- [timestamp]` 提取，其次从条目开头日期提取
- 去重用 MD5 哈希，避免文本微小差异导致重复导入
- 状态文件 `.sync_state.json` 保存 `synced_hashes` 列表

**详细文档**：`references/sync-memory-format-fix.md`

### 10. `import_from_memory_md` 函数格式限制（2026-05-23）

**核心问题**：`storage.py` 中的 `import_from_memory_md()` 函数**只解析 `- [` 格式的行**，完全忽略 `§` 分隔格式的内容。当 MEMORY.md 使用 `§` 分隔格式时，该函数返回 0 条导入。

**症状**：
```
✅ 同步成功!
   导入条目数: 0  ← 应该是 800+
   跳过重复: 0
   错误数: 0
```

**原因**：函数代码只提取 `lines = [l.strip() for l in content.split("\n") if l.strip().startswith("- [")]`，忽略了 `§` 分隔的大段文本。

**临时解决方案**（手动同步）：
```python
import hashlib
from core import MEMORY_MD, _get_collection
from storage import add_memory, list_memories

content = MEMORY_MD.read_text(encoding="utf-8")
lines = [l.strip() for l in content.split('\n') if l.strip().startswith('- [')]

# 获取现有记忆哈希用于去重
existing_hashes = set()
result = list_memories({"limit": 1000})
for m in result.get("memories", []):
    h = hashlib.md5(m.get("text", "").encode('utf-8')).hexdigest()
    existing_hashes.add(h)

# 同步新记忆
for line in lines:
    text = line[3:].strip()
    h = hashlib.md5(text.encode('utf-8')).hexdigest()
    if h not in existing_hashes:
        add_memory({"text": text, "metadata": {"imported": True}})
        existing_hashes.add(h)
```

**永久修复**：需要修改 `storage.py` 中的 `import_from_memory_md()` 函数，同时支持两种格式。参考：`references/import-from-memory-md-fix.md`

### 11. `dedupe_memories()` 仅处理向量数据库，不处理 MEMORY.md 文本文件（2026-05-23 重要）

**核心问题**：`storage.py` 中的 `dedupe_memories()` 函数**仅对 ChromaDB 向量数据库进行去重**，对 `~/.hermes/memories/MEMORY.md` 文本文件**完全无效**。

**症状**：
```
✅ 向量库去重完成
   去重前: 563 条
   去重后: 563 条
   删除: 0 条

❌ 但 MEMORY.md 文件仍有严重重复：
   总条目: 890 条
   唯一条目: 54 条
   重复条目: 836 条（94% 重复率）
```

**根本原因**：
- `dedupe_memories()` 使用 ChromaDB 的 `query` API 查找相似记录
- MEMORY.md 是纯文本文件，不受向量数据库操作影响
- 两个存储系统相互独立，去重操作不会跨系统同步

**MEMORY.md 重复模式**：
- **周期性重复**：约 13 条条目块被重复复制约 68 次
- **最严重重复组**：消防系列文章更新、技能更新记录、模型预加载优化等
- **重复率**：836/890 = 94%

**解决方案**：
1. **手动去重**：编辑 MEMORY.md 文件，删除重复条目
2. **脚本去重**：创建专用脚本处理 MEMORY.md 文本去重
3. **迁移策略**：将详细记录迁移到 Vector-Memory，原生记忆仅保留关键摘要

**推荐脚本**（参考 `references/memory-md-dedupe-pattern.md`）：
```python
from pathlib import Path

MEMORY_MD = Path.home() / ".hermes" / "memories" / "MEMORY.md"

def dedupe_memory_md():
    """对 MEMORY.md 进行文本去重"""
    content = MEMORY_MD.read_text(encoding="utf-8")
    lines = content.strip().split('\n')
    
    seen = set()
    unique_lines = []
    duplicates = 0
    
    for line in lines:
        # 跳过空行和分隔符
        if not line.strip() or line.strip() == '§':
            continue
        
        # 使用 MD5 哈希检测重复
        line_hash = hashlib.md5(line.strip().encode('utf-8')).hexdigest()
        if line_hash not in seen:
            seen.add(line_hash)
            unique_lines.append(line)
        else:
            duplicates += 1
    
    # 写入去重后的文件
    MEMORY_MD.write_text('\n§\n'.join(unique_lines) + '\n', encoding='utf-8')
    print(f"去重完成: {duplicates} 条重复被删除，剩余 {len(unique_lines)} 条唯一记录")
```

**⚠️ 重要提醒**：
- 执行去重前**务必备份** MEMORY.md 文件
- 去重后需同步到向量数据库（使用 `import_from_memory_md()`）
- 建议定期（每周）检查 MEMORY.md 重复情况

---

## 7. 噪声检测脚本局限（已移除）

`daily_noise_summary.py` 脚本**已于 2026-05-20 移除**。原因：
- 仅检测**精确重复**（字符串完全相同），不支持语义相似度检测
- 脚本中的嵌入比较代码已被注释掉（"embedding comparison requires vector store access"）
- 功能与 opt-05 版本管理重叠

如需语义去重，应使用 `vector_memory.py dedupe` 命令或 `search_memories` + reranker 手动比对。

---

## 8. auto-memory 技能合并（2026-05-20）

`auto-memory` 技能目录已被移除，其事件驱动自动记忆功能已**合并到本技能的"自动集成规则"章节**。未来会话无需加载 `auto-memory` 技能，直接查阅本技能的自动集成规则即可。

## 文件位置

| 路径 | 用途 |
|------|------|
| `~/.hermes/skills/vector_memory/scripts/` | 核心脚本 |
| `~/.hermes/skills/vector_memory/scripts/sync_memory_reliable.py` | **可靠记忆同步脚本**（支持 § 和 - [ 格式，MD5 去重） |
| `~/.hermes/scripts/sync_memory.py` | 记忆同步脚本（§ 分隔格式兼容） |
| `~/.hermes/scripts/.sync_state.json` | 同步状态（last_sync, synced_count, synced_hashes） |
| `~/.hermes/vector_store/` | ChromaDB 持久化 + `relations.json` + `version_history.json` |
| `~/.hermes/backups/` | 备份目录 |
| `~/.hermes/exports/` | 导出目录 |
| `~/.hermes/memories/MEMORY.md` | 文本同步文件 |
| `~/.hermes/scripts/preload_models.py` | 模型预加载脚本 |
| `~/.hermes/scripts/memory_web/` | Web UI v2.0（28 个路由） |
| `~/.hermes/scripts/memory_web/app-v3.py` | Web UI v3.0 专业级重构（7 页面 + 15+ API） |
| `~/.hermes/scripts/memory_web/app-v4.py` | **Web UI v4.0 完整重构（ModelManager + 装饰器 + args 参数模式）** |
| `~/.hermes/scripts/memory_web/static/css/style-v4.css` | v4.0 CSS 主题系统（22KB） |
| `~/.hermes/scripts/memory_web/static/js/app-v4.js` | v4.0 JS 工具库（6KB） |
| `~/.hermes/scripts/memory_web/templates/*-v4.html` | v4.0 模板（8 个） |
| `~/.hermes/skills/vector_memory/SKILL.md` | 本文件 |
---

## ⚠️ 重要变更日志

### 2026-05-23 — Jinja2 字典访问歧义陷阱

**问题**：`backup-v4.html` 中 `{{ backup.items }}` 显示为 Python 方法对象而非实际值。

**原因**：Jinja2 将 `backup.items` 解析为 `dict.items()` 方法而非字典键 `items`。

**修复**：改用显式字典访问语法 `{{ backup['items'] if backup['items'] is defined else 0 }}`。

**新增参考**：`references/web-ui-backup-list-items-debug-2026-05-23.md`

### 2026-05-23 — Web UI 搜索功能验证

**问题**：用户反馈搜索页面无法找到数据。

**诊断结果**：
- ✅ 数据库：563 条记录，`memories` 集合，768 维嵌入
- ✅ API 路由：`/api/search` 存在且正常工作
- ✅ FTS 全文搜索：关键词"监控"、"消防"、"故障"均可检索

**可能原因**（如搜索仍无结果）：
- 浏览器缓存 → 强制刷新 (Ctrl+F5)
- 网络请求被拦截 → 检查浏览器控制台 (F12)
- 集合切换问题 → 确认当前集合为 `memories`

**新增参考**：`references/web-ui-search-verification-2026-05-23.md`

### 2026-05-23 — read_file 工具 Windows 路径问题

**问题**：`read_file` 工具在 Windows 环境下多次返回 `File not found`。

**解决方案**：改用 `execute_code` 中的 Python `open()` 函数读取文件，稳定可靠。

### 2026-05-23 — `import_from_memory_md` 格式限制修复

**问题**：`storage.py` 中的 `import_from_memory_md()` 函数只解析 `- [` 格式，忽略 `§` 分隔格式，导致同步时导入 0 条。

**症状**：
```
✅ 同步成功!
   导入条目数: 0  ← 应该是 800+
```

**临时解决方案**：使用新创建的 `scripts/sync_memory_reliable.py` 脚本，支持两种格式 + MD5 去重。

**永久修复**：需要修改 `storage.py` 中的 `import_from_memory_md()` 函数。参考：`references/import-from-memory-md-fix.md`

**本次同步结果**：
- MEMORY.md：839 条 `- [` 格式条目，193KB，9 个 `§` 区块
- 向量库原有：537 条
- 新增导入：26 条（813 条已存在被跳过）
- 向量库当前：563 条

---

### 2026-05-23 — `list_collections()` 返回集合数量恒为 0

**问题**: 集合管理页面显示所有集合记忆数量为 0，即使数据库中有大量数据。

**原因**:
1. `storage.py` 的 `list_collections()` 只返回集合名称列表，不包含计数
2. `app-v4.py` 将字符串集合名硬编码为 `count: 0`

**修复**: 修改 `storage.py` 的 `list_collections()`，遍历集合并调用 `collection.count()` 获取实际计数。

**新增参考**: `references/web-ui-collection-count-fix-2026-05-23.md`

### 2026-05-23 — CI/CD 测试修复：`test_list_collections` 集合初始化问题

**问题**: GitHub Actions CI 中 `test_list_collections` 测试失败，断言 `list_collections()` 返回的集合列表包含 `"memories"` 默认集合，但实际返回空列表。

**根本原因**: ChromaDB 集合采用**懒创建**机制，只在首次写入数据时创建。干净测试环境中没有预置数据，导致 `list_collections()` 返回空列表。

**修复方案**: 修改 `storage.py` 的 `list_collections()` 函数，添加默认集合初始化逻辑：
1. 列出所有现有集合
2. 检查是否包含 `"memories"` 默认集合
3. 如不存在，调用 `_get_collection("memories")` 触发懒创建
4. 重新查询并返回完整集合列表

**修复后状态**: 19 passed, 2 warnings in 45.23s

**新增参考**: `references/ci-test-list-collections-fix-2026-05-23.md`

### 2026-05-23 — CI/CD 测试修复：模型加载失败导致 `AttributeError`

**问题**: GitHub Actions CI 中 `test_add_memory` 测试失败，抛出 `AttributeError: 'NoneType' object has no attribute 'parameters'`。

**根本原因**: 
1. `_get_preferred_model()` 路径查找逻辑有 bug — 第一个候选路径使用了错误的 `MODEL_DIR.replace()` 构造，导致路径无效
2. `_get_model()` 缺乏错误处理 — 模型下载或加载失败时 `_model` 保持为 `None`
3. `storage.py` 的 `add_memory()`、`add_batch()`、`add_with_chunks()` 未检查模型是否为 `None`

**修复方案**:
1. **修复 `_get_preferred_model()` 路径查找** — 移除有 bug 的第一个候选路径，添加 6 个候选路径：
   - `~/.cache/modelscope/hub/AI-ModelScope/<model-name>`
   - `~/.cache/modelscope/AI-ModelScope/<model-name>`
   - 带下划线的模型名变体（某些下载工具替换点为下划线）
   - 直接路径检查（使用 `os.sep` 适配 Windows）

2. **增强 `_get_model()` 错误处理** — 添加 try-except 捕获下载/加载失败，明确报错信息

3. **在存储函数中添加模型空值检查** — `add_memory()`、`add_batch()`、`add_with_chunks()` 调用 `_get_model()` 后立即检查 `if model is None`

**修复后状态**: 19 passed, 1 warning in 12.97s

**新增参考**: `references/ci-test-model-loading-fix-2026-05-23.md`

### 2026-05-23 — Web UI v4.0 完整重构

**重构原因**：v3.0 存在多个 bug 且 API 调用模式错误

**核心发现**：`vector_memory` 模块的所有函数都接收 **`args` 字典参数**，而非关键字参数！

### 2026-05-23 — Web UI 备份列表显示修复

**问题**: 备份页面 `backup-v4.html` 中 `{{ backup.items or 0 }}` 显示异常（显示为 Python 对象地址）。

**原因**: Jinja2 模板中 `backup.items` 可能被解析为字典的 `items()` 方法而非 `items` 键的值。

**修复**: 改用字典访问语法：
```html
<!-- 原代码 -->
<td><span class="badge badge-info">{{ backup.items or 0 }}</span></td>

<!-- 修复后 -->
<td><span class="badge badge-info">{{ backup['items'] if backup['items'] is defined else 0 }}</span></td>
```

**验证方法**: 检查 `~/.hermes/backups/` 目录下 `manifest.json` 的 `items` 字段为列表类型。

**详细调试记录**: `references/web-ui-backup-list-items-debug-2026-05-23.md`

### 2026-05-23 — read_file 工具 Windows 路径问题

**问题**：`read_file` 工具在 Windows 环境下多次失败（File not found），改用 `execute_code` 中的 Python `open()` 函数成功读取文件。

**推荐模式**：
```python
# 读取文件
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 写入文件（大文件）
with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
```

**适用场景**：当 `read_file` 返回 `File not found` 错误时，优先改用 `execute_code`。

| 问题 | v3.0 | v4.0 修复 |
|------|------|----------|
| API 参数模式 | 关键字参数 | args 字典参数 |
| Toast 容器 | 所有模板缺少 | base-v4.html 统一包含 |
| CSS 特性 | 缺少现代特性 | 完整 CSS 变量主题系统 |
| JS 语法 | 无 async/await | 现代 async/await + 错误处理 |
| 模型管理 | 全局变量竞态 | ModelManager 类封装 |
| 错误处理 | 不完善 | require_model + log_operation 装饰器 |

**新增文件**：
- `app-v4.py`（28KB）- 完整重构的 Flask 应用
- `style-v4.css`（22KB）- 专业级 CSS 主题系统
- `app-v4.js`（6KB）- async/await 现代语法
- 8 个 v4 模板文件

**参考文档**：
- `references/web-ui-v4-build.md` - 完整构建参考
- `references/web-ui-v4-api-patterns.md` - API 调用模式对照表

### 2026-05-20 — auto-memory 技能合并

`auto-memory` 技能目录已被移除，其事件驱动自动记忆功能已**合并到本技能的"自动集成规则"章节**。未来会话无需加载 `auto-memory` 技能，直接查阅本技能的自动集成规则即可。

### 2026-05-20 — daily_noise_summary.py 移除

`daily_noise_summary.py` 脚本已被移除。原因：仅检测精确重复（字符串完全相同），不支持语义相似度，功能与 opt-05 版本管理重叠。如需语义去重，使用 `vector_memory.py dedupe` 或 `search_memories` + reranker。

### 2026-05-21 — 记忆空间接近上限

原生记忆 `MEMORY.md` 使用率已达 **89%**（1,966/2,200 字符）。新增记忆前建议先审查并清理旧条目。

### 2026-05-21 — sync_memory.py 格式兼容性修复

`sync_memory.py` 脚本原只支持 `- [timestamp]` 格式，但 MEMORY.md 实际使用 `§` 分隔格式，导致同步失败（解析 0 条）。

**修复**：`parse_memory_file()` 增加 `§` 分隔格式检测，支持两种格式自动切换。改用 MD5 哈希去重，避免文本微小差异导致重复导入。

详细文档：`references/sync-memory-format-fix.md`

### 2026-05-21 — Windows 文件写入模式

在 Windows 环境下，`write_file` 工具写入大文件（>10KB）时可能超时失败。**推荐模式**：使用 `execute_code` 中的 Python `open()` 函数写入文件，稳定可靠。

```python
# 推荐：大文件写入
with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
```

### 2026-05-21 — Web UI Windows 启动

Web UI 需**Windows 原生启动**（PowerShell/CMD），非 WSL。WSL 启动的服务器端口在 Windows 浏览器中不可访问。

```cmd
cd C:\Users\Nemo\.hermes\scripts\memory_web
python app-v3.py
```

访问 http://localhost:5000

## 参考文档

| 参考文档 | 说明 |
|------|------|
| `references/web-ui-v2-build.md` | Web UI v2.0 完整构建参考（路由、模板、实现模式） |
| `references/web-ui-v3-build.md` | Web UI v3.0 专业级重构参考（7 页面架构、API 设计、响应式 UI、测试方案） |
| `references/web-ui-v3-testing-report.md` | Web UI v3.0 测试报告（15/15 通过，测试用例详情） |
| `references/web-ui-v4-build.md` | Web UI v4.0 完整构建参考（v3→v4 改进、架构、组件库、迁移指南） |
| `references/ci-test-list-collections-fix-2026-05-23.md` | CI 测试修复记录（list_collections 懒创建问题） |
| `references/ci-test-model-loading-fix-2026-05-23.md` | **CI 测试修复记录（模型加载失败导致 AttributeError）** |
| `references/ci-test-intermittent-model-loading-2026-05-23.md` | **CI 测试诊断记录（偶发模型加载错误：竞争条件/磁盘I/O）** |
| `references/ci-push-verified-2026-05-23.md` | CI/CD 推送验证记录（Windows 环境） |
| `references/web-ui-v4-api-patterns.md` | **Web UI v4.0 API 调用模式**（args 字典参数、返回值对照、ChromaDB 直接调用） |
| `references/web-ui-backup-list-debug-2026-05-23.md` | **备份列表显示问题调试记录**（Jinja2 字典访问歧义） |
| `references/web-ui-backup-list-items-debug-2026-05-23.md` | **备份列表 items 显示问题调试记录**（Jinja2 字典访问歧义） |
| `references/web-ui-collection-count-fix-2026-05-23.md` | **集合数量显示为 0 修复记录**（storage.py list_collections 未查询实际计数） |
| `references/web-ui-search-verification-2026-05-23.md` | **搜索功能验证报告**（数据库状态、API 路由、FTS 测试结果） |
| `references/memory-md-dedupe-pattern.md` | **MEMORY.md 文本去重模式**（dedupe_memories() 局限性、周期性重复、脚本方案） |
| `references/memory-system-status-2026-05-21.md` | 记忆系统全面状态审查报告（2026-05-21） |
| `references/memory-architecture-native-vs-vector.md` | 原生记忆 vs 向量记忆架构说明与使用策略 |
| `references/tutorial-svg-generation-pattern.md` | 教程文章 SVG 配图生成模式（配色、结构、嵌入方式） |
| `references/windows-large-file-write-pattern.md` | Windows 大文件写入模式（`write_file` 超时替代方案） |

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

## 📚 2026-05-23 Web UI v4.0 重构总结

### 核心发现

1. **API 参数模式**: 所有 `vector_memory` 函数接收 `args` 字典参数，非关键字参数
2. **字段名陷阱**: 返回字段名与常见假设不同（`text` 而非 `content`，`results` 而非 `memories`）
3. **多agent超时**: `delegate_task` 子agent超时 600 秒，复杂重构任务需直接完成
4. **ChromaDB 边界条件**: `get_or_create_collection()` 可能返回 `None`，必须做 `None` 检查

### v3.0 → v4.0 改进

| 问题 | v3.0 | v4.0 修复 |
|------|------|----------|
| Toast 容器 | 所有模板缺少 | base-v4.html 统一包含 |
| CSS 特性 | 缺少现代特性 | 完整 CSS 变量主题系统 |
| JS 语法 | 无 async/await | 现代 async/await + 错误处理 |
| 模型管理 | 全局变量竞态 | ModelManager 类封装 |
| 错误处理 | 不完善 | require_model + log_operation 装饰器 |
| API 参数 | 关键字参数 | args 字典参数 |
| 字段名 | 假设错误 | 实际字段映射 + 兼容性处理 |

### 文件结构

```
memory_web/
├── app-v4.py              # Flask 应用 (28KB)
│   ├── ModelManager       # 模型加载管理
│   ├── @require_model     # 模型检查装饰器
│   ├── @log_operation     # 操作日志装饰器
│   └── API 端点           # 15+ 个 API
├── static/
│   ├── css/style-v4.css   # 完整主题系统 (22KB)
│   └── js/app-v4.js       # async/await (6KB)
└── templates/
    ├── base-v4.html       # 基础模板（含 toastContainer）
    ├── index-v4.html      # 仪表盘
    ├── search-v4.html     # 搜索
    ├── memories-v4.html   # 记忆管理
    ├── collections-v4.html # 集合管理
    ├── backup-v4.html     # 备份管理
    ├── monitor-v4.html    # 性能监控
    └── export-v4.html     # 数据导出
```

### 参考文档

- `references/web-ui-v4-api-patterns.md` - API 调用模式对照表
- `references/flask-testing-pattern.md` - Flask 测试模式
- `references/ci-push-verified-2026-05-23.md` - CI/CD 推送验证（Windows 环境）