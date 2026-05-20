# 全方位综合测试模式

## 概述

对 Vector-Memory 系统进行 11 个维度的全方位测试，覆盖所有 10 项优化功能。

## 测试维度

| # | 测试类别 | 测试内容 | 关键断言 |
|---|----------|----------|----------|
| 1 | 基础添加和搜索 | `add_memory`, `add_batch`, `search_memories`, `list_memories` | 添加成功、搜索返回结果 |
| 2 | 0-100 分评分 | `search_memories` 返回 `relevance_score` | 分数在 0-100 范围内 |
| 3 | 多集合支持 | `create_collection`, `switch_collection`, `delete_collection`, 集合隔离 | 集合隔离搜索、删除成功 |
| 4 | 版本管理 | `add_memory` 版本递增、`get_memory_versions` | 同一 ID、版本递增 |
| 5 | 过期机制 | `get_access_stats`, `get_expired_memories`, `prune_expired_memories` | 统计正确、阈值检测 |
| 6 | 导出/备份 | `export_memories`, `backup_memories`, `list_exports`, `list_backups` | 文件存在、格式正确 |
| 7 | 摘要生成 | `generate_daily_summary` | 报告文件存在 |
| 8 | 统计信息 | `get_stats` | 总数、分类统计正确 |
| 9 | 关联表 | `link_memory`, `get_relations`, `search_related`, `unlink_memory` | 关联建立/解除成功 |
| 10 | 边界/异常 | 空搜索、空添加、删除默认集合、切换不存在集合 | 返回错误 |
| 11 | 性能测试 | `add_batch` 10 条、`search_memories` | 耗时 < 500ms |

## 测试脚本结构

```python
import sys, os, json, time, shutil
from datetime import datetime

sys.path.insert(0, os.path.expanduser('~/.hermes/skills/vector_memory/scripts'))

from vector_memory import (
    add_memory, add_batch, search_memories, list_memories, clear_memories,
    get_stats, get_access_stats, generate_daily_summary,
    create_collection, list_collections, switch_collection, delete_collection,
    link_memory, unlink_memory, get_relations, search_related,
    export_memories, backup_memories, list_exports, list_backups,
    get_expired_memories, prune_expired_memories,
    get_memory_versions, rollback_memory, clear_version_history,
)

# 测试统计
test_results = {"passed": 0, "failed": 0, "warnings": 0, "details": []}

def record_result(test_name, status, message=""):
    """记录测试结果"""
    test_results["details"].append({"test": test_name, "status": status, "message": message})
    if status == "PASS": test_results["passed"] += 1
    elif status == "FAIL": test_results["failed"] += 1
    else: test_results["warnings"] += 1
    icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
    print(f"  {icon} {test_name}: {message}")

# 1. 准备工作：清理环境
# 2. 测试 1-11：各维度测试
# 3. 生成测试报告
```

## 常见陷阱

### 1. `collection.get()` 返回 None

**问题**：ChromaDB 的 `collection.get()` 在某些情况下返回 None，导致后续 `.get('ids', [])` 调用失败。

**修复**：
```python
try:
    data = collection.get(include=['metadatas', 'documents'])
    if data is None:
        data = {'ids': [], 'metadatas': [], 'documents': []}
except Exception:
    data = {'ids': [], 'metadatas': [], 'documents': []}
```

**影响函数**：`get_stats`, `get_access_stats`, `generate_daily_summary`, `list_memories`

### 2. `_client` 为 None

**问题**：`clear_memories` 清空集合后重置 `_client = None`，后续调用仍尝试使用。

**修复**：
```python
# 使用 _get_chroma_client() 替代直接访问 _client
client = _get_chroma_client()
```

**影响函数**：`clear_memories`

### 3. 版本管理 text_hash 匹配失败

**问题**：修改文本后 text_hash 不同，无法匹配到同一记忆。

**修复**：基于 `category + device` metadata 匹配，而非 text_hash。

```python
# 版本匹配：优先匹配 metadata 标识（category + device）
for i, meta in enumerate(existing_metadatas):
    meta_category = meta.get('category')
    meta_device = meta.get('device')
    input_category = metadata.get('category')
    input_device = metadata.get('device')
    
    if (input_category and input_category == meta_category and
        input_device and input_device == meta_device):
        match_idx = i
        break
```

### 4. 集合不存在时自动创建

**问题**：ChromaDB 的 `get_or_create_collection` 会自动创建不存在的集合。

**修复**：`switch_collection` 先调用 `list_collections()` 验证集合存在，不存在则返回错误。

### 5. 测试集合名被重复使用

**问题**：测试中使用的集合名（如 `nonexistent_collection_xyz`）在多次测试后被创建，导致边界测试失效。

**修复**：使用唯一性强的集合名（如 `__definitely_not_exist_12345__`），或测试前清理。

## 测试报告格式

```
======================================================================
【测试报告】
======================================================================

  总测试数: 39
  ✅ 通过: 33
  ❌ 失败: 6
  ⚠️ 警告: 0
  通过率: 84.6%

❌ 失败详情:
  ❌ 环境清理: 'NoneType' object has no attribute '_client'
  ❌ 版本管理 - 更新: ID 相同=False, version=1, prev=None
  ...

======================================================================
全方位测试完成
======================================================================
```

## 应用建议

- 每次重大修改后运行全方位测试
- 新增功能时添加对应测试维度
- 修复 bug 后回归测试相关维度
- 测试失败时优先检查 `collection.get()` 返回值
