# search_memories / list_memories 返回 id 字段修复

## 问题描述

2026-05-18 发现 `search_memories()` 和 `list_memories()` 返回结果中**缺少 `id` 字段**，导致无法建立知识链关联。

## 根因

ChromaDB 的 `collection.query()` 和 `collection.peek()` 默认返回 `ids` 字段，但原代码未从结果中提取并包含在返回字典中。

## 修复内容

### 1. list_memories()

**修复前**：
```python
def list_memories(args):
    result = collection.peek(limit=limit if limit else 10)
    docs = result.get('documents', [])
    metas = result.get('metadatas', [])
    formatted = []
    for i, doc in enumerate(docs):
        formatted.append({
            "text": doc,
            "metadata": metas[i] if i < len(metas) else {}
        })
    return {"success": True, "results": formatted, "count": len(docs)}
```

**修复后**：
```python
def list_memories(args):
    result = collection.peek(limit=limit if limit else 10)
    docs = result.get('documents', [])
    metas = result.get('metadatas', [])
    ids = result.get('ids', [])
    formatted = []
    for i, doc in enumerate(docs):
        formatted.append({
            "id": ids[i] if i < len(ids) else None,
            "text": doc,
            "metadata": metas[i] if i < len(metas) else {}
        })
    return {"success": True, "results": formatted, "count": len(docs)}
```

### 2. search_memories()

**修复 1**：提取 `ids` 字段
```python
results = collection.query(**query_kwargs)
docs = results.get('documents', [[]])[0]
metas = results.get('metadatas', [[]])[0]
dists = results.get('distances', [[]])[0]
ids = results.get('ids', [[]])[0]  # 新增
```

**修复 2**：formatted.append 包含 id
```python
formatted.append({
    "id": ids[orig_idx] if ids and orig_idx < len(ids) else None,
    "text": doc,
    "metadata": metas[orig_idx] if metas else {},
    "score": float(score),
    ...
})
```

## 验证

修复后：
```python
result = search_memories({"text": "POE", "top_k": 3})
# 返回结果包含 id 字段
# {'id': '1779113864842', 'text': '...', 'metadata': {...}, 'score': 0.229...}
```

## 影响

- `link_memory()` 需要 `from_id` 和 `to_id`，修复后能正确获取 ID
- `get_knowledge_chain()` 需要记忆 ID，修复后能正确查询
- `search_related()` 需要记忆 ID，修复后能正确返回相关记忆

## 参考

- ChromaDB API: `collection.query()` 返回字段文档
- `references/chromadb-api-quirks.md`

---
*创建时间: 2026-05-18*
*来源: vector_memory 调试记录*
