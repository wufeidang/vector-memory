# 多agent模式超时处理指南

## 问题描述

2026-05-23 在重构 Vector-Memory Web UI v4.0 时，使用 `delegate_task` 调用多agent专家模式，结果3个子agent中有2个超时（600秒限制）。

## 超时原因分析

| 子agent | 任务 | 结果 | 原因 |
|---------|------|------|------|
| 0 | 诊断bug | ❌ 超时 | 需要大量文件读取和API调用 |
| 1 | 设计UI | ✅ 完成 | 任务相对简单，73秒完成 |
| 2 | 重构后端 | ❌ 超时 | 代码量大，需要复杂逻辑 |

## 解决方案

### 方案A：直接完成（推荐）

对于复杂但可分解的任务，直接完成比依赖多agent更可靠：

```python
# 1. 先诊断问题
# 2. 分阶段创建文件
# 3. 逐步测试验证
```

### 方案B：调整多agent配置

如果必须使用多agent，考虑：

1. **减少并发数**：`delegation.max_concurrent_children` 设置为1
2. **简化任务**：将大任务拆分为更小的子任务
3. **增加超时**：目前固定600秒，无法调整

### 方案C：使用cronjob

对于长耗时任务，使用 cronjob 而非 delegate_task：

```python
cronjob(action='create', 
        prompt='重构Web UI',
        schedule='once',
        no_agent=False)  # 需要agent推理
```

## 决策树

```
任务复杂度？
├── 简单（<5步） → 直接完成
├── 中等（5-10步） → 尝试多agent（2-3并发）
└── 复杂（>10步） → 直接完成或cronjob
```

## 最佳实践

1. **预估时间**：如果任务预计超过5分钟，考虑直接完成
2. **分阶段验证**：每完成一个阶段就测试验证
3. **保留中间产物**：即使子agent超时，已完成的部分仍可用
4. **fallback机制**：多agent超时后，立即切换为直接完成模式

## 本次重构的实际流程

```
1. 诊断v3.0 bug（execute_code） ✓
2. 创建 CSS v4.0（write_file） ✓
3. 创建 base-v4.html（write_file） ✓
4. 创建 app-v4.js（write_file） ✓
5. 创建 index-v4.html（write_file） ✓
6. 创建 search-v4.html（write_file） ✓
7. 创建 memories-v4.html（write_file） ✓
8. 创建 collections/backup/monitor/export模板（write_file） ✓
9. 创建 app-v4.py（write_file） ✓
10. 测试（execute_code） ⚠️ 路径问题未完全解决
```

总耗时：约15分钟，全部直接完成，无超时。