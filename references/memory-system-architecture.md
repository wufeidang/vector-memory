# 记忆系统架构与部署指南

## 系统概览

完整的 Hermes 记忆系统包含以下组件：

```
~/.hermes/
├── .env                          # 环境变量（Feishu 凭证等）
├── feishu_config.json            # Feishu API Token（自动刷新）
├── memories/
│   └── MEMORY.md                 # 记忆文件（人类可读，7 条示例）
├── vector_store/                 # ChromaDB 向量数据库
├── reports/                      # 生成的报告
│   ├── memory_summary_*.md       # 记忆摘要报告
│   └── noise_summary_*.md        # 噪声检测报告
├── scripts/                      # 自动化脚本
│   ├── auto_record.py            # 关键词触发自动记录
│   ├── daily_memory_summary.py   # 每日记忆摘要
│   ├── daily_noise_summary.py    # 每日噪声检测
│   ├── download_embedding_model.py # 嵌入模型下载
│   ├── feishu_file_sender.py     # Feishu 文件发送
│   ├── refresh_feishu_token.py   # Feishu Token 刷新
│   └── sync_memory.py            # 记忆双向同步
└── skills/
    └── vector_memory/            # 向量记忆技能
        ├── SKILL.md
        └── scripts/
            └── vector_memory.py  # 核心实现
```

## 容量分析

| 组件 | 当前大小 | 说明 |
|------|----------|------|
| MEMORY.md | ~1 KB | 7 条记忆 |
| 向量库 | ~2.3 MB | 6 条记忆 + 索引 |
| 模型缓存 | ~2.2 GB | BGE 中文模型 + 英文备选 |
| **总计** | **~2.3 GB** | — |

### 存储估算

| 记忆数量 | 向量库大小 |
|----------|------------|
| 1,000 条 | ~3.4 MB |
| 10,000 条 | ~34 MB |
| 100,000 条 | ~340 MB |
| 1,000,000 条 | ~3.4 GB |

> 单条记忆存储约 3.5 KB（768 维嵌入 + 元数据 + 内容）

## 嵌入模型

| 模型 | 路径 | 维度 | 大小 | 用途 |
|------|------|------|------|------|
| BGE Base 中文 v1.5 | `~/.cache/modelscope/hub/AI-ModelScope/bge-base-zh-v1.5` | 768 | ~391 MB | 主要使用 |
| all-MiniLM-L6-v2 | `~/.cache/modelscope/hub/AI-ModelScope/all-MiniLM-L6-v2` | 384 | ~932 MB | 英文备选 |

## Cron 定时任务

| 中文名称 | 调度 | 脚本 | 功能 |
|----------|------|------|------|
| 每日记忆摘要 | `0 8 * * *` | `daily_memory_summary.py` | 按类别统计记忆 |
| 每日噪声检测 | `0 9 * * *` | `daily_noise_summary.py` | 检测重复/相似记忆 |
| 每小时记忆同步 | `0 * * * *` | `sync_memory.py` | 同步 MEMORY.md ↔ 向量库 |
| 每小时 Feishu Token 刷新 | `0 * * * *` | `refresh_feishu_token.py` | 刷新 API token |

### 管理命令

```bash
# 查看任务
hermes cron list

# 创建任务
hermes cron create --name "任务名称" --script script.py --no-agent "0 * * * *"

# 编辑任务（包括中文名称）
hermes cron edit <job_id> --name "新名称"

# 手动运行
hermes cron run <job_id>

# 删除任务
hermes cron remove <job_id>
```

## 部署步骤

### 1. 安装依赖

```bash
pip install chromadb sentence-transformers torch numpy scikit-learn modelscope requests
```

### 2. 下载嵌入模型

```bash
python ~/.hermes/scripts/download_embedding_model.py
```

或手动下载：
```bash
python -c "from modelscope.hub.snapshot_download import snapshot_download; snapshot_download('AI-ModelScope/bge-base-zh-v1.5')"
```

### 3. 配置 Feishu（可选）

在 `.env` 中添加：
```bash
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_DOMAIN=feishu
FEISHU_HOME_CHANNEL=oc_xxx
```

### 4. 刷新 Feishu Token

```bash
python ~/.hermes/scripts/refresh_feishu_token.py
```

### 5. 创建 Cron 任务

```bash
# 记忆同步
hermes cron create --name "每小时记忆同步" --script sync_memory.py --no-agent "0 * * * *"

# 记忆摘要
hermes cron create --name "每日记忆摘要" --script daily_memory_summary.py --no-agent "0 8 * * *"

# 噪声检测
hermes cron create --name "每日噪声检测" --script daily_noise_summary.py --no-agent "0 9 * * *"

# Feishu Token 刷新
hermes cron create --name "每小时 Feishu Token 刷新" --script refresh_feishu_token.py --no-agent "0 * * * *"
```

### 6. 验证部署

```bash
# 测试同步脚本
python ~/.hermes/scripts/sync_memory.py

# 测试摘要脚本
python ~/.hermes/scripts/daily_memory_summary.py

# 测试噪声检测
python ~/.hermes/scripts/daily_noise_summary.py

# 测试 Feishu Token 刷新
python ~/.hermes/scripts/refresh_feishu_token.py

# 测试 Feishu 文件发送
python ~/.hermes/scripts/feishu_file_sender.py <测试文件>

# 查看 Cron 任务
hermes cron list
```

## 故障排查

### Cron 路径问题

**问题**: `Script not found: ~/.hermes/scripts/scripts/sync_memory.py`

**原因**: Cron 作业的 `--script` 参数路径相对于 `~/.hermes/`，不应包含 `scripts/` 前缀。

**修复**:
```bash
# ❌ 错误
hermes cron create --script scripts/sync_memory.py ...

# ✅ 正确
hermes cron create --script sync_memory.py ...
```

### Feishu Token 获取失败

**问题**: `KeyError: 'data'`

**原因**: API 响应中 `tenant_access_token` 在顶层，不在 `data` 对象中。

**修复**: 使用 `refresh_feishu_token.py` 脚本（已正确处理此问题）。

### 文件编码损坏

**问题**: 文件内容为二进制乱码

**原因**: Windows 上文件写入时编码问题。

**修复**:
```python
# 删除损坏文件
os.remove(path)

# 用 Python 重新写入
with open(path, 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)
```

## 文档

完整文档: `~/.hermes/MEMORY_SYSTEM_GUIDE.md`
