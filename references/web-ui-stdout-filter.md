# Web UI 搜索 stdout 过滤

## 问题

`vector_memory.py` 的 `_get_model()` 等函数使用 `print()` 输出日志到 stdout：

```
✅ 发现 ModelScope 模型: C:\Users\Nemo\.cache\modelscope\...
✅ 选择模型: BGE 中文模型（推荐）
   路径: C:\Users\Nemo\.cache\modelscope\...
✅ 模型加载成功: SentenceTransformer(...)
```

Flask Web UI 的 `api_search()` 通过 `subprocess.run(capture_output=True)` 捕获 stdout，这些日志被当作搜索结果返回，导致页面显示乱码。

## 解决方案

### 方案 A：在 Web UI 中过滤（快速修复）

在 `app.py` 的 `api_search()` 中过滤日志行：

```python
def api_search():
    data = request.get_json()
    query = data.get('query', '')
    if not query:
        return jsonify({"success": False, "error": "请输入搜索关键词"})
    
    result = run_script('vector_memory.py', ['search', query])
    if result.get('success'):
        # 过滤掉日志行
        lines = result['stdout'].strip().split('\n') if result['stdout'] else []
        filtered = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # 跳过日志行
            if line.startswith('✅') or line.startswith('⚠️') or line.startswith('ℹ️') or line.startswith('Loading'):
                continue
            # 只保留搜索结果行（格式: [0.xxxx] 内容）
            if line.startswith('[') and '] ' in line:
                filtered.append(line)
        return jsonify({"success": True, "results": filtered, "count": len(filtered)})
    else:
        return jsonify({"success": False, "error": result.get('error', '搜索失败')})
```

### 方案 B：修改 vector_memory.py（推荐长期方案）

将日志输出到 stderr，结果输出到 stdout：

```python
# 在 vector_memory.py 中
import sys

def _get_model():
    # 日志输出到 stderr
    print("✅ 发现 ModelScope 模型", file=sys.stderr)
    # ...
    
def search_memories(args):
    # 结果输出到 stdout
    print(f"[{score:.4f}] {text}")
```

这样 Web UI 捕获 stdout 时只包含搜索结果，无需过滤。

## 性能影响

- **方案 A**：无性能影响，只是字符串处理
- **方案 B**：无性能影响，只是 IO 重定向

## 最佳实践

- CLI 工具应将日志输出到 stderr，结果输出到 stdout
- Web API 捕获 stdout 时应过滤非结果行
- 搜索结果格式统一为 `[0.xxxx] 内容` 便于解析
