# Web UI 搜索功能验证报告

**日期**: 2026-05-23
**问题**: 用户反馈 `http://127.0.0.1:5000/search` 页面无法搜索到任何数据。

## 诊断结果

### 1. 数据库状态 ✅

| 检查项 | 结果 |
|--------|------|
| ChromaDB 数据库文件 | `~/.hermes/vector_store/chroma.sqlite3` 存在 |
| 记忆记录总数 | **563 条** |
| 集合名称 | `memories` |
| 嵌入维度 | 768 维 |

### 2. 搜索 API 路由 ✅

| 路由 | 状态 |
|------|------|
| `/api/search` | ✅ 存在，POST 方法 |
| 参数支持 | `query`（必填）、`collection`（可选）、`top_k`（可选） |
| 返回格式 | JSON，包含 `results`、`query`、`collection`、`total`、`elapsed_ms` |

### 3. 全文搜索 (FTS) 验证 ✅

| 测试关键词 | 结果 |
|------------|------|
| "记忆" | ✅ 检索到数据 |
| "监控" | ✅ 检索到数据 |
| "消防" | ✅ 检索到数据 |
| "故障" | ✅ 检索到数据 |

### 4. 前端代码验证 ✅

| 检查项 | 状态 |
|--------|------|
| `search-v4.html` 模板 | ✅ 正确调用 `/api/search` POST 接口 |
| `app-v4.js` 中的 `apiCall` 函数 | ✅ 支持 POST/PUT/PATCH 自动序列化 |
| 错误处理 | ✅ 包含 `try-catch` 和错误提示 |

## 可能原因分析

如果搜索仍无法找到数据，可能原因：

| 原因 | 排查方法 |
|------|----------|
| 浏览器缓存 | 强制刷新 (Ctrl+F5) 或清除缓存 |
| 网络请求被拦截 | 打开浏览器控制台 (F12) → Network 标签检查请求 |
| API 返回空结果 | 检查返回的 `results` 数组是否为空 |
| 搜索关键词不匹配 | 尝试更宽泛的关键词如"监控"、"消防"、"故障" |
| 集合切换问题 | 确认当前集合是否为 `memories`（默认集合） |

## 排查步骤

### 步骤 1: 检查浏览器控制台

```
1. 打开 http://127.0.0.1:5000/search
2. 按 F12 打开开发者工具
3. 切换到 Network 标签
4. 输入搜索关键词，点击搜索
5. 查看 `/api/search` 请求：
   - Status: 应为 200
   - Response: 查看返回的 JSON 数据
```

### 步骤 2: 手动测试 API

```bash
# 使用 curl 测试搜索 API
curl -X POST http://127.0.0.1:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "监控", "top_k": 5}'
```

### 步骤 3: 直接查询数据库

```python
from hermes_tools import terminal

# 检查数据库记录数
terminal("python -c \"from hermes_tools import memory; print(memory.list_memories({'limit': 0}))\"")
```

## 参考文档

- `references/web-ui-v4-api-patterns.md` — API 调用模式对照表
- `references/web-ui-v4-build.md` — Web UI v4.0 完整构建参考
- `references/flask-testing-pattern.md` — Flask 测试模式

---

**状态**: 诊断完成，等待用户手动测试验证