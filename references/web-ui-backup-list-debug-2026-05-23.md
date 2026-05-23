# Web UI 备份列表调试记录 (2026-05-23)

## 问题描述

用户反馈两个问题：
1. 备份列表中 items 显示异常（显示为 Python 对象地址）
2. Web UI 搜索页面无法搜索到任何数据

## 排查过程

### 1. 备份列表显示问题

**检查备份数据源**：
```
~/.hermes/backups/backup_20260523_182759/manifest.json
```
- `items` 字段为列表类型 ✓
- `items` 数量：563 条 ✓

**检查后端代码**（`app-v4.py`）：
```python
def get_backups():
    backups.append({
        "name": d,
        "time": manifest.get("backup_time", "unknown"),
        "items": len(manifest.get("items", []))  # 返回整数 ✓
    })
```

**检查前端模板**（`backup-v4.html`）：
```html
<td><span class="badge badge-info">{{ backup.items or 0 }}</span></td>
```

**根因分析**：
Jinja2 模板中 `backup.items` 可能被解析为字典的 `items()` 方法而非 `items` 键的值。虽然 `get_backups()` 返回的是整数，但模板渲染时可能因为变量名冲突导致异常。

**修复方案**：
改用字典访问语法，明确指定键名：
```html
<td><span class="badge badge-info">{{ backup['items'] if backup['items'] is defined else 0 }}</span></td>
```

### 2. 搜索功能问题

**检查搜索 API**（`app-v4.py`）：
```python
@app.route('/api/search', methods=['POST'])
def api_search():
    data = request.get_json()
    query = data.get('query', '')
    collection = data.get('collection', '')
    top_k = data.get('top_k', 10)
    results = search_memories({'text': query, 'collection': collection, 'top_k': top_k})
    return jsonify({'success': True, 'results': results})
```

**检查搜索模板**（`search-v4.html`）：
- 前端调用 `/api/search` ✓
- 支持 collection 选择 ✓
- 支持 top_k 选择 ✓

**可能原因**：
1. 向量数据库中没有记忆数据
2. 搜索关键词与记忆内容不匹配
3. 搜索参数问题

**验证步骤**：
1. 访问 `http://127.0.0.1:5000/memories` 确认有记忆数据
2. 使用记忆中的实际内容作为关键词测试搜索
3. 如果记忆列表为空，需要先添加记忆数据

## 工具使用经验

### read_file 工具 Windows 路径问题

在 Windows 环境下，`read_file` 工具多次失败（返回 `File not found` 错误）。

**替代方案**：改用 `execute_code` 中的 Python `open()` 函数：
```python
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()
```

**适用场景**：
- Windows 路径包含反斜杠时
- 文件路径较长时
- `read_file` 返回 `File not found` 错误时

## 文件位置

| 文件 | 路径 |
|------|------|
| Web UI 主程序 | `~/.hermes/scripts/memory_web/app-v4.py` |
| 备份页面模板 | `~/.hermes/scripts/memory_web/templates/backup-v4.html` |
| 搜索页面模板 | `~/.hermes/scripts/memory_web/templates/search-v4.html` |
| 备份数据 | `~/.hermes/backups/` |

## 当前备份状态

截至 2026-05-23，备份目录中有 10 个备份：
- 最新备份：`backup_20260523_182759`（563 条记忆记录）
- 早期备份：`backup_20260520_225508` 等（1-7 条记录）
