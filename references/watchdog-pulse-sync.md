# Watchdog 事件驱动脉冲同步

## 问题背景

旧版 `watch_memory_md()` 使用 5 秒轮询检查 `MEMORY.md` 文件大小和 mtime：
- CPU 持续占用（即使文件无变化）
- 响应延迟高达 5 秒
- 多线程 daemon 模式，停止时可能丢失事件

## 解决方案

使用 `watchdog` 库的事件驱动机制，实时响应文件修改。

### 安装

```bash
pip install watchdog
```

### 核心代码

```python
import os
import time
import threading
import json
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

_watch_running = False
_watch_observer = None
_watch_event_handler = None

def watch_memory_md(interval=None, callback=None):
    """实时监控 MEMORY.md 文件变化，自动增量导入（watchdog 事件驱动）。"""
    global _watch_running, _watch_observer, _watch_event_handler
    
    if _watch_running:
        return {"success": False, "message": "监控已在运行中"}
    
    mem_md = os.path.expanduser('~/.hermes/memories/MEMORY.md')
    if not os.path.exists(mem_md):
        return {"success": False, "message": "MEMORY.md 不存在"}
    
    # 记录已导入的行号集合
    imported_lines = set()
    coll = _get_client()
    existing = coll.get(include=['metadatas'])
    for meta in existing.get('metadatas', []):
        if 'memory_md_line' in meta:
            imported_lines.add(str(meta['memory_md_line']))
    
    class MemoryMdHandler(FileSystemEventHandler):
        """处理 MEMORY.md 文件修改事件的处理器。"""
        
        def __init__(self, mem_path, imported_set, callback_fn):
            self.mem_path = mem_path
            self.imported_set = imported_set
            self.callback_fn = callback_fn
            self._pending_import = False
            self._lock = threading.Lock()
        
        def on_modified(self, event):
            """文件修改事件触发。"""
            if event.is_directory:
                return
            if os.path.abspath(event.src_path) != os.path.abspath(self.mem_path):
                return
            
            with self._lock:
                if self._pending_import:
                    return  # 已有待处理任务，跳过本次
                self._pending_import = True
            
            # 延迟一小段时间等待写入完成（避免写入中途被读取）
            time.sleep(0.3)
            
            try:
                added = self._process_file()
                if self.callback_fn:
                    self.callback_fn(added=added, error=None)
            except Exception as e:
                if self.callback_fn:
                    self.callback_fn(added=0, error=str(e))
            finally:
                with self._lock:
                    self._pending_import = False
        
        def _process_file(self):
            """处理文件内容，导入新增行。"""
            with open(self.mem_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            added = 0
            for i, line in enumerate(lines):
                line = line.strip()
                if not line or not line.startswith('- ['):
                    continue
                
                line_id = str(i)
                if line_id in self.imported_set:
                    continue
                
                text, metadata = _parse_memory_line(line)
                if text:
                    meta = metadata or {}
                    meta['memory_md_line'] = line_id
                    meta['watch_imported'] = True
                    meta['watch_timestamp'] = time.strftime('%Y-%m-%d %H:%M:%S')
                    meta['watch_method'] = 'watchdog_event'
                    add_memory({'text': text, 'metadata': meta})
                    self.imported_set.add(line_id)
                    added += 1
            
            return added
    
    # 启动 watchdog 观察者
    _watch_running = True
    event_handler = MemoryMdHandler(mem_md, imported_lines, callback)
    observer = Observer()
    observer.schedule(event_handler, path=os.path.dirname(mem_md), recursive=False)
    observer.start()
    
    _watch_observer = observer
    _watch_event_handler = event_handler
    
    return {
        "success": True,
        "message": "watchdog 实时监控已启动（事件驱动，实时响应）",
        "method": "watchdog",
        "watching_file": mem_md
    }

def stop_watch():
    """停止 watchdog 监控。"""
    global _watch_running, _watch_observer, _watch_event_handler
    
    if _watch_observer is not None:
        _watch_observer.stop()
        _watch_observer.join(timeout=5)
        _watch_observer = None
    
    _watch_running = False
    _watch_event_handler = None
    
    return {"success": True, "message": "watchdog 监控已停止"}

def watch_status():
    """查询 watchdog 监控状态。"""
    global _watch_running, _watch_observer
    
    observer_alive = _watch_observer is not None and _watch_observer.is_alive()
    
    return {
        "success": True,
        "watching": _watch_running,
        "observer_alive": observer_alive,
        "method": "watchdog" if _watch_running else "none"
    }
```

## 注意事项

1. **必须导入 `threading`**：`threading.Lock()` 用于防止重复处理并发事件
2. **防抖机制**：`_pending_import` 标志位防止同一事件触发多次处理
3. **写入延迟**：`time.sleep(0.3)` 等待编辑器写入完成，避免读取不完整内容
4. **跨平台兼容性**：`watchdog` 在 Windows/macOS/Linux 均工作正常
5. **回调函数**：`callback(added=added, error=None)` 用于通知外部处理结果

## 性能对比

| 指标 | 旧版轮询 | 新版 watchdog |
|------|----------|---------------|
| 响应延迟 | 0-5 秒 | < 0.5 秒 |
| CPU 占用 | 持续轮询 | 事件触发，空闲零占用 |
| 事件丢失风险 | 低（轮询覆盖） | 极低（系统事件） |
| 依赖 | 无 | `watchdog >= 6.0.0` |

## 测试验证

```python
import vector_memory as vm

# 启动监控
result = vm.watch_memory_md(callback=lambda added=None, error=None: print(f"回调: added={added}"))

# 写入测试内容
with open(mem_file, 'a') as f:
    f.write("- [2026-05-19 12:00:00] 测试记忆: 这是测试内容\n")

# 等待处理
time.sleep(2)

# 检查导入结果
list_result = vm.list_memories({'limit': 10})

# 停止监控
vm.stop_watch()
```

## 相关文件

- `scripts/vector_memory.py` — 主实现文件
- `~/.hermes/memories/MEMORY.md` — 监控目标文件
- `~/.hermes/vector_store/` — ChromaDB 向量库