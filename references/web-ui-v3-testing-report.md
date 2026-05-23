# Web UI v3.0 测试报告

## 测试概览

| 指标 | 值 |
|------|-----|
| 测试框架 | pytest 8.3.5 |
| 测试文件 | test_web_ui_v3.py |
| 测试用例总数 | 15 |
| 通过数 | 15 |
| 失败数 | 0 |
| 通过率 | 100% |
| 总耗时 | ~12 秒 |

## 测试分类

### 1. TestSystemStatus（系统状态测试）

| 测试项 | 描述 | 结果 |
|--------|------|------|
| test_status_endpoint | 验证系统状态端点返回正确格式 | ✅ PASS |
| test_status_contains_required_fields | 验证返回数据包含 version, model_loaded 等字段 | ✅ PASS |

### 2. TestSearch（搜索功能测试）

| 测试项 | 描述 | 结果 |
|--------|------|------|
| test_basic_search | 基本搜索功能，验证返回结果格式 | ✅ PASS |
| test_search_with_filters | 带过滤器搜索（category 过滤） | ✅ PASS |
| test_search_empty_query | 空查询处理 | ✅ PASS |
| test_search_top_k_limit | top_k 参数限制验证 | ✅ PASS |

### 3. TestCollections（集合管理测试）

| 测试项 | 描述 | 结果 |
|--------|------|------|
| test_list_collections | 列出所有集合 | ✅ PASS |
| test_create_collection | 创建新集合 | ✅ PASS |
| test_switch_collection | 切换当前集合 | ✅ PASS |
| test_delete_collection | 删除集合 | ✅ PASS |

### 4. TestMemories（记忆管理测试）

| 测试项 | 描述 | 结果 |
|--------|------|------|
| test_add_memory | 添加单条记忆 | ✅ PASS |
| test_list_memories | 列出记忆 | ✅ PASS |
| test_delete_memory | 删除记忆 | ✅ PASS |

### 5. TestBackup（备份管理测试）

| 测试项 | 描述 | 结果 |
|--------|------|------|
| test_create_backup | 创建备份 | ✅ PASS |
| test_list_backups | 列出备份历史 | ✅ PASS |

## 测试代码结构

```python
import pytest
import sys, os

# 路径设置
web_dir = os.path.expanduser('~/.hermes/scripts/memory_web')
sys.path.insert(0, web_dir)

vm_scripts = os.path.join(os.path.expanduser('~/.hermes'), 'skills', 'vector_memory', 'scripts')
if vm_scripts not in sys.path:
    sys.path.insert(0, vm_scripts)

from app_v3 import create_app

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

# 测试类按功能分组
class TestSystemStatus:
    ...

class TestSearch:
    ...

class TestCollections:
    ...

class TestMemories:
    ...

class TestBackup:
    ...
```

## 关键测试模式

### 1. 测试客户端 fixture

```python
@pytest.fixture
def client():
    """每个测试使用独立的测试客户端"""
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client
```

### 2. 断言模式

```python
def test_basic_search(self, client):
    response = client.post('/api/search', 
        json={'text': '测试搜索', 'top_k': 3})
    
    # 状态码检查
    assert response.status_code == 200
    
    # JSON 格式检查
    data = response.get_json()
    assert data is not None
    assert data['success'] == True
    
    # 数据结构检查
    assert 'results' in data['data']
    assert isinstance(data['data']['results'], list)
```

### 3. 参数化测试（可选）

```python
@pytest.mark.parametrize("top_k,expected_max", [
    (1, 1),
    (5, 5),
    (10, 10),
])
def test_search_top_k_limit(self, client, top_k, expected_max):
    response = client.post('/api/search', 
        json={'text': '测试', 'top_k': top_k})
    data = response.get_json()
    assert len(data['data']['results']) <= expected_max
```

## 运行命令

```bash
# 基础运行
cd ~/.hermes/scripts/memory_web
pytest test_web_ui_v3.py -v

# 详细输出
pytest test_web_ui_v3.py -v --tb=long

# 只运行特定测试类
pytest test_web_ui_v3.py::TestSearch -v

# 只运行特定测试
pytest test_web_ui_v3.py::TestSearch::test_basic_search -v

# 生成 HTML 报告
pytest test_web_ui_v3.py -v --html=report.html
```

## 测试覆盖检查清单

- [x] 系统状态端点
- [x] 搜索功能（基本/过滤器/参数）
- [x] 集合管理（CRUD）
- [x] 记忆管理（CRUD）
- [x] 备份管理（创建/列出）
- [x] 错误处理
- [ ] 版本管理（待补充）
- [ ] 关联管理（待补充）
- [ ] 导出功能（待补充）
- [ ] 监控数据（待补充）

## 后续测试扩展建议

1. **版本管理测试**：测试 rollback_memory 功能
2. **关联管理测试**：测试 link/unlink_memory 功能
3. **导出功能测试**：测试 JSON/Markdown 导出
4. **监控数据测试**：验证监控日志记录
5. **集成测试**：端到端测试完整工作流
6. **性能测试**：测试大数据量下的响应时间