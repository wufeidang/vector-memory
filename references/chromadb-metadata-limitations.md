# ChromaDB 元数据限制与解决方案

## 问题描述

ChromaDB 的元数据（metadata）字段有严格的类型限制，不支持嵌套对象或复杂结构。

### 错误示例

```python
# ❌ 错误：直接存储嵌套对象
meta['relations'] = []
meta['relations'].append({'to': to_id, 'type': 'related'})
collection.update(ids=[from_id], metadatas=[meta])
# 报错: ValueError: Expected metadata list value for key 'relations' 
#        to contain only str, int, float, or bool and all elements must be the same type
```

### 原因

ChromaDB 元数据只支持以下类型：
- `str` (字符串)
- `int` (整数)
- `float` (浮点数)
- `bool` (布尔值)
- `List[str]`, `List[int]`, `List[float]`, `List[bool]` (同类型列表)

**不支持**：嵌套字典、列表混合类型、None 值等。

## 解决方案

### 方案 1：JSON 序列化（推荐）

将复杂结构序列化为 JSON 字符串存储，读取时反序列化。

```python
import json

# 写入时序列化
meta['relations'] = []
meta['relations'].append(json.dumps({'to': to_id, 'type': 'related'}))
collection.update(ids=[from_id], metadatas=[meta])

# 读取时反序列化
relations = meta.get('relations', [])
for rel_str in relations:
    try:
        rel = json.loads(rel_str)
        to_id = rel.get('to')
        rel_type = rel.get('type')
    except json.JSONDecodeError:
        continue
```

### 方案 2：扁平化存储

将嵌套结构展平为多个独立字段。

```python
# 写入
meta['relation_to_1'] = to_id
meta['relation_type_1'] = 'related'
meta['relation_to_2'] = another_id
meta['relation_type_2'] = 'depends_on'

# 读取
for i in range(1, max_relations + 1):
    to_id = meta.get(f'relation_to_{i}')
    rel_type = meta.get(f'relation_type_{i}')
    if to_id:
        # 处理关联
```

### 方案 3：使用 related_ids 列表 + relations 字符串

```python
# 简单关联用列表
meta['related_ids'] = [id1, id2, id3]

# 复杂关系用 JSON 字符串
meta['relations'] = json.dumps([
    {'to': id1, 'type': 'related'},
    {'to': id2, 'type': 'depends_on'},
])
```

## 在 vector_memory.py 中的应用

### link_memory 函数

```python
def link_memory(args):
    from_id = args.get('from_id')
    to_id = args.get('to_id')
    relation = args.get('relation', 'related')
    
    # ... 获取元数据 ...
    
    # ✅ 正确：使用 json.dumps 序列化
    from_meta['relations'] = from_meta.get('relations', [])
    from_meta['relations'].append(json.dumps({'to': to_id, 'type': relation}))
    collection.update(ids=[from_id], metadatas=[from_meta])
    
    # 双向链接
    to_meta['relations'] = to_meta.get('relations', [])
    to_meta['relations'].append(json.dumps({'to': from_id, 'type': 'related_to'}))
    collection.update(ids=[to_id], metadatas=[to_meta])
```

### get_knowledge_chain 函数

```python
def get_knowledge_chain(args):
    # ... 获取元数据 ...
    
    relations = meta.get('relations', [])
    for rel_str in relations:
        try:
            rel = json.loads(rel_str)  # ✅ 反序列化
        except json.JSONDecodeError:
            continue
        to_id = rel.get('to')
        rel_type = rel.get('type', 'related')
        # ... 构建知识链 ...
```

### unlink_memory 函数

```python
def unlink_memory(args):
    # ...
    if 'relations' in meta:
        # ✅ 反序列化后过滤
        meta['relations'] = [
            r for r in meta['relations'] 
            if json.loads(r).get('to') != to_id
        ]
    # ...
```

## 注意事项

1. **导入 json 模块**：在文件顶部添加 `import json`
2. **异常处理**：反序列化时用 try-except 捕获 JSONDecodeError
3. **类型一致性**：列表中的所有元素必须是同一类型（不能混合 str 和 dict）
4. **性能考虑**：JSON 序列化/反序列化有轻微开销，但对记忆系统影响可忽略

## 相关错误信息

```
ValueError: Expected metadata list value for key 'relations' to contain 
only str, int, float, or bool and all elements must be the same type, 
got [{'to': '1779113864958', 'type': 'related'}] in update.
```

此错误表明尝试存储的列表元素是字典类型，而 ChromaDB 只支持基本类型。

---
*创建时间: 2026-05-18*
*来源: vector_memory 技能开发过程中的调试记录*
