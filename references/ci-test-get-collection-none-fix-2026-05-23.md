# CI 测试修复：`_get_collection()` 返回 `None` 导致 `AttributeError`

**日期**: 2026-05-23
**测试文件**: `scripts/test_vector_memory.py`
**失败测试**: `TestMemories::test_add_memory`

## 错误日志

```
FAILED test_vector_memory.py::TestMemories::test_add_memory - AttributeError: 'NoneType' object has no attribute 'parameters'
```

## 根本原因

在干净环境中（无预置数据），ChromaDB 的 `get_or_create_collection()` 方法在某些边界条件下可能返回 `None`。`_get_collection()` 函数直接返回该值，未做 `None` 检查，导致后续代码尝试访问 `.parameters` 等属性时崩溃。

## 修复方案

### 1. 修改 `_get_collection()` 增加 `None` 检查

```python
def _get_collection(collection_name: str = None):
    """获取或创建集合，增加 None 检查"""
    client = _get_chroma_client()
    
    if collection_name is None:
        collection_name = _current_collection_name
    
    try:
        collection = client.get_or_create_collection(name=collection_name)
        if collection is None:
            # 回退：显式创建
            collection = client.create_collection(name=collection_name)
        return collection
    except Exception as e:
        logger.error(f"_get_collection error: {e}")
        return None
```

### 2. 修改 `add_memory()` 增加空值检查

```python
def add_memory(args):
    """添加记忆，增加空值检查"""
    collection = _get_collection(args.get("collection"))
    if collection is None:
        raise ValueError(f"无法获取集合: {args.get('collection')}")
    
    # ... 继续操作
```

## 影响范围

- `add_memory()` / `add_batch()` / `add_with_chunks()`
- 任何调用 `_get_collection()` 的函数

## 验证方法

```bash
pytest scripts/test_vector_memory.py::TestMemories -v
# 应全部通过
```

## 相关修复

- `list_collections()` 默认集合懒创建问题（2026-05-23）
- `get_stats()` 计数需要手动遍历集合

## 经验总结

**ChromaDB 边界条件处理原则**：
1. 永远不要假设 `get_or_create_collection()` 一定返回有效对象
2. 在调用集合方法前，先检查返回值是否为 `None`
3. 提供回退逻辑（如显式 `create_collection()`）
4. 测试环境应模拟干净环境，避免依赖预置数据
