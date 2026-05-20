# 自动化脚本参考

本文档列出记忆系统中所有自动化脚本的详细说明。

## 脚本清单

| 脚本 | 位置 | 功能 | Cron 任务 |
|------|------|------|-----------|
| `sync_memory.py` | `~/.hermes/scripts/sync_memory.py` | 双向同步 MEMORY.md ↔ 向量库 | 每小时记忆同步 |
| `daily_memory_summary.py` | `~/.hermes/scripts/daily_memory_summary.py` | 生成记忆分类摘要报告 | 每日记忆摘要 |
| `daily_noise_summary.py` | `~/.hermes/scripts/daily_noise_summary.py` | 检测重复/相似记忆 | 每日噪声检测 |
| `auto_record.py` | `~/.hermes/scripts/auto_record.py` | 关键词触发自动记录 | 实时触发 |
| `refresh_feishu_token.py` | `~/.hermes/scripts/refresh_feishu_token.py` | 刷新 Feishu API token | 每小时 Feishu Token 刷新 |
| `feishu_file_sender.py` | `~/.hermes/scripts/feishu_file_sender.py` | 发送文件到 Feishu | 手动调用 |
| `download_embedding_model.py` | `~/.hermes/scripts/download_embedding_model.py` | 下载嵌入模型 | 手动调用 |

---

## sync_memory.py — 记忆双向同步

### 功能

将 `MEMORY.md` 中的新记忆同步到 ChromaDB 向量库，自动检测已存在的记忆避免重复。

### 使用方式

```bash
python ~/.hermes/scripts/sync_memory.py
```

### 输出示例

```
=== 记忆同步脚本 ===
上次同步: 2026-05-17T20:00:00
已同步数量: 6
MEMORY.md 中的记忆: 7 条
向量库中已存在: 6 条
需要同步的新记忆: 1 条
✅ 已同步 1 条新记忆
```

### Cron 配置

```bash
hermes cron create --name "每小时记忆同步" --script sync_memory.py --no-agent "0 * * * *"
```

---

## daily_memory_summary.py — 每日记忆摘要

### 功能

按类别统计记忆，生成 Markdown 格式的报告。

### 使用方式

```bash
python ~/.hermes/scripts/daily_memory_summary.py
```

### 输出

报告保存至：`~/.hermes/reports/memory_summary_YYYYMMDD.md`

### 报告内容

- 生成时间
- 统计范围（全部/今日新增/历史）
- 按类别统计（learning, preference, config, project）
- 类别详情（每条记忆的摘要）

### Cron 配置

```bash
hermes cron create --name "每日记忆摘要" --script daily_memory_summary.py --no-agent "0 8 * * *"
```

---

## daily_noise_summary.py — 每日噪声检测

### 功能

检测向量库中重复或高度相似的记忆，生成检测报告。

### 使用方式

```bash
python ~/.hermes/scripts/daily_noise_summary.py
```

### 输出

报告保存至：`~/.hermes/reports/noise_summary_YYYYMMDD_HHMMSS.md`

### 检测逻辑

1. **精确匹配**：内容完全相同
2. **相似匹配**：嵌入向量余弦相似度 ≥ 85%

### Cron 配置

```bash
hermes cron create --name "每日噪声检测" --script daily_noise_summary.py --no-agent "0 9 * * *"
```

### ⚠️ 注意事项

该脚本在 2026-05-17 会话中经过修复：

- **原问题**：依赖 HuggingFace 在线模型，网络超时
- **修复方案**：改为使用本地 BGE 模型，修正 `list_memories` 调用格式
- **当前状态**：✅ 正常工作

---

## auto_record.py — 关键词触发自动记录

### 功能

检测输入文本中的触发关键词，自动将内容保存到记忆系统。

### 触发关键词

| 中文 | 英文 |
|------|------|
| 记住这个 | memory |
| 记录一下 | remember |
| 记下来 | 记录 |
| 保存这个 | 记住 |
| 添加到记忆 | — |

