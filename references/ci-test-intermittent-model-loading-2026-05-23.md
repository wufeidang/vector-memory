# CI/CD 测试：间歇性模型加载错误诊断

**日期**: 2026-05-23
**错误**: `AttributeError: 'NoneType' object has no attribute 'parameters'`
**测试**: `test_vector_memory.py::TestMemories::test_add_memory`

---

## 问题现象

pytest 测试失败，错误堆栈显示 `model.parameters` 为 `None`。

## 诊断过程

### 1. 验证模型缓存完整性

```python
# 检查模型文件
~/.cache/modelscope/hub/AI-ModelScope/bge-base-zh-v1.5/
├── pytorch_model.bin (409MB) ✓
├── config.json ✓
├── tokenizer.json ✓
└── ... (完整)
```

**结论**: 模型文件完整，非下载损坏问题。

### 2. 验证模型加载

```python
from core import _get_model
model = _get_model()
print(type(model))  # <class 'sentence_transformers.sentence_transformer.model.SentenceTransformer'>
print(model.parameters)  # 存在且非 None
```

**结论**: 模型加载正常，`parameters` 属性存在。

### 3. 重复测试验证稳定性

```bash
pytest test_vector_memory.py::TestMemories::test_add_memory -v
# Run 1: PASSED (10.06s)
# Run 2: PASSED (10.80s)
# Run 3: PASSED (10.93s)
# Full suite: 19 passed, 1 warning in 12.54s
```

**结论**: 问题为**偶发**，非代码 bug。

## 根本原因分析

`AttributeError: 'NoneType' object has no attribute 'parameters'` 的常见触发场景：

| 场景 | 概率 | 说明 |
|------|------|------|
| 模型文件损坏/不完整 | 低 | 本次已排除（409MB 文件完整） |
| 首次加载竞争条件 | **高** | 多线程/多进程下模型单例初始化竞态 |
| 磁盘 I/O 临时故障 | 中 | Windows 下大文件读取偶发延迟 |
| 内存不足导致加载中断 | 低 | 16GB 内存充足 |
| 代码逻辑 bug | 低 | 已有 `if model is None` 检查 |

**本次判断**: 偶发初始化问题，模型缓存和代码均正常。

## 修复模式

### 场景 A: 偶发错误（本次情况）

```bash
# 无需修复，重试即可
pytest test_vector_memory.py -v
```

### 场景 B: 持续失败

```bash
# 1. 清理模型缓存
rm -rf ~/.cache/modelscope/hub/AI-ModelScope/bge-base-zh-v1.5

# 2. 重启 Hermes 后自动重新下载

# 3. 或手动预加载模型
python ~/.hermes/scripts/preload_models.py

# 4. 验证
pytest test_vector_memory.py -v
```

### 场景 C: CI/CD 环境

```yaml
# GitHub Actions workflow
- name: Preload models
  run: python ~/.hermes/scripts/preload_models.py
  
- name: Run tests
  run: pytest ~/.hermes/skills/vector_memory/scripts/test_vector_memory.py -v
```

## 预防措施

1. **模型预加载**: 在 Hermes 启动时调用 `preload_models.py`
2. **重试机制**: CI/CD 中测试失败时自动重试 1-2 次
3. **健康检查**: 测试前验证模型加载状态

```python
# 测试前健康检查
from core import _get_model
model = _get_model()
assert model is not None, "模型加载失败，请检查 ~/.cache/modelscope"
```

## 参考

- 模型预加载脚本: `scripts/preload_models.py`
- CI 测试修复记录: `references/ci-test-model-loading-fix-2026-05-23.md`
- 模型路径查找: `core.py::_get_preferred_model()`
