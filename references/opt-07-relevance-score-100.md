# opt-07: 检索结果相关性评分（0-100 分）

## 背景

原始 `search_memories()` 返回的分数为：
- `score`: 融合分数（0-1 之间，基于余弦相似度）
- `rerank_score`: CrossEncoder 的 logit 值（无界实数）
- `vector_score`: 原始向量分数（0-1 之间）

这些分数对用户不够直观，难以判断相关性强度。

## 映射方案

### 1. 余弦相似度 → 0-100 分

```
cos_sim ∈ [-1, 1]
score_100 = (cos_sim + 1) / 2 × 100
```

| cos_sim | score_100 | 含义 |
|---------|-----------|------|
| -1.0 | 0 | 完全无关（反相关） |
| -0.5 | 25 | 弱负相关 |
| 0.0 | 50 | 不相关 |
| 0.5 | 75 | 中等正相关 |
| 1.0 | 100 | 完全相关 |

### 2. CrossEncoder Logit → 0-100 分

```
logit ∈ (-∞, +∞)
sigmoid(x) = 1 / (1 + e^(-x))
score_100 = sigmoid(logit) × 100
```

| logit | sigmoid | score_100 | 含义 |
|-------|---------|-----------|------|
| -5.0 | 0.0067 | 0.67 | 几乎不相关 |
| -2.0 | 0.1192 | 11.92 | 弱相关 |
| 0.0 | 0.5000 | 50.00 | 中性 |
| 2.0 | 0.8808 | 88.08 | 强相关 |
| 5.0 | 0.9933 | 99.33 | 几乎完全相关 |

## 代码实现

### 辅助函数

```python
def _to_score_100(cos_sim):
    """将余弦相似度 (-1 到 1) 映射为 0-100 分。"""
    return max(0.0, min(100.0, (cos_sim + 1.0) / 2.0 * 100.0))

def _sigmoid_to_score_100(logit):
    """将 CrossEncoder 的 logit 通过 sigmoid 映射为 0-100 分。"""
    import math
    sigmoid = 1.0 / (1.0 + math.exp(-logit))
    return sigmoid * 100.0
```

### search_memories() 修改

1. 计算 `vector_scores_100` 和 `tfidf_scores_100`
2. 调用 `rerank_results()` 获取 `relevance_100`
3. 在返回字典中添加 `relevance_score`、`vector_score_100`、`tfidf_score_100` 字段

### rerank_results() 修改

返回值从 5 元组改为 6 元组：
```python
# 旧版
(doc, combined, meta, rr_score, orig_score)

# 新版
(doc, combined, meta, rr_score, orig_score, relevance_100)
```

## 测试验证

### 单元测试

```python
# sigmoid 映射
assert _sigmoid_to_score_100(0.0) == 50.0
assert _sigmoid_to_score_100(2.0) > 80.0
assert _sigmoid_to_score_100(-2.0) < 20.0

# 余弦相似度映射
assert _to_score_100(-1.0) == 0.0
assert _to_score_100(0.0) == 50.0
assert _to_score_100(1.0) == 100.0
```

### 集成测试

```python
result = search_memories({"text": "POE 供电故障", "top_k": 3})
for r in result["results"]:
    assert 0 <= r["relevance_score"] <= 100
    assert 0 <= r["vector_score_100"] <= 100
```

## 实际效果

查询："POE 供电故障"

| 排名 | 文档 | relevance_score | vector_score_100 |
|------|------|-----------------|------------------|
| 1 | POE 供电故障排查指南 | 70.2 | 85.8 |
| 2 | 监控系统 POE 供电故障排查 | 67.9 | 74.9 |
| 3 | 消防泵房巡检 | 60.3 | 41.9 |

✅ POE 相关内容得分更高，消防泵房得分较低（相关性弱），评分逻辑正确。

## 注意事项

1. **函数签名变更**：修改 `rerank_results()` 返回值结构时，需检查所有调用方
2. **测试先行**：修改后必须运行实际检索测试，验证评分排序与语义相关性一致
3. **分数解释**：
   - 0-30 分：弱相关或不相关
   - 30-60 分：中等相关
   - 60-80 分：强相关
   - 80-100 分：高度相关

## 相关文件

- `scripts/vector_memory.py` — 核心实现
- `references/opt-07-relevance-score-100.md` — 本参考文档
