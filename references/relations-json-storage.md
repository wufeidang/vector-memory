# 关联表独立 JSON 存储

## 问题背景

旧版 `link_memory()` 将记忆关联存储在 ChromaDB 元数据字段中：
- ChromaDB 元数据仅支持 `str/int/float/bool` 基本类型
- 嵌套对象（dict/list）必须序列化为 JSON 字符串
- JSON 字符串包含特殊字符可能触发 ChromaDB 验证错误
- 关联数据与记忆数据耦合，无法独立管理

## 解决方案

将关联表迁移到独立 JSON 文件 `~/.hermes/vector_store/relations.json`。

### 安装

无需额外依赖，使用标准库 `json` 和 `os`。

### 核心代码

```python
import os
import json

_RELATIONS_FILE = os.path.join(os.path.expanduser('~'), '.hermes', 'vector_store', 'relations.json')

def _load_relations():
    """加载关联表。"""
    if not os.path.exists(_RELATIONS_FILE):
        return {}
    try:
        with open(_RELATIONS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}

def _save_relations(relations):
    """保存关联表。"""
    os.makedirs(os.path.dirname(_RELATIONS_FILE), exist_ok=True)
    with open(_RELATIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(relations, f, ensure_ascii=False, indent=2)

def link_memory(args):
    """建立两条记忆之间的关联关系（独立 JSON 存储）。"""
    from_id = args.get('from_id')
    to_id = args.get('to_id')
    relation = args.get('relation', 'related')

    if not from_id or not to_id:
        return {"success": False, "message": "缺少 from_id 或 to_id"}
    if from_id == to_id:
        return {"success": False, "message": "不能关联自己"}

    # 验证记忆存在
    collection = _get_client()
    from_data = collection.get(ids=[from_id], include=['metadatas'])
    if not from_data.get('ids'):
        return {"success": False, "message": "from_id 不存在"}
    to_data = collection.get(ids=[to_id], include=['metadatas'])
    if not to_data.get('ids'):
        return {"success": False, "message": "to_id 不存在"}

    # 加载关联表
    relations = _load_relations()
    
    # 建立双向关联
    if from_id not in relations:
        relations[from_id] = []
    if to_id not in relations:
        relations[to_id] = []
    
    # 添加 from -> to
    existing_from = [(r['to'], r['type']) for r in relations[from_id]]
    if (to_id, relation) not in existing_from:
        relations[from_id].append({'to': to_id, 'type': relation})
    
    # 添加 to -> from (反向)
    existing_to = [(r['to'], r['type']) for r in relations[to_id]]
    reverse_type = 'related_to' if relation == 'related' else f'related_to_{relation}'
    if (from_id, reverse_type) not in existing_to:
        relations[to_id].append({'to': from_id, 'type': reverse_type})
    
    _save_relations(relations)
    
    return {"success": True, "message": "已建立关联: %s <-> %s (%s)" % (from_id, to_id, relation)}

def unlink_memory(args):
    """移除两条记忆之间的关联。"""
    from_id = args.get('from_id')
    to_id = args.get('to_id')

    if not from_id or not to_id:
        return {"success": False, "message": "缺少 from_id 或 to_id"}

    relations = _load_relations()
    removed_count = 0
    
    # 移除 from -> to
    if from_id in relations:
        original_len = len(relations[from_id])
        relations[from_id] = [r for r in relations[from_id] if r['to'] != to_id]
        removed_count += original_len - len(relations[from_id])
        if not relations[from_id]:
            del relations[from_id]
    
    # 移除 to -> from
    if to_id in relations:
        original_len = len(relations[to_id])
        relations[to_id] = [r for r in relations[to_id] if r['to'] != from_id]
        removed_count += original_len - len(relations[to_id])
        if not relations[to_id]:
            del relations[to_id]
    
    _save_relations(relations)
    
    return {"success": True, "message": "已移除关联: %s <-> %s (删除 %d 条记录)" % (from_id, to_id, removed_count)}

def get_knowledge_chain(args):
    """获取某记忆的知识链（关联的记忆及关系）。"""
    doc_id = args.get('id')
    depth = args.get('depth', 1)

    if not doc_id:
        return {"success": False, "message": "缺少 id"}

    collection = _get_client()
    data = collection.get(ids=[doc_id], include=['documents', 'metadatas'])
    if not data.get('ids'):
        return {"success": False, "message": "记忆不存在"}

    chain = {
        "id": doc_id,
        "text": data['documents'][0][:100],
        "metadata": data['metadatas'][0],
        "relations": [],
        "depth": 0
    }

    if depth < 1:
        return {"success": True, "chain": chain}

    # 从独立关联表获取关系
    relations = _load_relations()
    doc_relations = relations.get(doc_id, [])
    
    for rel in doc_relations:
        to_id = rel.get('to')
        rel_type = rel.get('type', 'related')
        to_data = collection.get(ids=[to_id], include=['documents', 'metadatas'])
        if to_data.get('ids'):
            chain["relations"].append({
                "to_id": to_id,
                "type": rel_type,
                "text": to_data['documents'][0][:60],
                "category": to_data['metadatas'][0].get('category', '?')
            })

    return {"success": True, "chain": chain}

def search_related(args):
    """搜索与某记忆相关的记忆。"""
    doc_id = args.get('id')
    limit = args.get('limit', 5)

    if not doc_id:
        return {"success": False, "message": "缺少 id"}

    # 从独立关联表获取相关 ID
    relations = _load_relations()
    related_items = relations.get(doc_id, [])
    related_ids = [r['to'] for r in related_items[:limit]]
    
    if not related_ids:
        return {"success": True, "related": [], "count": 0}

    collection = _get_client()
    related_data = collection.get(ids=related_ids, include=['documents', 'metadatas'])
    related = []
    for i, rid in enumerate(related_data.get('ids', [])):
        # 找到对应的关系类型
        rel_type = 'related'
        for item in related_items:
            if item['to'] == rid:
                rel_type = item['type']
                break
        related.append({
            "id": rid,
            "text": related_data['documents'][i][:80],
            "metadata": related_data['metadatas'][i],
            "relation_type": rel_type
        })

    return {"success": True, "related": related, "count": len(related)}

def export_relations(args=None):
    """导出关联表为 JSON。"""
    relations = _load_relations()
    return {"success": True, "relations": relations, "count": len(relations)}

def clear_relations(args=None):
    """清空关联表。"""
    if os.path.exists(_RELATIONS_FILE):
        os.remove(_RELATIONS_FILE)
    return {"success": True, "message": "关联表已清空"}
```

