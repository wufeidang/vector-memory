# 记忆版本管理指南

## 概述

为记忆添加版本控制功能，支持版本历史查询和回滚操作。

## API

### add_memory_v2()

带版本管理的记忆添加。如果记忆已存在（文本内容完全匹配），则创建新版本而非覆盖。

```python
result = vector_memory action='add_v2' text='新内容' metadata='{"category":"tech"}'
```

**返回**：
- 新记忆：`{"success": true, "id": "...", "version": 1}`
- 更新记忆：`{"success": true, "id": "...", "version": 2, "prev_version": 1}`

### get_memory_versions()

获取某记忆的所有版本历史。

```python
result = vector_memory action='get_versions' id='1779193644582'
```

**返回**：
```json
{
  "success": true,
  "id": "1779193644582",
  "versions": [
    {"version": 3, "text": "...", "is_current": true},
    {"version": 2, "text": "...", "is_current": false},
    {"version": 1, "text": "...", "is_current": false}
  ],
  "count": 3
}
```

### rollback_memory()

回滚到指定版本（创建新版本）。

```python
result = vector_memory action='rollback' id='1779193644582' version='2'
```

**返回**：
```json
{
  "success": true,
  "message": "已回滚到版本 2（当前版本 4）",
  "new_version": 4,
  "rolled_back_from": 3,
  "rolled_back_to": 2
}
```

## 数据存储

### version_history.json

版本历史存储在独立 JSON 文件中：

```
~/.hermes/vector_store/version_history.json
```

**结构**：
```json
{
  "memory_id_1": [
    {
      "version": 1,
      "text": "旧内容",
      "metadata": {...},
      "timestamp": "2026-05-19 20:00:00"
    },
    {
      "version": 2,
      "text": "更新内容",
      "metadata": {...},
      "timestamp": "2026-05-19 20:30:00"
    }
  ]
}
```

## 版本检测逻辑

**注意**：ChromaDB 的 `where` 参数无法直接匹配 `documents` 字段。

**错误做法**：
```python
# ❌ 无法工作
existing = collection.get(where={"text": text})
```

**正确做法**：
```python
# ✅ 手动匹配
existing = collection.get()
existing_docs = existing.get('documents', [])
match_idx = None
for i, doc in enumerate(existing_docs):
    if doc == text:
        match_idx = i
        break
```

## 版本管理策略

| 操作 | 行为 | 版本变化 |
|------|------|----------|
| 首次添加 | 创建新记忆 | version: 1 |
| 更新相同内容 | 创建新版本 | version: n → n+1 |
| 回滚 | 创建回滚版本 | version: n → n+1（内容回退） |
| 删除 | 从向量库移除 | 历史保留在 version_history.json |

## 注意事项

1. **文本匹配**：版本检测基于**完全匹配**，相似内容会被视为新记忆
2. **历史保留**：回滚操作会保存当前版本到历史，不会丢失数据
3. **版本递增**：每次修改都创建新版本，版本号单调递增
4. **存储位置**：`version_history.json` 独立于 ChromaDB，可单独备份

## 未来改进

- [ ] 添加模糊匹配（语义相似度检测重复）
- [ ] 自动清理旧版本（保留最近 N 个）
- [ ] 版本差异对比（diff 显示）
- [ ] 批量版本操作