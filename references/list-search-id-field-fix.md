# list_memories / search_memories 返回 id 字段修复

## 问题描述

`list_memories()` 和 `search_memories()` 返回的结果中缺少 `id` 字段，导致无法建立知识链关联。

### 症状

```python
result = vm.list_memories({})
# 返回: {'success': True, 'results': [{'text': ..., 'metadata': ...}], 'count': N}
# 缺少: 'id' 字段

result = vm.search_memories({"text": "POE", "top_k": 3})
# 返回: {'success': True, 'results': [{'text': ..., 'metadata': ..., 'score': ...}], 'count': N}
# 缺少: 'id' 字段
```

### 影响

- 无法获取记忆的唯一标识符
- `link_memory()`、`get_knowledge_chain()`、`search_related()` 无法工作
- 知识链功能失效

## 原因

### list_memories

使用 `collection.peek()` 获取数据，但 `formatted.append()` 中只添加了 `text` 和 `metadata`，未添加 `id`。

### search_memories

使用 `collection.query()` 获取数据，但：
1. `collection.query()` 返回的 `ids` 未被提取
2. `formatted.append()` 中未添加 `id` 字段

## 修复方案

### list_memories 修复

```python
def list_memories(args):
    limit = args.get('limit')
    collection = _get_client()
    result = collection.peek(limit=limit if limit else 10)
    docs = result.get('documents', [])
    metas = result.get('metadatas', [])
    ids = result.get('ids', [])  # ✅ 添加：提取 ids
    
    formatted = []
    for i, doc in enumerate(docs):
        formatted.append({
            "id": ids[i] if i < len(ids) else None,  # ✅ 添加：包含 id
            "text": doc,
            "metadata": metas[i] if i < len(metas) else {}
        })
    return {"success": True, "results": formatted, "count": len(docs)}
```

### search_memories 修复

```python
def search_memories(args):
    # ... 前面的代码 ...
    
    results = collection.query(**query_kwargs)
    docs = results.get('documents', [[]])[0]
    metas = results.get('metadatas', [[]])[0]
    dists = results.get('distances', [[]])[0]
    ids = results.get('ids', [[]])[0]  # ✅ 添加：提取 ids
    
    # ... 计算分数 ...
    
    formatted = []
    for rank, (orig_idx, score, doc, vs, ts) in enumerate(indexed[:top_k]):
        formatted.append({
            "id": ids[orig_idx] if ids and orig_idx < len(ids) else None,  # ✅ 添加：包含 id
            "text": doc,
            "metadata": metas[orig_idx] if metas else {},
            "score": float(score),
            "vector_score": float(vs),
            "tfidf_score": float(ts),
            "rank": rank + 1
        })
    
    return {"success": True, "results": formatted, "count": len(formatted)}
```

## 验证

修复后，`list_memories` 和 `search_memories` 应返回包含 `id` 的结果：

```python
result = vm.list_memories({})
for m in result['results']:
    print(m['id'])  # 应输出类似: 1779113864842

result = vm.search_memories({"text": "POE", "top_k": 3})
for r in result['results']:
    print(r['id'])  # 应输出类似: 1779113864842
```

## 知识链功能验证

```python
# 获取文章 ID
all_memories = vm.list_memories({})
article_ids = [m['id'] for m in all_memories['results'] 
               if m.get('metadata', {}).get('type') == 'article']

# 建立关联
if len(article_ids) >= 2:
    vm.link_memory({'from_id': article_ids[0], 'to_id': article_ids[1]})

# 查询知识链
chain = vm.get_knowledge_chain({'id': article_ids[0]})
print(chain['chain']['relations'])  # 应显示关联的记忆
```

## 调试技巧

如果修复后仍然没有 `id`，检查：

1. **collection.query 是否返回 ids**：
   ```python
   results = collection.query(query_embeddings=[emb], n_results=5, include=['documents', 'metadatas', 'distances'])
   print(results.keys())  # 应包含 'ids'
   ```

2. **ids 是否为空列表**：
   ```python
   ids = results.get('ids', [[]])[0]
   print(f"ids length: {len(ids)}")  # 应 > 0
   ```

3. **formatted.append 是否正确添加 id**：
   ```python
   # 在循环中添加调试
   print(f"orig_idx={orig_idx}, ids={ids}, len(ids)={len(ids) if ids else 0}")
   ```

---
*创建时间: 2026-05-18*
*来源: vector_memory 技能开发过程中的调试记录*
