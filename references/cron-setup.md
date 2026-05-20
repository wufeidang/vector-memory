# Cron 作业设置指南

## 创建作业

```bash
hermes cron create --name <作业名> --script <脚本名> --no-agent "<调度表达式>"
```

**示例**:
```bash
# 每小时整点运行同步脚本
hermes cron create --name hourly_memory_sync --script sync_memory.py --no-agent "0 * * * *"

# 每天 8 点运行摘要脚本
hermes cron create --name daily_memory_summary --script daily_memory_summary.py --no-agent "0 8 * * *"
```

## ⚠️ 路径注意事项

**关键规则**: `--script` 参数是相对于 `~/.hermes/` 的路径。

| 写法 | 实际解析路径 | 结果 |
|------|-------------|------|
| `--script sync_memory.py` | `~/.hermes/scripts/sync_memory.py` | ✅ 正确 |
| `--script scripts/sync_memory.py` | `~/.hermes/scripts/scripts/sync_memory.py` | ❌ 错误 |

**原因**: cron 作业的工作目录已经是 `~/.hermes/`，脚本实际位于 `~/.hermes/scripts/` 子目录中。

## 验证作业

```bash
# 查看作业列表
hermes cron list

# 手动测试脚本
python ~/.hermes/scripts/sync_memory.py
```

## 管理作业

```bash
hermes cron list              # 列出所有作业
hermes cron remove <job_id>   # 删除作业
hermes cron edit <job_id> --script <新脚本名>  # 更新脚本路径
hermes cron edit <job_id> --name "<新名称>"    # 更新作业名称（支持中文）
```

### 添加中文名称

为 cron 作业添加中文描述名称（便于识别）：

```bash
hermes cron edit <job_id> --name "每小时记忆同步"
hermes cron edit <job_id> --name "每日记忆摘要"
hermes cron edit <job_id> --name "每小时 Feishu Token 刷新"
```

**注意**: 使用 `edit` 命令而非 `update`（`update` 不是有效命令）。

## 常见调度表达式

| 表达式 | 含义 |
|--------|------|
| `0 * * * *` | 每小时整点 |
| `0 8 * * *` | 每天 8:00 |
| `0 9 * * *` | 每天 9:00 |
| `0 0 * * 0` | 每周日 0:00 |
| `*/5 * * * *` | 每 5 分钟 |

## 调试技巧

1. **检查路径**: `hermes cron list` 查看脚本路径是否正确
2. **手动运行**: 先用 `python ~/.hermes/scripts/<脚本名>.py` 测试
3. **查看日志**: 作业运行后检查 `~/.hermes/reports/` 或 `~/.hermes/logs/`