## 注意事项

1. **双向关联**：`link_memory()` 自动建立双向关联（`related` ↔ `related_to`）
2. **去重检查**：建立关联前检查是否已存在，避免重复
3. **记忆验证**：关联前验证记忆是否存在于向量库
4. **JSON 序列化**：使用 `ensure_ascii=False` 保留中文字符
5. **独立管理**：`export_relations()` 和 `clear_relations()` 用于独立导出/清理关联表

## 改进对比

| 项目 | 旧版 (ChromaDB) | 新版 (独立 JSON) |
|------|-----------------|------------------|
| 存储位置 | ChromaDB 元数据字段 | relations.json 独立文件 |
| 数据类型限制 | 仅 str/int/float/bool | 完整 JSON 结构 |
| 查询效率 | 需 collection.get() | 直接 JSON 加载 |
| 序列化风险 | JSON 字符串可能触发验证 | 无限制 |
| 可移植性 | 依赖 ChromaDB | 纯 JSON，易迁移 |
| 独立管理 | 与记忆数据耦合 | 可独立导出/清理 |

## 测试验证

```python
import vector_memory as vm

# 添加测试记忆
result1 = vm.add_memory({'text': '测试记忆 A', 'metadata': {'category': 'test'}})
result2 = vm.add_memory({'text': '测试记忆 B', 'metadata': {'category': 'test'}})
id_a = result1.get('id')
id_b = result2.get('id')

# 建立关联
vm.link_memory({'from_id': id_a, 'to_id': id_b, 'relation': 'related'})

# 获取知识链
chain = vm.get_knowledge_chain({'id': id_a, 'depth': 1})
print(f"A 的关联: {chain['chain']['relations']}")

# 搜索相关记忆
related = vm.search_related({'id': id_a, 'limit': 5})
print(f"与 A 相关的记忆: {related['related']}")

# 导出关联表
export = vm.main({'action': 'export_relations'})
print(f"关联表: {export['relations']}")

# 移除关联
vm.unlink_memory({'from_id': id_a, 'to_id': id_b})

# 验证关联已移除
chain = vm.get_knowledge_chain({'id': id_a, 'depth': 1})
print(f"A 的关联数: {len(chain['chain']['relations'])}")
```

## 相关文件

- `scripts/vector_memory.py` — 主实现文件
- `~/.hermes/vector_store/relations.json` — 关联表文件
- `~/.hermes/vector_store/` — ChromaDB 向量库