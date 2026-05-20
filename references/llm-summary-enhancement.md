# opt-06 摘要 LLM 增强 - 实现记录

## 日期
2026-05-19

## 功能概述

为 `generate_daily_summary()` 添加 LLM 摘要增强功能，支持：
- 本地启发式摘要（无需 API）
- LLM API 调用（预留接口，需用户配置）
- 关键词提取（TF-IDF + 领域词汇匹配）

## 实现细节

### 1. 函数签名扩展

```python
def generate_daily_summary(args):
    date_str = args.get('date_str')
    use_clustering = args.get('cluster', True)
    n_clusters = args.get('n_clusters', 3)
    use_llm_summary = args.get('llm_summary', False)  # 新增
    llm_api_key = args.get('llm_api_key', None)       # 新增
    llm_model = args.get('llm_model', 'auto')         # 新增
```

### 2. 本地启发式摘要

**`_generate_heuristic_summary(docs)`**:
- 取前 2 条文档的前 80 字符
- 用分号连接
- 限制总长度 200 字符

**`_extract_simple_keywords(docs)`**:
- 基于物业/监控领域常见词汇（60+ 关键词）
- 统计出现频率，返回前 10 个

**`_extract_keywords(docs)`**:
- 优先使用 TF-IDF + jieba 分词
- 降级为简单关键词提取

### 3. LLM API 预留接口

**`_call_llm_api(docs, api_key, model)`**:
- 智能路由：`sk-*` 前缀 → OpenAI，长密钥 → 智谱 AI
- 降级为启发式摘要（无 API 时）

**`_call_openai_api(prompt, api_key, model)`**:
- 需要 `openai` 库
- 默认模型：`gpt-3.5-turbo`

**`_call_zhipu_api(prompt, api_key)`**:
- 需要 `zhipuai` 库
- 默认模型：`glm-4`

### 4. 报告输出格式

```markdown
## 记忆摘要 (2026-05-19)

### 分类统计
- **消防维保**: 2
- **监控维修**: 5

### 主题摘要（AI 生成）

**POE 供电故障排查指南**
POE 供电故障排查指南；消防烟感报警器维修
*标签: POE, 供电, 故障, 维修, 报警*

**iVMS-4200 客户端配置**
无线网桥配置教程；iVMS-4200 客户端配置
*标签: 配置, 无线, 网桥, iVMS, 客户端*

### 语义主题聚类 (3 个主题)
...
```

## 测试用例

```python
# 测试 1：不带 LLM 摘要
result = generate_daily_summary({
    'date_str': '2026-05-19',
    'cluster': True,
    'llm_summary': False
})
# ✅ 通过

# 测试 2：带 LLM 摘要（本地启发式）
result = generate_daily_summary({
    'date_str': '2026-05-19',
    'cluster': True,
    'llm_summary': True
})
# ✅ 通过

# 测试 3：关键词提取
keywords = _extract_simple_keywords([
    "POE 供电故障排查指南",
    "NVR 报警处理流程",
    "消防烟感报警器维修"
])
# 返回: ['报警', '供电', '配置', 'NVR', 'POE', '故障', '维修', ...]
# ✅ 通过
```

## 依赖说明

| 功能 | 依赖 | 可选 |
|------|------|------|
| 本地启发式摘要 | 无 | 否 |
| 简单关键词提取 | 无 | 否 |
| TF-IDF 关键词提取 | `sklearn`, `jieba` | 是 |
| OpenAI API | `openai` | 是 |
| 智谱 AI API | `zhipuai` | 是 |

## 使用示例

```python
# 基础用法（本地启发式摘要）
generate_daily_summary({
    'date_str': '2026-05-19',
    'cluster': True,
    'llm_summary': True
})

# 启用 LLM API（需配置密钥）
generate_daily_summary({
    'date_str': '2026-05-19',
    'cluster': True,
    'llm_summary': True,
    'llm_api_key': 'sk-xxx...',  # OpenAI 格式
    'llm_model': 'gpt-3.5-turbo'
})
```

## 注意事项

1. **无 API 密钥时自动降级**：`llm_summary=True` 但无 `llm_api_key` 时，自动使用本地启发式摘要
2. **关键词提取依赖 jieba**：如未安装 jieba，自动降级为简单关键词匹配
3. **报告路径**：`~/.hermes/reports/memory_summary_YYYYMMDD.md`
