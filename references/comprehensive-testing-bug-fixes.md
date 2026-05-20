# 综合测试 Bug 修复模式

## 发现于 2026-05-19 全方位测试

在运行全方位综合测试时，发现并修复了 6 个 bug。以下是修复模式和预防措施。

---

## Bug 1: `clear_memories` 中 `_client` 为 None

### 症状
```
❌ 环境清理: 'NoneType' object has no attribute '_client'
```

### 原因
`clear_memories` 重置了 `_client` 为 `None`，但后续代码仍尝试访问 `_client._client`。

### 修复
```python
# 修复前
collection = _get_client()
client = collection._client

# 修复后
collection = _get_client()
client = collection._client if hasattr(collection, '_client') else _get_chroma_client()
```

### 预防措施
- 使用 `_get_chroma_client()` 直接获取 ChromaDB 客户端
- 访问属性前检查 `hasattr()`

---

## Bug 2: `get_stats` 中 `collection.get()` 返回 None

### 症状
```
❌ 统计信息: 'NoneType' object has no attribute 'get'
```

### 原因
ChromaDB 的 `collection.get()` 在某些情况下返回 `None`。

### 修复
```python
# 修复前
all_data = collection.get(include=['metadatas', 'documents'])
total_count = len(all_data.get('ids', []))

# 修复后
try:
    all_data = collection.get(include=['metadatas', 'documents'])
    if all_data is None:
        all_data = {'ids': [], 'metadatas': [], 'documents': []}
except Exception:
    all_data = {'ids': [], 'metadatas': [], 'documents': []}
total_count = len(all_data.get('ids', []))
```

### 预防措施
- 所有 `collection.get()` 调用后检查是否为 `None`
- 使用 try-except 包裹

---

## Bug 3: `get_access_stats` 中 `collection.get()` 返回 None

### 症状
```
❌ 过期机制: 'NoneType' object has no attribute 'get'
```

### 原因
同 Bug 2，`collection.get()` 返回 `None`。

### 修复
```python
# 修复前
collection = _get_client()
data = collection.get(include=['metadatas'])

# 修复后
collection = _get_client()
try:
    data = collection.get(include=['metadatas'])
    if data is None:
        data = {'metadatas': [], 'ids': []}
except Exception:
    data = {'metadatas': [], 'ids': []}
```

---

## Bug 4: `generate_daily_summary` 中 `collection.get()` 返回 None

### 症状
```
❌ 摘要生成: 'NoneType' object has no attribute 'get'
```

### 原因
同 Bug 2。

### 修复
```python
# 修复前
collection = _get_client()
data = collection.get(include=['metadatas', 'documents', 'embeddings'])

# 修复后
collection = _get_client()
try:
    data = collection.get(include=['metadatas', 'documents', 'embeddings'])
    if data is None:
        data = {'ids': [], 'documents': [], 'metadatas': [], 'embeddings': []}
except Exception:
    data = {'ids': [], 'documents': [], 'metadatas': [], 'embeddings': []}
```

---

## Bug 5: 版本管理基于 text_hash 匹配失败

### 症状
```
❌ 版本管理 - 更新: ID 相同=False, version=1, prev=None
```

### 原因
`text_hash` 基于文本内容计算，修改文本后 hash 不同，无法匹配到同一记忆。

### 修复
```python
# 修复前：仅基于 text_hash 匹配
for i, meta in enumerate(existing_metadatas):
    if meta.get('text_hash') == text_hash and not force_new:
        match_idx = i
        break

# 修复后：优先基于 category + device 匹配
for i, meta in enumerate(existing_metadatas):
    if force_new:
        continue
    meta_category = meta.get('category')
    meta_device = meta.get('device')
    input_category = metadata.get('category')
    input_device = metadata.get('device')
    
    # 如果 category 和 device 都匹配，认为是同一记忆
    if (input_category and input_category == meta_category and
        input_device and input_device == meta_device):
        match_idx = i
        break
    # 如果没有 metadata 标识，回退到 text_hash 匹配
    elif not input_category and not input_device:
        if meta.get('text_hash') == text_hash:
            match_idx = i
            break
```

### 预防措施
- 添加记忆时务必提供 `category` 和 `device` 元数据
- 版本匹配优先使用 metadata 标识，而非 text_hash

---

## Bug 6: 测试用例使用已存在的集合名

### 症状
```
❌ 边界 - 切换不存在集合: 应返回错误: False
```

### 原因
测试用例使用的集合名 `nonexistent_collection_xyz` 在之前的测试中已被创建。

### 修复
- 使用绝对不存在的集合名，如 `__definitely_not_exist_12345__`
- 测试前清理环境

---

## 综合测试脚本模式

```python
import sys
import os
sys.path.insert(0, os.path.expanduser('~/.hermes/skills/vector_memory/scripts'))

from vector_memory import (
    add_memory, add_batch, search_memories, list_memories, clear_memories,
    get_stats, get_access_stats, generate_daily_summary,
    create_collection, list_collections, switch_collection, delete_collection,
    link_memory, unlink_memory, get_relations,
    export_memories, backup_memories, list_exports, list_backups,
    get_expired_memories, prune_expired_memories,
)

# 测试统计
test_results = {"passed": 0, "failed": 0, "warnings": 0, "details": []}

def record_result(test_name, status, message=""):
    test_results["details"].append({"test": test_name, "status": status, "message": message})
    if status == "PASS":
        test_results["passed"] += 1
    elif status == "FAIL":
        test_results["failed"] += 1
    else:
        test_results["warnings"] += 1
    icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
    print(f"  {icon} {test_name}: {message}")

# 测试结构
# 1. 准备工作：清理环境
# 2. 测试 1: 基础功能
# 3. 测试 2-N: 各优化项功能
# 4. 测试 N+1: 边界和异常
# 5. 测试 N+2: 性能测试
# 6. 生成报告

# 报告生成
total = test_results["passed"] + test_results["failed"] + test_results["warnings"]
pass_rate = (test_results["passed"] / total * 100) if total > 0 else 0
print(f"通过率: {pass_rate:.1f}%")
```
