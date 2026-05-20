# Web UI 搜索 stdout 日志过滤

## 问题背景

Web UI 搜索 API 返回结果包含模型加载日志，而非仅搜索结果：

```
✅ 发现 ModelScope 模型: C:\Users\Nemo\.cache\modelscope\hub\AI-ModelScope\bge-base-zh-v1.5
✅ 选择模型: BGE 中文模型（推荐）
   路径: C:\Users\Nemo\.cache\modelscope\hub\AI-ModelScope\bge-base-zh-v1.5
✅ 模型加载成功: SentenceTransformer(...)
[0.2570] Vector-Memory 10 项优化全部完成...
```

## 原因

`vector_memory.py` 的 `_get_model()` 等函数使用 `print()` 输出日志到 stdout，而 Flask `run_script()` 捕获整个 stdout 作为结果。

## 修复方案

在 `api_search()` 中过滤日志行，只保留 `[0.xxxx] 内容` 格式的搜索结果：

```python
def api_search():
    data = request.get_json()
    query = data.get('query', '')
    if not query:
        return jsonify({"success": False, "error": "请输入搜索关键词"})
    result = run_script('vector_memory.py', ['search', query])
    if result.get('success'):
        # 过滤掉日志行（✅、⚠️、ℹ️、Loading weights 等）
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

## 最佳实践

- **CLI 工具应将日志输出到 stderr**，结果输出到 stdout
- **Web API 捕获 stdout 时应过滤非结果行**
- **搜索结果格式统一为 `[0.xxxx] 内容`** 便于解析

## 优化后（v1.1）

v1.1 版本采用直接导入模式，无需 subprocess，因此无需过滤 stdout。但此模式仍适用于其他 CLI 工具。