### 排除关键词（避免误触发）

查询、搜索、列出、删除、清空、import、list、search、delete、clear

### 使用方式

```bash
python ~/.hermes/scripts/auto_record.py "记住这个：用户偏好使用中文交流"
```

### 触发流程

```
用户输入 → 检测关键词 → 提取记忆内容 → 添加到向量库 → 同步到 MEMORY.md
```

---

## refresh_feishu_token.py — Feishu Token 刷新

### 功能

从 `.env` 读取 Feishu App ID/Secret，调用 API 获取 tenant access token，生成配置文件。

### 使用方式

```bash
python ~/.hermes/scripts/refresh_feishu_token.py
```

### 输出

生成 `~/.hermes/feishu_config.json`:

```json
{
  "access_token": "t-g1045hkWC6Q2ZKFQG5TFVHDK4D7H4NTQLTF7L7RD",
  "feishu_home_channel": "oc_668de3bf7447f404402869fc6bb7a4ae",
  "_generated_at": "2026-05-17T21:34:11",
  "_expires_in": "约 2 小时，请定期刷新",
  "_note": "此文件包含敏感信息，请勿泄露"
}
```

### API 端点

```
POST https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal
```

### ⚠️ 关键注意事项

`tenant_access_token` 在 API 响应**顶层**，不在 `data` 对象中：

```python
# ✅ 正确
token = response.json()['tenant_access_token']

# ❌ 错误（KeyError: 'data'）
token = response.json()['data']['tenant_access_token']
```

### Cron 配置

```bash
hermes cron create --name "每小时 Feishu Token 刷新" --script refresh_feishu_token.py --no-agent "0 * * * *"
```

---

## feishu_file_sender.py — Feishu 文件发送

### 功能

上传文件到 Feishu 并发送到指定频道。

### 使用方式

```bash
python ~/.hermes/scripts/feishu_file_sender.py <文件路径> [频道ID]

# 示例
python ~/.hermes/scripts/feishu_file_sender.py report.pdf
python ~/.hermes/scripts/feishu_file_sender.py report.pdf oc_abc123
```

### 依赖

- `~/.hermes/feishu_config.json`（需先运行 `refresh_feishu_token.py`）

### API 流程

1. **上传文件**：`POST /open-apis/im/v1/files` → 获取 `file_key`
2. **发送消息**：`POST /open-apis/im/v1/messages` → 发送 file 类型消息

### ⚠️ 注意事项

`content` 字段必须是**JSON 字符串**（已转义）：

```python
# ✅ 正确
content = json.dumps({"file_key": file_key})
payload = {"receive_id": channel_id, "msg_type": "file", "content": content}

# ❌ 错误
payload = {"receive_id": channel_id, "msg_type": "file", "content": {"file_key": file_key}}
```

---

## download_embedding_model.py — 嵌入模型下载

### 功能

从 ModelScope 下载 BGE 中文模型到本地缓存。

### 使用方式

```bash
python ~/.hermes/scripts/download_embedding_model.py
```

### 默认下载

- `AI-ModelScope/bge-base-zh-v1.5`（推荐，~391 MB）

### 手动下载其他模型

```bash
python -c "from modelscope.hub.snapshot_download import snapshot_download; snapshot_download('AI-ModelScope/bge-large-zh-v1.5')"
```

---

## 脚本验证清单

部署后建议逐一验证：

```bash
# 1. 同步脚本
python ~/.hermes/scripts/sync_memory.py

# 2. 摘要脚本
python ~/.hermes/scripts/daily_memory_summary.py

# 3. 噪声检测
python ~/.hermes/scripts/daily_noise_summary.py

# 4. Token 刷新
python ~/.hermes/scripts/refresh_feishu_token.py

# 5. 文件发送（需先有测试文件）
python ~/.hermes/scripts/feishu_file_sender.py test.txt

# 6. 查看 Cron 任务
hermes cron list
```
