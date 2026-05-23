# CI 测试失败：test_list_collections 集合初始化问题

## 错误日志

```
Run cd scripts
============================= test session starts ==============================
platform linux -- Python 3.10.20, pytest-9.0.3, pluggy-1.6.0 -- /opt/hostedtoolcache/Python/3.10.20/x64/bin/python
cachedir: .pytest_cache
rootdir: /home/runner/work/vector-memory/vector-memory/scripts
plugins: anyio-4.13.0
collecting ... collected 19 items

test_vector_memory.py::TestCore::test_version PASSED                     [  5%]
test_vector_memory.py::TestCore::test_locks_present PASSED               [ 10%]
test_vector_memory.py::TestCollections::test_list_collections FAILED     [ 15%]

=================================== FAILURES ===================================
____________________ TestCollections.test_list_collections _____________________
test_vector_memory.py:50: in test_list_collections
    assert any(c.get("name") == "memories" for c in collections)
E   assert False
E    +  where False = any(<generator object TestCollections.test_list_collections.<locals>.<genexpr> at 0x7f8c7abf3680>)
=============================== warnings summary ===============================
test_vector_memory.py::TestCollections::test_list_collections
  /opt/hostedtoolcache/Python/3.10.20/x64/lib/python3.10/site-packages/opentelemetry/util/_importlib_metadata.py:32: DeprecationWarning: SelectableGroups dict interface is deprecated. Use select.
    return EntryPoints(ep for group_eps in eps.values() for ep in group_eps)

-- Docs: https://pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED test_vector_memory.py::TestCollections::test_list_collections - assert False
 +  where False = any(<generator object TestCollections.test_list_collections.<locals>.<genexpr> at 0x7f8c7abf3680>)
!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
==================== 1 failed, 2 passed, 1 warning in 1.34s ====================
Error: Process completed with exit code 1.
```

## 问题诊断

### 测试代码（test_vector_memory.py:50）

```python
def test_list_collections(self):
    """测试列出集合"""
    result = vm.list_collections()
    assert result["success"]
    collections = result.get("collections", [])
    assert len(collections) > 0
    # 检查默认集合 "memories" 是否存在
    assert any(c.get("name") == "memories" for c in collections)
```

### 失败原因

`list_collections()` 返回空列表 `[]`，因为：

1. **ChromaDB 懒创建机制**：集合只在首次写入数据时创建
2. **CI 环境是干净的**：没有预置数据，`memories` 集合不存在
3. **测试期望默认集合存在**：断言检查 `memories` 集合，但实际没有

## 解决方案

### 方案 1：在 storage.py 的 list_collections() 中添加默认集合初始化

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

### 方案 2：在测试前预置数据

```python
# test_vector_memory.py
@pytest.fixture(autouse=True)
def ensure_default_collection():
    """确保默认集合存在"""
    from storage import _get_collection
    _get_collection("memories")  # 触发创建
    yield
```

### 方案 3：修改测试断言（不推荐）

```python
# 允许没有默认集合
collections = result.get("collections", [])
if len(collections) > 0:
    assert any(c.get("name") == "memories" for c in collections)
```

## 推荐方案

**方案 1** 是最优解，因为：
- ✅ 符合用户预期：`list_collections()` 应该返回可用的集合列表
- ✅ 测试通过：CI 环境自动初始化默认集合
- ✅ 生产友好：用户首次使用时无需手动创建集合

## 验证

```bash
# 本地测试
pytest scripts/test_vector_memory.py::TestCollections::test_list_collections -v

# 预期输出
test_vector_memory.py::TestCollections::test_list_collections PASSED

# 完整测试
pytest scripts/test_vector_memory.py -v
# 预期：19 passed, 1 warning
```

## 相关文件

- `scripts/storage.py` — 需要修改 `list_collections()` 函数
- `scripts/test_vector_memory.py` — 测试文件
- `scripts/vector_memory.py` — 主入口

## 教训

1. **ChromaDB 懒创建**：不要在测试中假设集合已存在
2. **CI 环境隔离**：CI 是干净环境，不能依赖本地数据
3. **默认集合策略**：核心功能应确保默认状态可用
4. **测试断言**：断言应反映实际行为，而非假设

## 更新日志

| 日期 | 变更 |
|------|------|
| 2026-05-23 | 初始记录 CI 测试失败 |
| 2026-05-23 | 添加 storage.py list_collections() 修复方案 |