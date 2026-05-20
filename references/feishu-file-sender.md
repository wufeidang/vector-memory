# Feishu 文件发送脚本

## 脚本位置

`~/.hermes/scripts/feishu_file_sender.py`

## 功能

通过 Feishu 开放 API 上传文件并发送到指定频道。

## 用法

```bash
python ~/.hermes/scripts/feishu_file_sender.py <文件路径> [频道ID]
```

如果未提供频道 ID，使用配置文件中的 `feishu_home_channel`。

## 配置要求

### 必需配置文件

脚本需要 `~/.hermes/feishu_config.json`：

```json
{
  "access_token": "从 Feishu 开放平台获取的 token",
  "feishu_home_channel": "oc_xxxxxxxxxxxxxxxxxxxxx"
}
```

### 获取 access_token

1. 访问 https://open.feishu.cn/app
2. 进入应用 → 凭证与基础信息
3. 获取 `App ID` 和 `App Secret`（已在 `.env` 中配置）
4. 调用 API 获取 tenant access token：

```bash
curl -X POST "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal" \
  -H "Content-Type: application/json" \
  -d '{
    "app_id": "cli_a978bc2547f89cd1",
    "app_secret": "你的 App Secret"
  }'
```

返回：
```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "tenant_access_token": "t-xxxxxxxxxxxxxxxxxxxxxxxx",
    "expire_in": 7200
  }
}
```

### 环境变量

`.env` 中已配置：

| 变量 | 值 |
|------|-----|
| `FEISHU_APP_ID` | `cli_a978bc2547f89cd1` |
| `FEISHU_APP_SECRET` | （已配置） |
| `FEISHU_DOMAIN` | `feishu` |
| `FEISHU_HOME_CHANNEL` | `oc_668de3bf7447f404402869fc6bb7a4ae` |

## API 端点

| 操作 | URL |
|------|-----|
| 上传文件 | `https://open.feishu.cn/open-apis/im/v1/files` |
| 发送文件消息 | `https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id` |

## 注意事项

1. **access_token 有效期**：tenant access token 有效期 2 小时，需定期刷新
2. **文件大小限制**：Feishu 对上传文件大小有限制（通常 100MB）
3. **文件类型**：支持常见文件类型（图片、文档、视频等）
4. **权限要求**：应用需有 `im:message` 和 `im:file` 权限

## 待完成

- [ ] 创建 `refresh_feishu_token.py` 脚本自动刷新 token
- [ ] 创建 `feishu_config.json` 配置文件
- [ ] 添加 token 过期自动检测与刷新

## 相关

- `hermes-windows-environment` 技能 — Windows 环境配置
- `references/feishu-config-on-windows.md` — Feishu 网关配置指南
