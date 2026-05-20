# Gateway 性能调优指南

> 基于 2026-05-17 会话诊断发现

## 问题现象

Feishu 消息回复异常缓慢：

| 响应 | 耗时 | API 调用次数 |
|------|------|-------------|
| 响应 1 | 143.1 秒 (2 分 23 秒) | 1 |
| 响应 2 | 1479.1 秒 (24 分 39 秒) | 7 |
| **平均** | **811 秒 (13.5 分钟)** | — |

## 根本原因

### 1. `max_turns` 设置过高

```yaml
# config.yaml 中
max_turns: 90  # ⚠️ 太高了！
```

这意味着 Agent 最多可以执行 **90 轮** 工具调用/思考迭代。对于简单查询，这会导致不必要的延迟。

### 2. `max_iterations` 偏高

```yaml
max_iterations: 50  # ⚠️ 建议降低
```

### 3. Gateway 频繁重启

一天内重启 **7 次**（20:28, 20:29, 20:34, 20:57, 21:00, 21:06, 21:19），可能原因：
- 超时导致崩溃
- 配置变更触发重启
- 资源问题

## 解决方案

### 方案 1：降低 max_turns（推荐）

```bash
hermes config set agent.max_turns 20
```

**效果**：简单查询通常 1-3 轮即可完成，20 轮上限足够处理复杂任务。

### 方案 2：降低 max_iterations

```bash
hermes config set agent.max_iterations 20
```

### 方案 3：切换更快的模型

当前模型 `z-ai/glm-5.1` (NVIDIA NIM) 响应较慢。可考虑：

| 模型 | 特点 |
|------|------|
| `sensenova-6.7-flash-lite` | 商汤，响应快 |
| `gpt-4o-mini` | 如果 OpenAI API 可用 |

### 方案 4：检查 Gateway 稳定性

1. 检查 `.env` 中的 API 密钥是否有效
2. 查看完整错误日志：`hermes logs gateway --lines 500`
3. 检查 `max_turns` 和 `max_iterations` 配置

## 验证方法

修改配置后，重启 Gateway：

```bash
hermes gateway restart
```

观察日志中的响应时间：

```bash
hermes logs gateway --lines 50
# 查找 "response ready" 行中的 time= 字段
```

理想响应时间：< 30 秒（简单查询），< 60 秒（复杂任务）。

## 配置参考

```yaml
# 推荐配置
agent:
  max_turns: 20
  max_iterations: 20

gateway:
  gateway_timeout: 600      # 降低超时
  gateway_timeout_warning: 300
  restart_drain_timeout: 120
```

---

*最后更新: 2026-05-17*
