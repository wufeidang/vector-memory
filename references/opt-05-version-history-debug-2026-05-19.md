# opt-05 版本历史调试记录（2026-05-19）

## 问题概述

在实现记忆版本管理时，发现版本历史保存不完整的问题：
- 添加 v1 后，版本历史为空
- 更新为 v2 后，版本历史有 1 个条目
- 更新为 v3 后，版本历史仍有 1 个条目（期望 3 个）

## 调试过程

### 第一步：检查缩进

**症状**：版本历史只保存 v1，后续更新未追加。

**发现**：`add_memory()` 中保存旧版本的代码缩进错误：

```python
# ❌ 错误代码
if existing_id not in history:
    history[existing_id] = []
# 从 collection 获取旧版本的文本
    old_data = collection.get(ids=[existing_id], include=['documents', 'metadatas'])
    old_text = old_data.get('documents', [''])[0] if old_data.get('documents') else ''
    
    history[existing_id].append({
        "version": old_version,
        ...
    })
```

`collection.get()` 和 `append()` 被错误地缩进在 `if` 块内，导致：
- 只有当 `existing_id` 不在 `history` 中时（即第一次更新）才会执行
- 后续更新时，因为 `existing_id` 已在 `history` 中，跳过整个块

**修复**：

```python
# ✅ 正确代码
if existing_id not in history:
    history[existing_id] = []
# 从 collection 获取旧版本的文本
old_data = collection.get(ids=[existing_id], include=['documents', 'metadatas'])
old_text = old_data.get('documents', [''])[0] if old_data.get('documents') else ''

history[existing_id].append({
    "version": old_version,
    ...
})
```

### 第二步：测试 v1 创建

**症状**：添加 v1 后，版本历史为空。

**发现**：`add_memory()` 的 `else` 分支（新记忆）中没有初始化版本历史。

**修复**：在 `else` 分支中添加：

```python
# 新记忆 - 初始化版本历史
history = _load_version_history()
history[doc_id] = [{
    "version": 1,
    "text_hash": text_hash,
    "text": text,
    "metadata": metadata,
    "timestamp": metadata.get('created_at', '')
}]
_save_version_history(history)
```

### 第三步：测试 clear_memories() 后缓存问题

**症状**：清空记忆后，再次添加时版本匹配失败。

**发现**：`clear_memories()` 执行 `client.delete_collection("memories")` 后，全局变量 `_client` 和 `_collection` 仍指向已删除的对象。

**修复**：

```python
def clear_memories(args=None):
    client = _get_client()
    client.delete_collection("memories")
    
    # 重置全局缓存
    global _client, _collection
    _client = None
    _collection = None
    
    _save_version_history({})
    _save_relations({})
    
    return {"success": True, "message": "所有记忆已清空"}
```

## 测试用例

```python
import os, sys, importlib.util

script_path = os.path.expanduser('~/.hermes/skills/vector_memory/scripts/vector_memory.py')
spec = importlib.util.spec_from_file_location("vm", script_path)
vm = importlib.util.module_from_spec(spec)
sys.modules["vm"] = vm
spec.loader.exec_module(vm)

# 清空
vm._save_version_history({})
vm._collection.delete(ids=vm._collection.get()['ids'])

# 测试 v1
vm.add_memory({'text': "POE供电故障排查指南", 'metadata': {"category": "监控维修"}})
history = vm._load_version_history()
assert len(list(history.keys())) == 1, "v1 后应有 1 个版本历史"

# 测试 v2
vm.add_memory({'text': "POE供电故障排查指南（修订版）", 'metadata': {"category": "监控维修"}})
history = vm._load_version_history()
doc_id = list(history.keys())[0]
assert len(history[doc_id]) == 2, f"v2 后应有 2 个版本，实际 {len(history[doc_id])}"

# 测试 v3
vm.add_memory({'text': "POE供电故障排查指南（最终版）", 'metadata': {"category": "监控维修"}})
history = vm._load_version_history()
assert len(history[doc_id]) == 3, f"v3 后应有 3 个版本，实际 {len(history[doc_id])}"

print("✅ 所有测试通过")
```

## 关键教训

1. **缩进陷阱**：Python 中嵌套在 `if` 块内的代码只在条件满足时执行。语法检查可能通过，但逻辑会出错。
2. **版本历史初始化**：新记忆创建时必须初始化版本历史，否则后续更新无法记录。
3. **全局缓存重置**：删除 ChromaDB 集合后必须重置 `_client` 和 `_collection` 缓存。
4. **测试驱动**：每项功能必须有测试用例验证，不能仅凭代码通过语法检查就认为完成。

## 文件位置

- 核心脚本：`~/.hermes/skills/vector_memory/scripts/vector_memory.py`
- 版本历史文件：`~/.hermes/vector_store/version_history.json`
- 关联表文件：`~/.hermes/vector_store/relations.json`