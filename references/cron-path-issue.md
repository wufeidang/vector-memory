# Cron 作业路径问题排查

> 基于 2026-05-17 会话发现的 cron 路径问题

## 问题现象

创建 cron 作业时，脚本路径解析错误：

```
error: Script not found: C:\Users\Nemo\.hermes\scripts\scripts\sync_memory.py
```

## 根本原因

`hermes cron create --script` 参数中的路径是**相对于 `~/.hermes/`** 的，而不是相对于 `~/.hermes/scripts/`。

| 指定路径 | 实际解析路径 | 结果 |
|----------|--------------|------|
| `sync_memory.py` | `~/.hermes/scripts/sync_memory.py` | ✅ 正确 |
| `scripts/sync_memory.py` | `~/.hermes/scripts/scripts/sync_memory.py` | ❌ 错误（重复） |

## 解决方案

### 创建 cron 作业时

```bash
# ✅ 正确 - 只写文件名
hermes cron create --name "每小时记忆同步" --script sync_memory.py --no-agent "0 * * * *"

# ❌ 错误 - 不要加 scripts/ 前缀
hermes cron create --name "每小时记忆同步" --script scripts/sync_memory.py --no-agent "0 * * * *"
```

### 编辑 cron 作业时

```bash
hermes cron edit <job_id> --script sync_memory.py
```

## 验证方法

```bash
# 1. 查看 cron 列表，确认脚本路径正确
hermes cron list

# 2. 手动运行脚本测试
python ~/.hermes/scripts/sync_memory.py
```

## 常见 cron 作业配置

| 作业名 | 调度 | 脚本 | 说明 |
|--------|------|------|------|
| 每小时记忆同步 | `0 * * * *` | `sync_memory.py` | 同步 MEMORY.md → 向量库 |
| 每小时 Feishu Token 刷新 | `0 * * * *` | `refresh_feishu_token.py` | 刷新 Feishu API token |
| 每日记忆摘要 | `0 8 * * *` | `daily_memory_summary.py` | 生成记忆分类报告 |
| 每日噪声检测 | `0 9 * * *` | `daily_noise_summary.py` | 检测重复/相似记忆 |

---

*最后更新: 2026-05-17*
