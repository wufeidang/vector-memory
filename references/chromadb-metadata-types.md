# ChromaDB 元数据类型限制

## 问题描述

ChromaDB 的元数据（metadata）字段**仅支持基本类型**，不支持嵌套对象：

| 类型 | 支持 | 说明 |
|------|------|------|
| `str` | ✅ | 字符串 |
| `int` | ✅ | 整数 |
| `float` | ✅ | 浮点数 |
| `bool` | ✅ | 布尔值 |
| `dict` | ❌ | 嵌套对象 |
| `list` of dict | ❌ | 对象列表 |
| `list` of str/int/float/bool | ✅ | 基本类型列表 |

## 错误示例

```python
# ❌ 错误 - 元数据包含嵌套 dict
collection.update(
    ids=["doc1"],
    metadatas=[{"relations": [{"to": "doc2", "type": "related"}]}]
)
# ValueError: Expected metadata list value for key 'relations' to contain only str, int, float, or bool
```

## 解决方案

### 方案 1：JSON 序列化（推荐）

将嵌套对象序列化为 JSON 字符串：

```python
import json

# 写入时序列化
meta['relations'] = meta.get('relations', [])
meta['relations'].append(json.dumps({'to': to_id, 'type': relation}))
collection.update(ids=[from_id], metadatas=[meta])

# 读取时反序列化
relations = meta.get('relations', [])
for rel_str in relations:
    rel = json.loads(rel_str)
    to_id = rel.get('to')
    rel_type = rel.get('type')
```

### 方案 2：扁平化字段

将关联信息拆分为多个基本类型字段：

```python
# 写入
meta['relation_to_1'] = "doc2"
meta['relation_type_1'] = "related"
meta['relation_to_2'] = "doc3"
meta['relation_type_2'] = "refers"

# 读取
for i in range(1, max_relations + 1):
    to = meta.get(f'relation_to_{i}')
    if to:
        rel_type = meta.get(f'relation_type_{i}')
```

**缺点**：需要预定义最大关联数，扩展性差。

### 方案 3：使用 separate 集合

为关系建立独立的集合：

```python
# 主集合存储记忆
# 关系集合存储关联
rel_coll = client.get_collection("relations")
rel_coll.add(
    ids=[str(uuid.uuid4())],
    metadatas=[{"from": "doc1", "to": "doc2", "type": "related"}]
)
```

**缺点**：查询时需要跨集合 join，性能较差。

## 最佳实践

对于向量化记忆系统，**推荐方案 1（JSON 序列化）**：
- 保持数据结构灵活
- 无需预定义字段
- 序列化/反序列化开销小
- 兼容 ChromaDB 类型限制

## 相关修复

2026-05-18 修复了 `vector_memory.py` 中的以下函数：
- `link_memory()` - 序列化 relations
- `unlink_memory()` - 反序列化过滤
- `get_knowledge_chain()` - 反序列化解析
- `search_memories()` - 添加 id 字段返回
- `list_memories()` - 添加 id 字段返回

## 参考文档

- ChromaDB 官方文档：https://docs.trychroma.com/usage-guide#metadata
- ChromaDB API quirks: `references/chromadb-api-quirks.md`
- ID 字段修复: `references/search-memories-id-field-fix.md`

---
*创建时间: 2026-05-18*
*来源: vector_memory 调试记录*
