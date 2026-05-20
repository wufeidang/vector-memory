# opt-08: 多集合支持（按项目/类别分集合）

**完成时间**: 2026-05-19  
**状态**: ✅ 全部通过测试

## 功能目标

支持按项目/类别分集合存储记忆，实现数据隔离和分类管理。

## 新增 API

| 函数 | 说明 |
|------|------|
| `create_collection(args)` | 创建新集合 |
| `list_collections(args)` | 列出所有集合及数量 |
| `delete_collection(args)` | 删除集合（默认 memories 不可删除） |
| `switch_collection(args)` | 切换当前活跃集合 |
| `get_current_collection(args)` | 获取当前活跃集合名 |

## 核心修改

### 1. 新增 `_get_chroma_client()` 函数

**关键发现**：`_get_client()` 返回的是 `Collection` 对象，不是 `Client` 对象！

```python
# ❌ 错误 - _get_client() 返回 Collection
def _get_client():
    global _client, _collection
    if _client is None:
        _client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        _collection = _client.get_or_create_collection("memories")
    return _collection  # 返回的是 Collection

# ✅ 正确 - 新增 _get_chroma_client() 返回 Client
def _get_chroma_client():
    """获取 ChromaDB Client 对象（用于多集合管理）。"""
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    return _client  # 返回的是 Client
```

**影响范围**：所有集合管理函数（`list_collections`, `create_collection`, `delete_collection`, `switch_collection`）必须使用 `_get_chroma_client()` 而不是 `_get_client()`。

### 2. 新增 `_get_collection(name)` 函数

```python
def _get_collection(name=None):
    """获取指定名称的集合，不存在则自动创建。"""
    if name is None:
        name = _current_collection_name
    
    client = _get_chroma_client()
    try:
        return client.get_or_create_collection(name=name)
    except Exception as e:
        print(f"⚠️ 获取集合 '{name}' 失败: {str(e)[:100]}")
        # 回退到默认集合
        return client.get_or_create_collection(name="memories")
```

### 3. 全局活跃集合变量

```python
# 当前活跃集合名（默认 "memories"）
_current_collection_name = "memories"
```

### 4. 核心函数更新

所有核心函数需要支持 `collection` 参数，并默认使用当前活跃集合：

```python
def add_memory(args):
    text = args.get('text')
    metadata = args.get('metadata', {})
    collection_name = args.get('collection')  # 显式指定集合
    # 如果未显式指定，使用当前活跃集合
    if collection_name is None:
        collection_name = _current_collection_name
    # ...
    collection = _get_collection(collection_name)
```

**需要更新的函数列表**：
- `add_memory()`
- `add_batch()`
- `add_with_chunks()`
- `search_memories()`
- `list_memories()`
- `clear_memories()`
- `import_from_memory_md()`
- `dedupe_memories()`
- `get_stats()`

## 使用方式

### 方式 1: 切换当前活跃集合

```python
# 切换到 monitor 集合
switch_collection({"name": "monitor"})

# 之后的所有操作都在 monitor 集合中进行
add_memory({"text": "POE 交换机故障排查..."})
search_memories({"text": "POE"})

# 切换回 fire_safety 集合
switch_collection({"name": "fire_safety"})
add_memory({"text": "消防泵房巡检..."})
```

### 方式 2: 显式指定 collection 参数

```python
# 当前在 fire_safety 集合
switch_collection({"name": "fire_safety"})

# 但显式指定到 monitor 集合
add_memory({
    "text": "监控摄像头安装...",
    "collection": "monitor"  # 显式指定
})
```

## 测试验证

| 测试项 | 结果 |
|--------|------|
| 创建 `monitor` 和 `fire_safety` 集合 | ✅ |
| 切换到 `monitor` 添加 2 条记忆 | ✅ |
| 切换到 `fire_safety` 添加 2 条记忆 | ✅ |
| 在 `monitor` 中搜索只返回 POE/NVR | ✅ 无交叉污染 |
| 在 `fire_safety` 中搜索只返回消防 | ✅ 无交叉污染 |
| 显式指定 `collection` 参数 | ✅ |

## 调试记录

### 问题 1: `'Collection' object has no attribute 'list_collections'`

**症状**: `list_collections()` 调用失败

**原因**: 使用了 `_get_client()` 获取的 `Collection` 对象调用 `list_collections()`

**修复**: 所有集合管理函数改用 `_get_chroma_client()`

### 问题 2: 数据写入错误集合

**症状**: 切换到 `monitor` 集合后添加记忆，但数据实际写入了 `memories` 集合

**原因**: `add_memory()` 中 `collection_name` 从 `args.get('collection')` 获取，但未默认到 `_current_collection_name`

**修复**: 添加默认值逻辑：
```python
if collection_name is None:
    collection_name = _current_collection_name
```

## 参考

- ChromaDB 文档: https://docs.trychroma.com/
- `~/.hermes/vector_store/` → 多集合共享同一持久化目录
