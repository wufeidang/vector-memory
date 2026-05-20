# Feishu API 实战指南

> 基于 2026-05-17 会话经验整理

## 快速开始

### 1. 刷新 Token

```bash
python ~/.hermes/scripts/refresh_feishu_token.py
```

**输出**: 生成/更新 `~/.hermes/feishu_config.json`

### 2. 发送文件

```bash
python ~/.hermes/scripts/feishu_file_sender.py <文件路径> [频道ID]

# 示例
python ~/.hermes/scripts/feishu_file_sender.py report.pdf
python ~/.hermes/scripts/feishu_file_sender.py report.pdf oc_abc123
```

---

## API 关键注意事项

### ⚠️ Token 响应结构

Feishu tenant access token API 的响应结构：

```json
{
  "code": 0,
  "expire": 5077,
  "msg": "ok",
  "tenant_access_token": "t-g1045hkWC6Q2ZKFQG5TFVHDK4D7H4NTQLTF7L7RD"
}
```

**关键点**: `tenant_access_token` 在**顶层**，不在 `data` 对象中！

```python
# ✅ 正确
token = data['tenant_access_token']

# ❌ 错误（会报 KeyError: 'data'）
token = data['data']['tenant_access_token']
```

### ⚠️ 文件发送消息格式

发送 file 消息时，`content` 字段必须是**JSON 字符串**（已转义）：

```python
import json

# ✅ 正确 - content 是 JSON 字符串
content = json.dumps({"file_key": file_key})
payload = {
    "receive_id": channel_id,
    "msg_type": "file",
    "content": content  # 字符串，不是对象
}

# ❌ 错误 - content 直接是对象
payload = {
    "receive_id": channel_id,
    "msg_type": "file",
    "content": {"file_key": file_key}  # 对象，会报错
}
```

### ⚠️ 文件上传格式

上传文件时使用 `multipart/form-data`：

```python
files = {
    'file_type': (None, 'stream'),
    'file_name': (None, os.path.basename(file_path)),
    'file': (os.path.basename(file_path), open(file_path, 'rb'))
}
```

---

## 配置文件结构

### `.env` (环境变量)

```bash
FEISHU_APP_ID=cli_a978bc2547f89cd1
FEISHU_APP_SECRET=IvDYEj...iTwq
FEISHU_DOMAIN=feishu
FEISHU_CONNECTION_MODE=websocket
FEISHU_HOME_CHANNEL=oc_668de3bf7447f404402869fc6bb7a4ae
```

### `feishu_config.json` (自动生成)

```json
{
  "access_token": "t-g1045hkWC6Q2ZKFQG5TFVHDK4D7H4NTQLTF7L7RD",
  "feishu_home_channel": "oc_668de3bf7447f404402869fc6bb7a4ae",
  "_generated_at": "2026-05-17T21:34:11",
  "_expires_in": "约 2 小时，请定期刷新",
  "_note": "此文件包含敏感信息，请勿泄露"
}
```

---

## 自动化配置

### Cron 定时刷新 Token

```bash
hermes cron create --name "每小时 Feishu Token 刷新" \
    --script refresh_feishu_token.py \
    --no-agent "0 * * * *"
```

**原因**: Token 有效期约 2 小时，每小时刷新确保可用性。

---

## 故障排查

### Token 获取失败

**症状**: `获取 token 失败: 'data'`

**原因**: 代码尝试访问 `data['data']['tenant_access_token']`，但实际响应中 token 在顶层。

**修复**: 修改为 `data['tenant_access_token']`

### 文件发送失败

**症状**: `发送失败: ...`

**排查步骤**:
1. 检查 `feishu_config.json` 是否存在且包含有效 token
2. 检查 token 是否过期（运行 `refresh_feishu_token.py` 刷新）
3. 检查文件路径是否正确
4. 检查频道 ID 是否有效

### 配置缺失

**症状**: `Feishu 配置未找到`

**修复**: 
1. 运行 `hermes gateway setup` 配置 Feishu
2. 或手动创建 `~/.hermes/.env` 文件

---

## API 端点

| 操作 | 端点 | 方法 |
|------|------|------|
| 获取 tenant token | `/open-apis/auth/v3/tenant_access_token/internal` | POST |
| 上传文件 | `/open-apis/im/v1/files` | POST (multipart) |
| 发送消息 | `/open-apis/im/v1/messages?receive_id_type=chat_id` | POST |

---

## 相关脚本

| 脚本 | 功能 |
|------|------|
| `refresh_feishu_token.py` | 从 .env 获取 App ID/Secret，刷新 tenant access token |
| `feishu_file_sender.py` | 上传文件并发送到 Feishu 频道 |

---

*最后更新: 2026-05-17*
