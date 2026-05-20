# 2026-05-18 向量化记忆系统 3 项功能补全记录

## 背景

2026-05-18 会话中，向量化记忆系统完成了 10 维度精细测试。前 5 项（基础 CRUD、语义搜索、去重、分类管理、混合检索）和 6、8、10 项（批量写入、分块索引、监控指标）已在之前会话完成。本会话补全了 3 项缺失功能：脉冲同步、语义摘要发散、知识链集成。

## 问题诊断

使用 `delegate_task` 并行 3 个 agent 补全功能时，**全部超时**（600s）。原因：
- BGE 中文模型加载慢（~10s）
- 每个 agent 需独立加载模型，3 个 agent 并行加载导致总时间超限
- 模型加载是串行瓶颈，并行反而更慢

**解决方案**：放弃并行 agent，直接用 `execute_code` 手动实现 3 项功能。

## 补全的 3 项功能

### 1. 脉冲同步（#5）

**函数**：
- `watch_memory_md(interval=5)` — 轮询监控 MEMORY.md，发现新增行自动导入
- `stop_watch()` — 停止监控
- `watch_status()` — 查询监控状态

**实现要点**：
- 使用文件 `size` 和 `mtime` 检测变化，避免全量解析
- 已导入行通过 `memory_md_line` 元数据标记去重
- 轮询间隔默认 5 秒，可配置
- 失败静默处理，下次轮询重试

**测试**：
```python
watch_memory_md(interval=5)
watch_status()  # {'success': True, 'watching': True, 'thread_alive': True}
stop_watch()
```

### 2. 语义摘要发散（#7）

**增强前**：仅按 `category` 计数，输出分类统计。

**增强后**：
- 支持 `cluster=True` 开启 K-Means 语义聚类
- `n_clusters` 参数控制聚类数（记忆不足时自动调整）
- 每个簇提取最长文档前 40 字作为主题预览
- 报告包含：分类统计 + 语义主题分布

**测试**：
```python
generate_daily_summary({'date_str': '2026-05-18', 'cluster': True, 'n_clusters': 2})
# 返回 2 个聚类，每个聚类有 count 和 topic_preview
```

**报告示例**：
```
### 语义主题聚类 (2 个主题)

**主题 0** (2 条记忆): iVMS-4200 客户端添加设备配置
  - [tech] 无线网桥信号强度 -65dBm
  - [config] iVMS-4200 客户端添加设备配置

**主题 1** (3 条记忆): 摄像头 IP 地址冲突，两个设备都是 192.168.1.100
  - [tech] POE 交换机供电电压应该是 48V，实测只有 36V
  - [tech] 摄像头 IP 地址冲突，两个设备都是 192.168.1.100
  - [tech] NVR 硬盘坏道检测，发现 3 个坏道
```

### 3. 知识链集成（#9）

**函数**：
- `link_memory(from_id, to_id, relation='related')` — 建立双向关联
- `unlink_memory(from_id, to_id)` — 移除关联
- `get_knowledge_chain(doc_id, depth=1)` — 获取知识链
- `search_related(doc_id, limit=5)` — 搜索相关记忆

**元数据扩展**：
- `related_ids`: 关联记忆 ID 列表
- `relations`: 关系详情列表 `[{'to': id, 'type': relation}]`

**测试**：
```python
link_memory({'from_id': 'a', 'to_id': 'b', 'relation': 'related'})
chain = get_knowledge_chain({'id': 'a', 'depth': 1})
# chain['chain']['relations'] 包含关联记忆的简要信息
related = search_related({'id': 'a', 'limit': 3})
unlink_memory({'from_id': 'a', 'to_id': 'b'})
```

## 函数签名差异（陷阱）

| 函数 | 参数类型 | 调用示例 |
|------|---------|---------|
| `main(action, args)` | args 字典 | `main('watch_status', {})` |
| `watch_status()` | 无参数 | `watch_status()` |
| `generate_daily_summary(args)` | args 字典 | `generate_daily_summary({'date_str': '2026-05-18'})` |
| `link_memory(args)` | args 字典 | `link_memory({'from_id': 'a', 'to_id': 'b'})` |
| `watch_memory_md(interval)` | 位置参数 | `watch_memory_md(5)` |

**注意**：`main()` 入口统一用 args 字典，但直接调用辅助函数时需确认签名。

## 文件变更

- `~/.hermes/skills/vector_memory/scripts/vector_memory.py` — 添加约 200 行代码（watch、clustering、knowledge chain）
- `~/.hermes/skills/vector_memory/SKILL.md` — 更新 API 列表、CLI 示例、新增 2 个陷阱条目

## 10 维度测试最终结果

| # | 维度 | 状态 |
|---|------|------|
| 1 | 基础 CRUD | ✅ |
| 2 | 语义搜索 | ✅ |
| 3 | 去重 | ✅ |
| 4 | 分类管理 | ✅ |
| 5 | 脉冲同步 | ✅ (本会话补全) |
| 6 | 批量写入 | ✅ |
| 7 | 语义摘要发散 | ✅ (本会话补全) |
| 8 | 分块索引 | ✅ |
| 9 | 知识链集成 | ✅ (本会话补全) |
| 10 | 监控指标 | ✅ |
