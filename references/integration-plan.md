# Vector-Memory 与 Hermes 集成方案

## 整体架构

```
Hermes 会话启动
    │
    ├── 每次对话 → 自动搜索 Vector-Memory（获取相关上下文）
    │       │
    │       └── 命中 → 结果注入系统提示 / 对话流
    │
    └── 用户透露 → 自动保存到 Vector-Memory
            │
            └── 专业知识 → 语义编码 → ChromaDB 存储
```

## 三种集成模式

### 模式 A：Hermes 技能（自动触发，推荐）

Hermes 加载 `vector-memory` 技能后，在每次对话中手动触发搜索：

```python
# 对话中触发搜索
from vector_memory_scripts.core import _get_collection
from vector_memory_scripts.search import search_memories

# 自动搜索（Hermes 在系统提示中注册此行为）
result = search_memories({"text": user_message, "top_k": 3})
if result.get("count", 0) > 0:
    # 将结果注入当前对话上下文
    context = "\n".join([r["text"] for r in result["results"]])
```

**实现方式：** 修改 Hermes 的 `agent/prompt_builder.py`，在用户消息处理后，对 `vector-memory` 注册的 trigger keywords 匹配时自动调用搜索。

### 模式 B：Cron 定时任务（自动同步）

使用 Hermes 内置 cron 执行定期同步：

```bash
# 同步 MEMORY.md ↔ 向量库（每小时）
hermes cron create --name "向量记忆同步" \
  --script ~/.hermes/skills/vector-memory/scripts/sync_memory_reliable.py \
  --no-agent "0 * * * *"

# 每日记忆摘要
hermes cron create --name "记忆摘要" \
  --script ~/.hermes/skills/vector-memory/scripts/backup_memory.py \
  --no-agent "0 8 * * *"

# 模型预加载（网关启动后）
hermes cron create --name "模型预加载" \
  --script ~/.hermes/skills/vector-memory/scripts/preload_models.py \
  --no-agent "@reboot"
```

### 模式 C：网关平台集成（Feishu 等）

结合 Feishu 飞书实现多渠道知识管理：

```bash
# 配置 Feishu 自动记录
export FEISHU_APP_ID=cli_xxx
export FEISHU_APP_SECRET=xxx

# 定时刷新 Token
hermes cron create --name "Feishu Token 刷新" \
  --script refresh_feishu_token.py \
  --no-agent "0 * * * *"
```

## 自动搜索触发规则

在 Hermes 系统提示中加入以下指令：

```
## 向量记忆系统
你安装了 Vector-Memory 知识库（ChromaDB + BGE 中文嵌入）。
规则：
1. 当用户提到设备型号、故障现象、技术参数、经验总结时，
   自动调用 search_memories({"text": "用户输入"}) 获取相关记忆
2. 当用户分享故障处理步骤、设备参数、专业经验时，
   提示用户「要保存到记忆库吗？」
3. 搜索结果融入回答，不打断对话流畅性
```

## 部署检查清单

- [ ] 安装依赖：`uv pip install --system chromadb sentence-transformers torch scikit-learn modelscope flask`
- [ ] 首次运行：`python vector_memory.py stats`（自动下载模型，~2.2GB）
- [ ] 验证搜索：`python vector_memory.py search "测试"`
- [ ] 创建 cron 同步任务
- [ ] 测试自动搜索注入
- [ ] （可选）模型预加载：修改网关启动脚本加入 `preload_models.py`

## 存储容量估算

| 记忆数 | 向量库大小 |
|--------|-----------|
| 1,000 条 | ~3.4 MB |
| 10,000 条 | ~34 MB |
| 100,000 条 | ~340 MB |

> 单条记忆 ~3.5 KB（768 维嵌入 + 元数据 + 内容）
> 模型缓存 ~2.2 GB（BGE 中文 + 英文备选）
