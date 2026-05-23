# 监控数据自动记录修复

## 问题描述

Web UI 监控页面数据一直不更新，原因是 `memory_monitor.py` 是独立模块，不会自动被搜索/备份操作调用。

## 根本原因

| 模块 | 职责 | 是否调用监控 |
|------|------|-------------|
| `search.py` | 搜索记忆 | ❌ 否 |
| `backup_memory.py` | 创建备份 | ❌ 否 |
| `memory_monitor.py` | 记录监控数据 | 被动等待调用 |

监控模块设计为**被动记录**，需要主动调用 `record_search()` 和 `record_backup()`。

## 修复方案

将监控记录直接集成到核心操作中，确保每次搜索/备份都自动记录。

### 1. 搜索操作集成（`search.py`）

在 `search_memories()` 函数末尾添加：

```python
elapsed = time.time() - start
elapsed_ms = round(elapsed * 1000, 2)

# 自动记录监控数据
try:
    from memory_monitor import record_search
    record_search(
        query=text,
        results_count=len(results),
        elapsed_ms=elapsed_ms,
        source="vector_memory",
        metadata={"top_k": top_k, "where": where}
    )
except Exception:
    pass  # 监控记录失败不影响搜索

return {"success": True, "results": results, "count": len(results), "elapsed_ms": elapsed_ms}
```

### 2. 备份操作集成（`backup_memory.py`）

在 `create_backup()` 函数中：

```python
def create_backup():
    """创建完整备份"""
    start_time = time.time()  # ← 函数开头记录开始时间
    
    # ... 备份操作 ...
    
    # 清理旧备份（保留最近7个）
    cleanup_old_backups()
    
    # 自动记录监控数据
    try:
        from memory_monitor import record_backup
        duration_ms = round((time.time() - start_time) * 1000, 2)
        record_backup(
            duration_ms=duration_ms,
            items_count=len(manifest.get("items", [])),
            success=True
        )
    except Exception:
        pass  # 监控记录失败不影响备份
    
    return backup_path, manifest
```

## 验证方法

```bash
# 1. 执行一次搜索
python -c "from search import search_memories; search_memories({'text': '测试', 'top_k': 1})"

# 2. 检查监控日志
cat ~/.hermes/monitor_data/performance_log.json

# 3. 应看到新增条目
{
  "entries": [
    {
      "timestamp": "2026-05-21T17:46:22.913967",
      "query": "测试",
      "results_count": 3,
      "elapsed_ms": 2388.03,
      "source": "vector_memory",
      "metadata": {"top_k": 1, "where": null}
    }
  ],
  ...
}
```

## 监控数据结构

`performance_log.json` 支持两种操作类型：

### 搜索记录

```json
{
  "timestamp": "2026-05-21T17:46:22.913967",
  "query": "监控",
  "results_count": 3,
  "elapsed_ms": 2388.03,
  "source": "vector_memory",
  "metadata": {"top_k": 5, "where": null}
}
```

### 备份记录

```json
{
  "timestamp": "2026-05-21T17:46:32.197564",
  "type": "backup",
  "duration_ms": 1895.29,
  "items_count": 7,
  "success": true
}
```

## Web UI 监控页面

监控页面从 `performance_log.json` 读取数据，显示：

- 24 小时搜索次数、总命中数、平均耗时
- 备份次数、备份项目数、平均备份耗时
- 最近操作日志（最多 20 条）
- 性能报告列表

自动刷新：每 30 秒调用 `/api/stats` 更新统计。

## 注意事项

1. **异常处理**：监控记录失败不应影响主功能，用 `try/except` 包裹
2. **时间精度**：使用 `time.time()` 计算耗时，转换为毫秒
3. **元数据**：可选记录额外信息（如查询参数、集合名称等）
4. **数据清理**：`memory_monitor.clear_old_data(days=30)` 清理超过 30 天的数据
