# Web UI v4.0 API 调用模式

## 核心发现

`vector_memory` 模块的所有函数都接收 **`args` 字典参数**，而非关键字参数！

## API 调用对照表

| 函数 | ❌ 错误调用 | ✅ 正确调用 |
|------|------------|------------|
| `list_collections` | `vm.list_collections()` | `vm.list_collections(args=None)` |
| `list_memories` | `vm.list_memories(limit=100)` | `vm.list_memories({"limit": 100})` |
| `search_memories` | `vm.search(query, top_k=10)` | `vm.search_memories({"text": query, "top_k": 10})` |
| `add_memory` | `vm.add_memory(content, collection="x")` | `vm.add_memory({"text": content, "collection": "x"})` |
| `get_memory` | `vm.get_memory(id)` | `collection.get(ids=[id], include=['documents', 'metadatas'])` |
| `delete_memory` | `vm.delete_memory(id)` | `collection.delete(ids=[id])` |
| `create_collection` | `vm.create_collection(name)` | `vm.create_collection({"name": name})` |
| `switch_collection` | `vm.switch_collection(name)` | `vm.switch_collection({"collection": name})` |
| `delete_collection` | `vm.delete_collection(name)` | `vm.delete_collection({"name": name})` |
| `backup_memories` | `vm.backup(path)` | `vm.backup_memories({"backup_dir": path})` |
| `restore_memories` | `vm.restore(path)` | `vm.restore_memories({"backup_dir": path})` |
| `export_memories` | `vm.export(format, collection)` | `vm.export_memories({"format": format, "collection": coll})` |
| `import_from_memory_md` | `vm.import_data(path)` | `vm.import_from_memory_md({"filepath": path})` |

## 返回值对照表

| 函数 | 返回字段 | 说明 |
|------|---------|------|
| `list_collections` | `{"collections": [name1, name2], "count": 2}` | 返回集合名称列表，**不是**带 count 的对象 |
| `list_memories` | `{"results": [...], "count": N}` | 返回 `results` 不是 `memories` |
| `search_memories` | `{"results": [...], "count": N}` | results 包含 id, text, metadata, score |
| `add_memory` | `{"success": True, "memory_id": "..."}` | 返回 memory_id |
| `export_memories` | `{"success": True, "content": "..."}` | 返回 `content` 不是 `data` |

## 直接调用 ChromaDB 方法

某些操作需要直接调用 collection 对象：

```python
# 获取 collection 对象
collection = vm._get_collection(collection_name)

# 获取单条记忆
data = collection.get(ids=[memory_id], include=['documents', 'metadatas'])
memory = {
    "id": data['ids'][0],
    "content": data['documents'][0],
    "metadata": data['metadatas'][0]
}

# 删除记忆
collection.delete(ids=[memory_id])

# 列出所有记忆
data = collection.get(include=['metadatas', 'documents'])
```

## 独立模块调用

某些功能在独立模块中，需直接导入：

```python
# 生成报告
from generate_report import generate_report
report = generate_report("daily")

# 备份管理
from backup_memory import create_backup, list_backups, restore_backup
backups = list_backups()
```

## ⚠️ 字段名陷阱排查清单（2026-05-23 实际 Bug）

### 陷阱 1：`created_at` 和 `collection` 在 metadata 内部

`list_memories` 返回 `{id, text, metadata}`，关键字段埋在 metadata 里：

```python
# 实际返回
{
    "id": "abc123",
    "text": "记忆内容",
    "metadata": {"created_at": "2026-05-23", "collection": "default", ...}
}

# ❌ 模板中这样写会报 UndefinedError
{{ mem.created_at }}

# ✅ 必须用
{{ mem.metadata.created_at }}
{{ mem.metadata.collection }}
```

**Web UI 兼容性处理方案**（在后端补全字段）：
```python
for m in results:
    meta = m.get("metadata", {})
    m["created_at"] = meta.get("created_at", "-")
    m["collection"] = meta.get("collection", current_collection)
```

### 陷阱 2：`list_collections` 返回字符串列表，非字典列表

```python
# 实际返回
["default", "monitor", "fire"]

# ❌ 遍历时用 c.get("count") → AttributeError: 'str' has no 'get'
for c in collections:
    count = c.get("count")  # 报错！

# ✅ 必须做类型检测 + 转换
def format_collections(raw_collections):
    formatted = []
    for c in raw_collections:
        if isinstance(c, str):
            formatted.append({"name": c, "count": 0})
        elif isinstance(c, dict):
            formatted.append(c)
    return formatted
```

