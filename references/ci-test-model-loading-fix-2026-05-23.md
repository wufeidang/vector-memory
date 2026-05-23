# CI/CD 测试修复：模型加载失败导致 AttributeError

**日期**: 2026-05-23  
**修复人**: Nemo叔叔  
**测试状态**: ✅ 19 passed, 1 warning in 12.97s

---

## 问题描述

GitHub Actions CI 中 `test_add_memory` 测试失败，抛出错误：

```
FAILED test_vector_memory.py::TestMemories::test_add_memory 
AttributeError: 'NoneType' object has no attribute 'parameters'
```

---

## 根本原因分析

### 原因 1: `_get_preferred_model()` 路径查找 bug

第一个候选路径使用了错误的 `MODEL_DIR.replace()` 构造：

```python
# ❌ 错误代码
candidates = [
    os.path.join(os.path.expanduser("~/.cache/modelscope"), "hub", 
                 MODEL_DIR.replace(os.path.expanduser("~/.cache/modelscope"), "").lstrip("/"), 
                 MODEL_NAME.replace(".", "_")),
    # ...
]
```

`MODEL_DIR` 本身已经是完整路径（`~/.cache/modelscope/hub`），再次 `replace()` 导致路径构造错误。

### 原因 2: `_get_model()` 缺乏错误处理

模型下载或加载失败时，`_model` 保持为 `None`，后续调用 `model.encode()` 触发 `AttributeError`。

### 原因 3: 存储函数未检查模型空值

`add_memory()`、`add_batch()`、`add_with_chunks()` 调用 `_get_model()` 后未检查返回值。

---

## 修复方案

### 1. 修复 `_get_preferred_model()` 路径查找

移除有 bug 的第一个候选路径，添加 6 个候选路径：

```python
def _get_preferred_model():
    """检查多个可能路径（修复 Windows 路径问题）"""
    model_short = MODEL_NAME.split("/")[-1]
    modelscope_base = os.path.expanduser("~/.cache/modelscope")
    candidates = [
        # 标准路径：hub/AI-ModelScope/model-name
        os.path.join(modelscope_base, "hub", "AI-ModelScope", model_short),
        # 替代路径：AI-ModelScope/model-name（无 hub）
        os.path.join(modelscope_base, "AI-ModelScope", model_short),
        # 带下划线的模型名（某些下载工具会替换点）
        os.path.join(modelscope_base, "hub", "AI-ModelScope", model_short.replace(".", "_")),
        os.path.join(modelscope_base, "AI-ModelScope", model_short.replace(".", "_")),
        # 直接路径检查（使用 os.sep 适配 Windows）
        os.path.join(modelscope_base, "hub", MODEL_NAME.replace("/", os.sep).replace(".", "_")),
        os.path.join(modelscope_base, MODEL_NAME.replace("/", os.sep).replace(".", "_")),
    ]
    candidates = [os.path.abspath(p) for p in candidates]
    for path in candidates:
        if os.path.exists(path) and os.path.isdir(path):
            return path
    return None
```

### 2. 增强 `_get_model()` 错误处理

```python
def _get_model(model_path=None):
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is None:
            from sentence_transformers import SentenceTransformer
            path = model_path or _get_preferred_model()
            if path is None:
                from modelscope.hub.snapshot_download import snapshot_download
                print("✅ 下载模型: %s" % MODEL_NAME, file=sys.stderr)
                try:
                    snapshot_download(MODEL_NAME, local_dir=MODEL_DIR)
                except Exception as e:
                    print("❌ 模型下载失败: %s" % str(e), file=sys.stderr)
                    raise RuntimeError("模型下载失败: %s" % str(e))
                path = _get_preferred_model()
                if path is None:
                    raise RuntimeError("模型下载后仍无法找到路径，请检查 ~/.cache/modelscope")
            print("✅ 加载嵌入模型: %s" % path, file=sys.stderr)
            try:
                _model = SentenceTransformer(path, device="cpu")
                _model.max_seq_length = 512
            except Exception as e:
                print("❌ 模型加载失败: %s" % str(e), file=sys.stderr)
                raise RuntimeError("模型加载失败: %s" % str(e))
    return _model
```

### 3. 在存储函数中添加模型空值检查

**storage.py - `add_memory()`**:
```python
def add_memory(args):
    # ...
    model = _get_model()
    if model is None:
        return {"success": False, "message": "嵌入模型加载失败，请检查模型路径"}
    # ...
```

**storage.py - `add_batch()`**:
```python
def add_batch(args):
    # ...
    model = _get_model()
    if model is None:
        return {"success": False, "message": "嵌入模型加载失败，请检查模型路径"}
    # ...
```

**storage.py - `add_with_chunks()`**:
```python
def add_with_chunks(args):
    # ...
    model = _get_model()
    if model is None:
        return {"success": False, "message": "嵌入模型加载失败，请检查模型路径"}
    # ...
```

---

## 验证方法

```bash
# 运行单个测试
pytest scripts/test_vector_memory.py::TestMemories::test_add_memory -v

# 运行全部测试
pytest scripts/test_vector_memory.py -v
```

**修复后结果**:
```
======================= 19 passed, 1 warning in 12.97s ========================
```

---

## 推送记录

```
Commit: 5690c79
Remote: https://github.com/wufeidang/vector-memory.git
Branch: master
Files: 3 files changed, 910 insertions(+), 20 deletions(-)
```

---

## 经验总结

1. **模型加载必须做错误处理** — 网络问题、磁盘空间不足、权限问题都可能导致模型下载/加载失败
2. **路径查找要覆盖多种情况** — Windows/Linux 路径分隔符不同，模型名中的点可能被替换为下划线
3. **依赖外部资源的函数要检查返回值** — `_get_model()` 返回 `None` 时，后续调用必然失败
4. **CI 环境是干净环境** — 本地能运行不代表 CI 能运行，模型可能需要首次下载

---

## 相关文件

- `scripts/core.py` — 模型加载逻辑
- `scripts/storage.py` — 记忆 CRUD 函数
- `scripts/test_vector_memory.py` — 单元测试