# Feishu API 使用注意事项

## Tenant Access Token API

**端点**: `POST https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal`

**请求体**:
```json
{
  "app_id": "cli_xxx",
  "app_secret": "xxx"
}
```

**响应结构**（⚠️ 重要）:

```json
{
  "code": 0,
  "expire": 7200,
  "msg": "ok",
  "tenant_access_token": "t-g1045hkWC6Q2ZKFQG5TFVHDK4D7H4NTQLTF7L7RD"
}
```

**⚠️ 关键**: `tenant_access_token` 在响应**顶层**，不在 `data` 对象中！

```python
# ✅ 正确
token = response.json()['tenant_access_token']

# ❌ 错误（会报错 KeyError: 'data'）
token = response.json()['data']['tenant_access_token']
```

## 文件上传 API

**端点**: `POST https://open.feishu.cn/open-apis/im/v1/files`

**请求**: multipart/form-data
- `file_type`: 表单字段，值 `"stream"`
- `file_name`: 文件名
- `file`: 文件二进制内容

**响应**:
```json
{
  "code": 0,
  "data": {
    "file_key": "fil_xxx"
  }
}
```

## 发送文件消息 API

**端点**: `POST https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id`

**请求体**:
```json
{
  "receive_id": "oc_xxx",
  "msg_type": "file",
  "content": "{\"file_key\": \"fil_xxx\"}"
}
```

**⚠️ 注意**: `content` 字段必须是**JSON 字符串**（已转义），不是 JSON 对象！

```python
# ✅ 正确
content = json.dumps({"file_key": file_key})
payload = {"receive_id": channel_id, "msg_type": "file", "content": content}

# ❌ 错误（API 会报错）
payload = {"receive_id": channel_id, "msg_type": "file", "content": {"file_key": file_key}}
```

## Token 有效期

- Tenant access token 有效期约 **2 小时**
- 建议每小时刷新一次
- 可使用 `refresh_feishu_token.py` 脚本自动获取

## 配置文件

脚本读取 `~/.hermes/feishu_config.json`:
```json
{
  "access_token": "t-g1045hkWC6Q2ZKFQG5TFVHDK4D7H4NTQLTF7L7RD",
  "feishu_home_channel": "oc_668de3bf7447f404402869fc6bb7a4ae",
  "_generated_at": "2026-05-17T21:34:11",
  "_expires_in": "约 2 小时，请定期刷新"
}
```

## 相关脚本

- `~/.hermes/scripts/refresh_feishu_token.py` — 获取并刷新 token
- `~/.hermes/scripts/feishu_file_sender.py` — 发送文件到 Feishu
