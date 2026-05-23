# sync_memory.py 格式兼容性修复

## 问题描述

`sync_memory.py` 脚本最初只支持传统格式的记忆条目：

```
- [2026-05-20 20:01:08] 记忆内容 {metadata}
```

但 MEMORY.md 实际使用的是 `§` 分隔格式：

```
2026-05-20 进度快照：
- 监控教程系列：7/12 完成
- 消防教程系列：3/12 完成
§
2026-05-20 更新：消防系列第02期文章已完成
§
...
```

导致同步脚本解析出 0 条记忆，无法同步。

## 修复方案

修改 `parse_memory_file()` 函数，支持两种格式：

### 1. § 分隔格式（当前使用）

```python
if '§' in content:
    sections = content.split('§')
    for section in sections:
        section = section.strip()
        if not section:
            continue
        # 从条目开头提取日期
        # 或从嵌入的 - [timestamp] 格式提取
```

### 2. 传统格式（兼容）

```python
else:
    for line in content.split('\n'):
        if line.startswith('- ['):
            # 解析 - [timestamp] text {metadata}
```

## 时间戳提取逻辑

| 来源 | 优先级 | 示例 |
|------|--------|------|
| 嵌入的 `- [timestamp]` | 最高 | `... - [2026-05-20 20:01:08] 摘要` |
| 条目开头的日期 | 中等 | `2026-05-20 进度快照：` |
| 无时间戳 | 最低 | 标记为"未知时间" |

## 去重机制

改用 **MD5 哈希** 判断重复，而非文本精确匹配：

```python
def compute_text_hash(text):
    return hashlib.md5(text.encode('utf-8')).hexdigest()

# 保存已同步的哈希列表
state['synced_hashes'].append(hash)
```

避免文本微小差异（如空格、换行）导致的重复导入。

## 验证结果

| 项目 | 修复前 | 修复后 |
|------|--------|--------|
| 解析条目数 | 0 | 9 |
| 新导入 | 0 | 9 |
| 向量库总计 | 14 | 23 |

## 文件位置

- 脚本：`~/.hermes/scripts/sync_memory.py`
- 状态：`~/.hermes/scripts/.sync_state.json`
- 记忆文件：`~/.hermes/memories/MEMORY.md`

## 相关

- 每小时自动同步 Cron 任务调用此脚本
- 同步状态包含 `last_sync`、`synced_count`、`synced_hashes` 三个字段
