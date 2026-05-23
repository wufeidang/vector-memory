# Web UI 集合数量显示为 0 修复记录

**日期**: 2026-05-23  
**问题**: 集合管理页面显示所有集合记忆数量为 0  
**影响**: 用户无法直观了解各集合数据量

## 症状

```
记忆集合
➕ 新建集合
memories  0 条  ← 实际有 564 条
```

## 根因分析

### 1. storage.py 的 list_collections() 返回格式

```python
def list_collections(args=None):
    """列出所有集合"""
    client = _get_chroma_client()
    collections = [c.name for c in client.list_collections()]
    return {"success": True, "collections": collections, "count": len(collections)}
```

**问题**: 只返回 `["memories"]` 字符串列表，不包含计数。

### 2. app-v4.py 的类型转换逻辑

```python
@app.route('/collections')
def collections_page():
    raw = storage.list_collections()
    if raw.get("success"):
        # 将字符串集合名转换为字典格式
        collections = [{"name": c, "count": 0} if isinstance(c, str) else c for c in raw.get("collections", [])]
    else:
        collections = []
    return render_template('collections-v4.html', collections=collections)
```

**问题**: 字符串集合名被硬编码为 `count: 0`。

## 修复方案

修改 `storage.py` 的 `list_collections()` 函数，查询每个集合的实际计数：

```python
def list_collections(args=None):
    """列出所有集合及其记忆数量"""
    client = _get_chroma_client()
    collections_info = []
    for collection in client.list_collections():
        count = collection.count()  # 获取实际记忆数量
        collections_info.append({
            "name": collection.name,
            "count": count
        })
    return {"success": True, "collections": collections_info, "count": len(collections_info)}
```

## 验证步骤

### 1. 直接测试 storage 模块

```python
import sys
sys.path.insert(0, 'C:\\Users\\Nemo\\.hermes\\skills\\vector_memory\\scripts')
import storage

result = storage.list_collections(None)
print(result)
# 期望输出:
# {"success": True, "collections": [{"name": "memories", "count": 564}], "count": 1}
```

### 2. 重启 Web UI

```cmd
cd C:\Users\Nemo\.hermes\scripts\memory_web
python app-v4.py
```

### 3. 浏览器访问

访问 `http://localhost:5000/collections`，确认集合显示正确数量。

## 兼容性说明

`app-v4.py` 的类型转换逻辑已兼容 dict 格式：

```python
collections = [{"name": c, "count": 0} if isinstance(c, str) else c for c in raw.get("collections", [])]
```

当 `list_collections()` 返回 dict 列表时，`isinstance(c, str)` 为 False，直接使用原 dict，无需修改。

## 相关文件

- `C:\Users\Nemo\.hermes\skills\vector_memory\scripts\storage.py` - 已修复
- `C:\Users\Nemo\.hermes\scripts\memory_web\app-v4.py` - 兼容现有逻辑
- `C:\Users\Nemo\.hermes\scripts\memory_web\templates\collections-v4.html` - 模板无需修改

## 相关陷阱

此问题与 `backup-v4.html` 的 `{{ backup.items }}` 显示问题类似，都是数据展示层面的问题：

| 问题 | 位置 | 根因 | 修复 |
|------|------|------|------|
| 备份列表 items 显示异常 | `backup-v4.html` | Jinja2 字典访问歧义 | 改用 `{{ backup['items'] }}` |
| 集合数量显示为 0 | `storage.py` | 未查询实际计数 | 调用 `collection.count()` |
