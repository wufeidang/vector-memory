# Web UI v2.0 构建参考

## 架构概览

```
memory_web/
├── app.py              # Flask 应用（28 个路由）
├── templates/          # Jinja2 模板
│   ├── base.html       # 基模板（导航、页脚）
│   ├── index.html      # 仪表盘
│   ├── search.html     # 搜索（含高级选项）
│   ├── memories.html   # 记忆管理
│   ├── collections.html # 集合管理
│   ├── backup.html     # 备份管理
│   ├── monitor.html    # 性能监控
│   └── export.html     # 数据导出/导入
└── static/
    ├── css/style.css   # 样式（模态框、表单、徽章等）
    └── js/main.js      # 通用 JS（API 调用、工具函数）
```

## 路由清单

| 路由 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 首页仪表盘 |
| `/search` | GET | 搜索页面 |
| `/memories` | GET | 记忆管理 |
| `/collections` | GET | 集合管理 |
| `/backup` | GET | 备份管理 |
| `/monitor` | GET | 性能监控 |
| `/export` | GET | 数据导出 |
| `/api/status` | GET | 系统状态 |
| `/api/stats` | GET | 性能统计 |
| `/api/search` | POST | 搜索记忆 |
| `/api/search/status` | GET | 模型加载状态 |
| `/api/backup/create` | POST | 创建备份 |
| `/api/backup/list` | GET | 列出备份 |
| `/api/backup/restore/<name>` | POST | 恢复备份 |
| `/api/collections/list` | GET | 列出集合 |
| `/api/collections/create` | POST | 创建集合 |
| `/api/collections/switch/<name>` | POST | 切换集合 |
| `/api/collections/delete/<name>` | POST | 删除集合 |
| `/api/memories/list` | GET | 列出记忆 |
| `/api/memories/add` | POST | 添加记忆 |
| `/api/memories/<id>` | GET | 获取记忆详情 |
| `/api/memories/delete/<id>` | POST | 删除记忆 |
| `/api/export` | POST | 导出数据 |
| `/api/export/download/<file>` | GET | 下载导出文件 |
| `/api/export/delete/<file>` | POST | 删除导出文件 |
| `/api/import` | POST | 导入 JSON 数据 |
| `/api/report/generate` | POST | 生成性能报告 |

## 关键实现模式

### 1. 模型预加载

```python
_vm_module = None
_vm_model_loaded = False

def _preload_vector_memory():
    global _vm_module, _vm_model_loaded
    _vm_module = importlib.import_module("vector_memory")
    _vm_module._get_model()  # 触发模型加载
    _vm_model_loaded = True
```

### 2. 确保模型加载

```python
def ensure_vm_loaded():
    if _vm_module is None or not _vm_model_loaded:
        _preload_vector_memory()
    return _vm_module is not None and _vm_model_loaded
```

### 3. 辅助函数隔离

所有数据获取逻辑封装为独立函数，页面路由和 API 路由复用：

```python
def get_backup_list(): ...
def get_performance_stats(hours=24): ...
def get_report_list(): ...
def get_export_list(): ...
def get_recent_logs(hours=24): ...
```

### 4. 模板变量传递

页面路由传递模板所需的所有变量：

```python
@app.route('/memories')
def memories_page():
    collections = []
    memories = []
    if ensure_vm_loaded():
        coll_result = _vm_module.list_collections()
        list_result = _vm_module.list_memories({"limit": 50})
        # ...
    return render_template('memories.html', collections=collections, memories=memories)
```

## 启动命令

```cmd
cd C:\Users\Nemo\.hermes\scripts\memory_web
python app.py
```

访问：http://localhost:5000

## 前端功能

| 功能 | 实现方式 |
|------|----------|
| 模型状态指示 | 导航栏绿/红点 + `api/status` 轮询 |
| 统计自动刷新 | `setInterval` 每 30 秒调用 `api/stats` |
| 搜索高亮 | 根据得分显示绿/黄/灰徽章 |
| 模态框 | CSS `.modal-overlay` + JS `openModal/closeModal` |
| 表单验证 | JS `validateForm()` 检查必填字段 |
| 错误处理 | JS `handleError()` 统一提示 |

## 注意事项

1. **Windows 路径**：`os.path.expanduser("~/.hermes")` 返回混合路径，需用 `os.path.abspath()` 归一化
2. **模板路径**：`template_folder` 需指定绝对路径
3. **静态文件**：`static_folder` 需指定绝对路径
4. **模型加载失败**：UI 应优雅降级，显示错误信息而非崩溃
