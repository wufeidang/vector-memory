# 项目进度追踪工作流

## 场景

当用户询问项目进度或需要记录项目状态时，使用此工作流将项目信息结构化地添加到记忆系统。

## 步骤

### 1. 检查项目实际状态

```bash
# 列出项目目录结构
ls -la /path/to/project/

# 读取项目配置文件
cat /path/to/project/README.md
cat /path/to/project/project-plan.md
cat /path/to/project/publishing-log.md
```

### 2. 提取关键信息

| 信息类型 | 来源文件 | 提取内容 |
|----------|----------|----------|
| 项目概述 | README.md | 定位、目标读者、发布渠道 |
| 文章列表 | articles/ 目录 | 已完成的 HTML 文件 |
| 发布状态 | publishing-log.md | 已发布/待发布状态 |
| 发展规划 | project-plan.md | 阶段规划、技术模块 |

### 3. 结构化添加到记忆

```python
from vector_memory import add_batch

# 添加项目概览
add_batch({
    "texts": [
        "监控维修实战教程系列（monitor-tutorial-series）：已完成 7 篇文章（第 01-07 期），均待发布",
        "监控教程第 01 期：POE 供电原理与故障排查（已完成，待发布）",
        "监控教程第 02 期：NVR 常见报警代码解析（已完成，待发布）",
        # ... 继续添加每篇文章
    ],
    "metadatas": [
        {"category": "公众号项目", "project": "monitor-tutorial-series", "status": "7 篇已完成，待发布", "articles": 7},
        {"category": "公众号项目", "project": "monitor-tutorial-series", "article": "01", "topic": "POE 供电故障排查", "status": "已完成"},
        {"category": "公众号项目", "project": "monitor-tutorial-series", "article": "02", "topic": "NVR 报警处理", "status": "已完成"},
        # ... 继续添加元数据
    ]
})
```

### 4. 验证记忆一致性

```python
from vector_memory import search_memories

# 搜索项目记忆
result = search_memories({"text": "公众号项目", "top_k": 10})

# 对比记忆中的标题与实际文章标题
# 发现不一致时，清空并重新添加
```

## 元数据规范

| 字段 | 必填 | 说明 |
|------|------|------|
| `category` | ✅ | `公众号项目` / `系统优化` / `其他` |
| `project` | ✅ | 项目标识符，如 `monitor-tutorial-series` |
| `article` | ⚠️ | 文章期数，如 `01`, `02` |
| `topic` | ⚠️ | 文章主题 |
| `status` | ✅ | `已完成` / `待发布` / `待启动` / `进行中` |
| `articles` | ⚠️ | 文章总数（用于概览） |
| `phase` | ⚠️ | 阶段标识，如 `第一阶段`, `Phase 1` |

## 注意事项

1. **标题一致性**：记忆中的文章标题必须与实际文件标题一致
2. **状态准确**：`已完成` ≠ `已发布`，区分清楚
3. **定期同步**：每完成一篇文章，及时更新记忆
4. **批量添加**：使用 `add_batch()` 一次性添加多篇文章，提高效率

## 示例查询

```python
# 搜索监控教程所有文章
search_memories({"text": "监控教程", "top_k": 10})

# 搜索特定期数
search_memories({"text": "第 06 期", "top_k": 3})

# 搜索待发布文章
search_memories({"text": "待发布", "top_k": 10})

# 搜索消防教程
search_memories({"text": "消防教程", "top_k": 10})
```
