# Flask Web 应用测试模式

## 问题背景

直接启动 Flask 服务器并通过 HTTP 请求测试存在以下问题：

1. **启动慢**：模型预加载需要 8+ 秒
2. **难以捕获输出**：服务器输出被管道捕获，难以调试
3. **超时风险**：长时间运行的测试容易超时
4. **资源占用**：需要维持服务器进程

## 推荐方案：使用 `test_client()`

Flask 内置 `test_client()` 提供轻量级测试环境，无需启动实际服务器：

```python
import sys, os

# 设置路径
web_dir = os.path.expanduser('~/.hermes/scripts/memory_web')
sys.path.insert(0, web_dir)

vm_scripts = os.path.join(os.path.expanduser('~/.hermes'), 'skills', 'vector_memory', 'scripts')
if vm_scripts not in sys.path:
    sys.path.insert(0, vm_scripts)

# 导入模块
import importlib
vm = importlib.import_module("vector_memory")
import app

# 创建测试客户端
app.app.config['TESTING'] = True
client = app.app.test_client()

# 测试 GET 请求
response = client.open('/api/status', method='GET')
print(response.status_code)  # 200
print(response.get_json())   # {'model_loaded': True, ...}

# 测试 POST 请求（带 JSON）
response = client.open('/api/search', method='POST', json={'query': '测试'})
print(response.status_code)  # 200
print(response.get_json())   # {'success': True, 'results': [...]}
```

## 测试模式

```python
tests = [
    ('GET', '/api/status'),
    ('GET', '/memories'),
    ('GET', '/collections'),
    ('POST', '/api/search', {'query': '测试'}),
    ('POST', '/api/backup/create', {}),
]

for method, path, *data in tests:
    if data:
        response = client.open(path, method=method, json=data[0])
    else:
        response = client.open(path, method=method)
    
    print(f"  {method} {path}: {response.status_code}")
```

## 优势对比

| 维度 | HTTP 请求 | test_client() |
|------|-----------|---------------|
| 启动时间 | 8-15 秒 | <1 秒 |
| 输出捕获 | 困难 | 直接获取 response |
| 超时风险 | 高 | 低 |
| 资源占用 | 高（进程） | 低（内存） |
| 调试能力 | 弱 | 强（可直接检查对象） |

## 注意事项

1. **路径设置**：需将 `memory_web/` 和 `vector_memory/scripts/` 都加入 `sys.path`
2. **模型预加载**：首次导入 `vector_memory` 会触发模型加载，后续测试复用
3. **数据库状态**：测试客户端共享同一数据库，注意测试顺序和清理
4. **环境变量**：某些依赖环境变量的功能可能需要手动设置
5. **pytest 集成**：推荐使用 pytest 替代手动测试脚本，支持自动化运行和详细报告

## pytest 测试模板（推荐）

```python
import pytest
import sys, os

# 添加路径
web_dir = os.path.expanduser('~/.hermes/scripts/memory_web')
sys.path.insert(0, web_dir)

vm_scripts = os.path.join(os.path.expanduser('~/.hermes'), 'skills', 'vector_memory', 'scripts')
if vm_scripts not in sys.path:
    sys.path.insert(0, vm_scripts)

from app_v3 import create_app

@pytest.fixture
def client():
    """创建测试客户端"""
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture(autouse=True)
def setup():
    """每个测试前的设置"""
    # 可选：清理测试数据
    yield
    # 可选：测试后清理

class TestSystemStatus:
    """系统状态测试"""
    
    def test_status_endpoint(self, client):
        response = client.get('/api/system/status')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] == True
        assert 'version' in data['data']

class TestSearch:
    """搜索功能测试"""
    
    def test_basic_search(self, client):
        response = client.post('/api/search', 
            json={'text': '测试搜索', 'top_k': 3})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] == True
        assert 'results' in data['data']
    
    def test_search_with_filters(self, client):
        response = client.post('/api/search', 
            json={'text': '测试', 'top_k': 5, 
                  'where': {'category': 'tech'}})
        assert response.status_code == 200

class TestCollections:
    """集合管理测试"""
    
    def test_list_collections(self, client):
        response = client.get('/api/collections')
        assert response.status_code == 200
        data = response.get_json()
        assert 'collections' in data['data']
    
    def test_create_collection(self, client):
        response = client.post('/api/collections', 
            json={'name': 'test-collection'})
        assert response.status_code == 200
```

## 完整测试套件（v3.0 参考）

测试覆盖 15 个 API 端点，分类组织：

| 测试类 | 测试项数量 | 覆盖端点 |
|--------|-----------|----------|
| TestSystemStatus | 2 | `/api/system/status` |
| TestSearch | 4 | `/api/search`（基本/过滤器/无结果/错误处理） |
| TestCollections | 4 | `/api/collections`（列出/创建/切换/删除） |
| TestMemories | 3 | `/api/memories`（添加/列出/删除） |
| TestBackup | 2 | `/api/backup`（创建/列出） |

运行命令：
```bash
cd ~/.hermes/scripts/memory_web
pytest test_web_ui_v3.py -v --tb=short
```

输出示例：
```
test_web_ui_v3.py::TestSystemStatus::test_status_endpoint PASSED
test_web_ui_v3.py::TestSearch::test_basic_search PASSED
test_web_ui_v3.py::TestSearch::test_search_with_filters PASSED
...
============================== 15 passed in 12.34s ==============================
```

## 完整测试脚本模板

```python
#!/usr/bin/env python3
"""Web UI 测试脚本"""
import sys, os, json

web_dir = os.path.expanduser('~/.hermes/scripts/memory_web')
sys.path.insert(0, web_dir)

vm_scripts = os.path.join(os.path.expanduser('~/.hermes'), 'skills', 'vector_memory', 'scripts')
if vm_scripts not in sys.path:
    sys.path.insert(0, vm_scripts)

import importlib
importlib.import_module("vector_memory")
import app

app.app.config['TESTING'] = True
client = app.app.test_client()

def test_endpoint(method, path, json_data=None, expected_status=200):
    kwargs = {'method': method}
    if json_data is not None:
        kwargs['json'] = json_data
    response = client.open(path, **kwargs)
    
    status = "✅" if response.status_code == expected_status else "❌"
    print(f"  {status} {method} {path}: {response.status_code}")
    
    if response.status_code == 200:
        try:
            data = response.get_json()
            if data and 'error' in data:
                print(f"     错误: {data['error'][:100]}")
        except:
            pass
    return response.status_code == expected_status

print("Web UI 端点测试:")
tests = [
    ('GET', '/api/status'),
    ('GET', '/'),
    ('GET', '/search'),
    ('GET', '/memories'),
    ('GET', '/collections'),
    ('GET', '/backup'),
    ('GET', '/monitor'),
    ('GET', '/export'),
    ('GET', '/api/stats'),
    ('GET', '/api/search/status'),
    ('GET', '/api/backup/list'),
    ('GET', '/api/collections/list'),
    ('POST', '/api/search', {'query': '测试'}),
]

passed = sum(test_endpoint(*t) for t in tests)
print(f"\n结果: {passed}/{len(tests)} 通过")
```