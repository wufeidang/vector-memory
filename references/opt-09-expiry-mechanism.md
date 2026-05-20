# opt-09 记忆过期机制（2026-05-19）

## 功能目标

为记忆添加访问追踪和指数衰减权重，长期未检索的记忆自动降权，避免陈旧信息干扰检索结果。

## 实现方案

### 1. 指数衰减权重公式

```
weight = exp(-decay_rate × days_since_access)
```

- 默认 `decay_rate = 0.0231`，30 天半衰期
- 60 天后权重降至 25%，90 天后降至 12.5%
- 最小权重 `min_weight = 0.1`，避免权重过低导致完全不可见

### 2. 访问追踪字段

自动添加到元数据：
- `last_accessed`: ISO 格式时间戳，记录最后访问时间
- `access_count`: 整数，累计访问次数

### 3. 搜索时自动降权

```python
# 计算衰减权重
decay_weights = _apply_decay_to_scores(docs, metas, ids, decay_rate)

# 应用衰减
score = original_score * decay_weight
```

## 新增 API

```python
# 获取访问统计
get_access_stats()
# → {"total": 5, "accessed": 5, "never_accessed": 0, "avg_decay_weight": 0.758, "half_life_days": 30.0}

# 获取过期记忆（超过阈值未访问）
get_expired_memories({"threshold_days": 30})
# → {"expired": [...], "count": 1}

# 删除过期记忆（默认干跑模式）
prune_expired_memories({"threshold_days": 60, "dry_run": True})
# → {"message": "【干跑模式】将删除 1 条...", "dry_run": True}

# 搜索时自定义衰减率
search_memories({"text": "POE", "decay_rate": 0.1})  # 更激进的衰减
```

## 返回字段扩展

```json
{
  "id": "...",
  "text": "...",
  "score": 0.097,                    // 衰减后的综合分
  "original_score": 0.388,           // 原始综合分
  "decay_weight": 0.250,             // 衰减权重
  "relevance_score": 24.5,           // 衰减后的 0-100 分
  "original_relevance_score": 98.0   // 原始 0-100 分
}
```

## 测试验证

| 测试项 | 结果 |
|--------|------|
| 刚添加的记忆权重=1.0 | ✅ |
| 60 天前访问的记忆权重=0.250 | ✅ 显著衰减 |
| 衰减后分数排序正确 | ✅ 旧记忆被新记忆超越 |
| 过期记忆检测（30 天阈值） | ✅ 找到 1 条 |
| 干跑模式预览删除 | ✅ 不实际删除 |
| 自定义 decay_rate=0.1 | ✅ 权重降至 0.1 |
| 平均衰减权重统计 | ✅ 0.758（5 条中 1 条衰减） |

## 关键陷阱

### ChromaDB `get(include=['ids', ...])` 错误

**问题**：`collection.get(include=['ids', 'metadatas', 'documents'])` 报错：
```
ValueError: Expected include item to be one of documents, embeddings, metadatas, distances, uris, data, got ids
```

**原因**：`ids` 是 ChromaDB `get()` 的默认返回字段，**不能**放在 `include` 参数中。

**修复**：
```python
# ❌ 错误
data = collection.get(include=['ids', 'metadatas', 'documents'])

# ✅ 正确
data = collection.get(include=['metadatas', 'documents'])
ids = data['ids']  # ids 始终可用
```

## 注意事项

1. 新记忆默认 `last_accessed = created_at`，权重从 1.0 开始衰减
2. 衰减权重有最小值 `min_weight=0.1`，避免权重过低导致完全不可见
3. 删除过期记忆默认开启 `dry_run=True`，需显式设置 `dry_run=False` 才实际删除
4. `get_access_stats()` 计算半衰期：`half_life_days = ln(2) / decay_rate ≈ 30 天`