### 陷阱 3：`get_stats` 需要手动遍历每个集合计数

因为 `list_collections` 返回字符串，无法直接获取每个集合的记忆数：

```python
# ❌ 这样 total_memories 永远是 0
collections = vm.list_collections()
total = sum(c.get("count", 0) for c in collections)  # 每个 c 是 str，count 恒为 0

# ✅ 正确的统计方式
collections = vm.list_collections()
total = 0
for name in collections:
    if isinstance(name, str):
        result = vm.list_memories({"collection": name, "limit": 0})
        count = result.get("count", 0)
        total += count
    # ...
```

### 陷阱 4：搜索结果的 collection 字段缺失

`search_memories` 的 results 中**没有 `collection` 字段**，模板里 `item.collection` 永远是 undefined：

```python
# 实际返回的搜索结果
{
    "id": "...",
    "text": "...",
    "metadata": {"key": "value"},
    "score": 0.85
    # ❌ 没有 collection 字段
}

# ✅ 后端必须手动补上（从当前活动集合取）
results = vm.search_memories({"text": query, "collection": coll_name})
for r in results.get("results", []):
    r["collection"] = coll_name  # 手动注入
```

### 陷阱 5：backup_memories 自动创建备份目录（不需手动建）

`backup_memories` 函数**内部已自动创建目录**（`os.makedirs(backup_dir, exist_ok=True)`），不需要调用前手动创建：

```python
# ✅ 直接调用即可
result = vm.backup_memories({"backup_dir": backup_path})
# backup_memories 内部自动创建目录

# ✅ 读取 backup_memories 已创建的 manifest.json（不要自己新建覆盖）
manifest_path = os.path.join(backup_path, "manifest.json")
if os.path.exists(manifest_path):
    manifest = json.load(open(manifest_path))  # 已含实际备份项目
```

### 陷阱 6：restore_memories 默认 dry_run=True（只预览不恢复）

`restore_memories` 的 `dry_run` 参数默认为 `True`，即只预览恢复内容而不实际恢复：

```python
# ❌ dry_run=True (默认) — 只预览，不恢复
result = vm.restore_memories({"backup_dir": path})
# result.success = True, 但没有文件被实际恢复

# ✅ 实际恢复必须显式设置 dry_run=False
result = vm.restore_memories({"backup_dir": path, "dry_run": False})
```

### 陷阱 6：list_memories 不支持文本过滤

`list_memories` 只支持按 `collection` 和 `limit` 分页，**不支持搜索文本过滤**：

```python
# ❌ 想搜包含特定文本的记忆
vm.list_memories({"limit": 100, "query": "硬盘"})  # query 参数被忽略

# ✅ 正确的过滤方式（内存侧过滤）
all_mems = vm.list_memories({"collection": coll, "limit": 1000})
filtered = [m for m in all_mems.get("results", [])
            if "硬盘" in m.get("text", "")]
```

---

## 后端字段兼容层模式（v4.0 推荐）

在 Flask 路由中统一处理字段映射，避免模板和 API 反复踩坑：

```python
@app.route('/api/memories')
def api_memories_list():
    result = vm.list_memories({"collection": coll, "limit": limit})
    memories = result.get("results", [])
    formatted = []
    for m in memories:
        meta = m.get("metadata", {})
        formatted.append({
            "id": m["id"],
            "text": m.get("text", ""),
            "content": m.get("text", ""),  # 兼容旧模板
            "created_at": meta.get("created_at", ""),
            "collection": meta.get("collection", coll),
            "metadata": meta
        })
    return jsonify({"success": True, "results": formatted, "count": len(formatted)})
```

## Web UI v4.0 架构

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

## v3.0 → v4.0 修复总结

| 问题 | v3.0 | v4.0 修复 |
|------|------|----------|
| Toast 容器 | 所有模板缺少 | base-v4.html 统一包含 |
| CSS 特性 | 缺少现代特性 | 完整 CSS 变量主题系统 |
| JS 语法 | 无 async/await | 现代 async/await + 错误处理 |
| 模型管理 | 全局变量竞态 | ModelManager 类封装 |
| 错误处理 | 不完善 | require_model + log_operation 装饰器 |
| API 参数 | 关键字参数 | args 字典参数 |
| 返回值 | 假设错误字段 | 实际字段映射 |

## 测试模式

```python
from flask import Flask
# 使用 test_client() 测试，无需启动服务器
client = app.test_client()
response = client.get('/')
assert response.status_code == 200
```
