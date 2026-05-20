# Web UI 模型预加载优化

## 问题

Web UI 搜索响应慢（每次搜索约 10 秒），因为每次搜索都通过 `subprocess` 启动新进程，重新加载嵌入模型和 reranker 模型。

## 根本原因

```python
# 原实现：每次搜索启动新进程
result = run_script('vector_memory.py', ['search', query])
```

`subprocess.run()` 每次启动新 Python 进程，导致：
1. Python 解释器启动 ~0.5s
2. 导入 `vector_memory.py` ~0.3s
3. 加载 `bge-base-zh-v1.5` ~5s
4. 加载 `bge-reranker-v2-m3` ~3s
5. 执行搜索 ~0.2s

**总计：~9-10s**

## 解决方案

### 方案 A：Web UI 服务器启动时预加载

修改 `app.py`，将 `vector_memory.py` 所在目录加入 `sys.path`，服务器启动时预加载模型到内存：

```python
import sys
import importlib

# 将 vector_memory.py 所在目录加入 sys.path
VECTOR_MEMORY_SCRIPTS = r'C:\Users\Nemo\.hermes\skills\vector_memory\scripts'
if VECTOR_MEMORY_SCRIPTS not in sys.path:
    sys.path.insert(0, VECTOR_MEMORY_SCRIPTS)

_vm_module = None
_vm_model_loaded = False

def _preload_vector_memory():
    """预加载 vector_memory 模块和模型。"""
    global _vm_module, _vm_model_loaded
    if _vm_module is None:
        _vm_module = importlib.import_module("vector_memory")
        # 触发模型加载
        _vm_module._get_model()
        _vm_module._get_reranker()
        _vm_model_loaded = True
    return _vm_module

# 服务器启动时调用
_preload_vector_memory()
```

搜索时直接调用：

```python
@app.route('/search', methods=['POST'])
def api_search():
    data = request.get_json()
    query = data.get('query', '')
    if not query:
        return jsonify({"success": False, "error": "请输入搜索关键词"})
    
    vm = _preload_vector_memory()
    result = vm.search_memories({'text': query, 'top_k': 5})
    
    return jsonify(result)
```

### 方案 B：Hermes 启动时预加载模型

修改 `Hermes_Gateway.cmd`，在启动 Hermes 前先加载模型：

```cmd
@echo off
set HERMES_HOME=C:\Users\Nemo\.hermes

echo 预加载记忆系统模型...
C:\Python314\python.exe "%HERMES_HOME%\scripts\preload_models.py"

echo 启动 Hermes Gateway...
cd /d C:\Users\Nemo\AppData\Roaming\Python\Python314\site-packages
C:\Python314\python.exe -m hermes_cli.main gateway run --replace
```

`preload_models.py` 脚本：

```python
import sys
import importlib

sys.path.insert(0, r'C:\Users\Nemo\.hermes\skills\vector_memory\scripts')

vm = importlib.import_module("vector_memory")

# 加载嵌入模型
vm._get_model()
# 加载 reranker 模型
vm._get_reranker()

print("✅ 模型预加载完成")
```

## 性能对比

| 场景 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| 首次搜索 | ~10s | ~2.5s | 4x |
| 后续搜索 | ~10s | ~0.6s | 17x |

## 注意事项

1. **模型内存不共享**：每个 Python 进程独立加载模型，预加载到 Web UI 服务器不影响 Hermes Gateway
2. **内存占用**：两个模型加载后约 1.5-2GB 内存
3. **GPU 加速**：如有 GPU，可设置 `device='cuda'` 加速推理

## 相关文件

- `scripts/memory_web/app.py` → Web UI Flask 应用（v1.1 模型预加载优化版）
- `scripts/preload_models.py` → 模型预加载脚本
- `scripts/vector_memory.py` → 向量记忆核心模块