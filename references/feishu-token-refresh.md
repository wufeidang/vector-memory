# Feishu Token 刷新脚本

## 脚本位置

`~/.hermes/scripts/refresh_feishu_token.py`

## 功能

从 `.env` 文件读取 Feishu App ID 和 App Secret，调用 Feishu 开放平台 API 获取 tenant access token，并生成配置文件。

## 使用方式

```bash
python ~/.hermes/scripts/refresh_feishu_token.py
```

## 输出

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

## API 端点

```
POST https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal
```

**请求体**:
```json
{
  "app_id": "cli_xxx",
  "app_secret": "xxx"
}
```

**响应**（⚠️ 注意 token 位置）:
```json
{
  "code": 0,
  "expire": 7200,
  "msg": "ok",
  "tenant_access_token": "t-g1045..."
}
```

**关键**: `tenant_access_token` 在响应**顶层**，不在 `data` 对象中！

```python
# ✅ 正确
token = response.json()['tenant_access_token']

# ❌ 错误
token = response.json()['data']['tenant_access_token']  # KeyError
```

## 依赖

- `.env` 文件包含 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET`
- `requests` 库（已安装）

## Cron 定时刷新

建议每小时自动刷新 token：

```bash
hermes cron create --name "每小时 Feishu Token 刷新" --script refresh_feishu_token.py --no-agent "0 * * * *"
```

## Token 有效期

- Tenant access token 有效期约 **2 小时**
- 建议每小时刷新一次
- 过期后需重新运行脚本获取新 token

## 相关文件

- `~/.hermes/.env` — Feishu 应用凭证
- `~/.hermes/feishu_config.json` — 生成的 token 配置
- `~/.hermes/scripts/feishu_file_sender.py` — 文件发送脚本（依赖此配置）
