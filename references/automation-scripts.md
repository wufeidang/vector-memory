# 自动化脚本说明

## 脚本列表

| 脚本 | 功能 | 位置 |
|------|------|------|
| `auto_record.py` | 关键词触发自动记录 | `~/.hermes/scripts/auto_record.py` |
| `sync_memory.py` | 每小时同步 MEMORY.md → 向量库 | `~/.hermes/scripts/sync_memory.py` |
| `daily_memory_summary.py` | 每日记忆摘要报告 | `~/.hermes/scripts/daily_memory_summary.py` |
| `daily_noise_summary.py` | 噪声/重复记忆检测 | `~/.hermes/scripts/daily_noise_summary.py` |
| `refresh_feishu_token.py` | Feishu token 刷新 | `~/.hermes/scripts/refresh_feishu_token.py` |
| `feishu_file_sender.py` | Feishu 文件发送 | `~/.hermes/scripts/feishu_file_sender.py` |

## 噪声检测脚本

**功能**: 检测向量库中的重复或高度相似记忆，生成报告。

**实现细节**:
- 使用 `list_memories({"limit": 1000})` 获取所有记忆
- 检测完全重复（content 相同）
- 可选：使用 embedding 余弦相似度检测相似记忆（阈值 0.85）

**报告位置**: `~/.hermes/reports/noise_summary_YYYYMMDD_HHMMSS.md`

**⚠️ 注意事项**:
- 脚本依赖 `vector_memory` 技能的 `list_memories` 函数
- `list_memories` 接受 **args 字典**，不是关键字参数
- 如果向量库为空，脚本会跳过并退出（退出码 0）

## Cron 作业路径注意事项

**⚠️ 常见错误**: 脚本路径重复 `scripts/`

```bash
# ❌ 错误 - 路径会变成 ~/.hermes/scripts/scripts/sync_memory.py
hermes cron create --script scripts/sync_memory.py "0 * * * *"

# ✅ 正确 - 路径解析为 ~/.hermes/scripts/sync_memory.py
hermes cron create --script sync_memory.py "0 * * * *"
```

**原因**: cron 作业的工作目录已经是 `~/.hermes/`，所以 `scripts/` 前缀会导致路径重复。

**验证方法**:
```bash
hermes cron list  # 查看脚本路径
python ~/.hermes/scripts/sync_memory.py  # 手动测试
```

## 脚本依赖

所有脚本都依赖以下环境：
- Python 3.10+
- `chromadb`, `sentence-transformers`（向量记忆相关）
- `requests`（Feishu 相关）
