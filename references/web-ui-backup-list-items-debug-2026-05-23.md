# Web UI 备份列表显示问题调试记录

**日期**: 2026-05-23
**问题**: 备份页面 `backup-v4.html` 中 `{{ backup.items or 0 }}` 显示异常，显示为 `built-in method items of dict object at 0x000001141F708A00>` 而非实际数字。

## 症状

```
备份列表表格中，"记忆数量"列显示为：
built-in method items of dict object at 0x000001141F708A00
```

## 原因分析

Jinja2 模板引擎对 `{{ backup.items }}` 的解析存在歧义：

1. `backup` 是一个字典（dict）
2. `backup.items` 在 Jinja2 中被解析为**字典的 `items()` 方法**，而非 `items` 键的值
3. 这导致输出的是方法对象的字符串表示，而非实际的列表长度

## 修复方案

### 错误写法（原代码）
```html
<td><span class="badge badge-info">{{ backup.items or 0 }}</span></td>
```

### 正确写法（修复后）
```html
<td><span class="badge badge-info">{{ backup['items'] if backup['items'] is defined else 0 }}</span></td>
```

## 关键要点

### 1. Jinja2 属性访问规则

在 Jinja2 中，`{{ obj.attr }}` 会被解析为：
- 首先尝试 `obj.attr`（字典键或对象属性）
- 如果失败，尝试 `obj.get("attr")`
- 如果仍然失败，尝试 `obj.attr()`（调用方法）

对于字典对象，`backup.items` 会被优先解析为 `dict.items()` 方法！

### 2. 安全访问模式

| 场景 | 推荐语法 |
|------|----------|
| 字典键访问（安全） | `{{ backup['items'] }}` |
| 带默认值 | `{{ backup['items'] if backup['items'] is defined else 0 }}` |
| 对象属性访问 | `{{ backup.items }}`（仅当 items 是属性而非方法时） |
| 方法调用 | `{{ backup.items() }}`（显式调用） |

### 3. 调试技巧

当遇到类似显示问题时，检查：

```python
# 在 Python 中验证数据类型
backup = {'name': 'backup_20260523', 'items': ['item1', 'item2']}
print(type(backup['items']))  # <class 'list'>
print(len(backup['items']))   # 2

# 在模板中调试（临时）
{{ backup.items }}      # 可能显示方法对象
{{ backup['items'] }}   # 正确显示列表
{{ backup.items() }}    # 显示字典所有键值对
```

## 相关文件

- `~/.hermes/scripts/memory_web/templates/backup-v4.html` — 备份管理页面模板
- `~/.hermes/scripts/memory_web/app-v4.py` — 后端数据源（`get_backups()` 函数）

## 验证方法

1. 重启 Web UI: `python app-v4.py`
2. 访问 `http://127.0.0.1:5000/backup`
3. 检查备份列表中"记忆数量"列是否显示正确数字

## 关联问题

- **搜索功能验证**: 同一天的搜索功能验证发现数据库有 563 条记录，FTS 搜索正常，API 路由存在。如搜索仍无结果，检查浏览器控制台 (F12) 是否有 API 错误信息。
- **字段名陷阱**: `vector_memory` 返回的字段名与常见假设不同（`text` 而非 `content`，`results` 而非 `memories`），参考 `references/web-ui-v4-api-patterns.md`。

---

**参考**: `vector_memory` SKILL.md 中 "2026-05-23 — Web UI 备份列表显示修复" 章节