# Windows 路径解析问题

## 问题

在 Windows 环境下，`os.path.expanduser("~/.hermes")` 返回混合路径格式：

```python
>>> os.path.expanduser("~/.hermes")
'C:\\Users\\Nemo/.hermes'  # 注意：反斜杠和正斜杠混合
```

这导致 `os.path.exists()` 检查失败，因为路径不匹配。

## 根本原因

- `~` 展开使用 Windows 风格（反斜杠）
- 手动拼接的路径使用 Unix 风格（正斜杠）
- Windows 的 `os.path.exists()` 对混合路径敏感

## 解决方案

### 方案 A：使用 `os.path.abspath()`

```python
# 修复前
HERMES_HOME = os.path.expanduser("~/.hermes")

# 修复后
HERMES_HOME = os.path.abspath(os.path.expanduser("~/.hermes"))
```

### 方案 B：使用 `os.path.join()`

```python
from pathlib import Path

HERMES_HOME = Path.home() / '.hermes'
```

### 方案 C：基于 `__file__` 计算（最可靠）

```python
# 在 app.py 中
HERMES_HOME = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
```

## Web UI 路径修复

在 `~/.hermes/scripts/memory_web/app.py` 中：

```python
# 修复前
HERMES_HOME = os.path.expanduser("~/.hermes")

# 修复后
HERMES_HOME = os.path.abspath(os.path.expanduser("~/.hermes"))
SCRIPTS_DIR = os.path.join(HERMES_HOME, "scripts")
VECTOR_MEMORY_SCRIPTS = os.path.join(HERMES_HOME, "skills", "vector_memory", "scripts")
```

## Windows 原生 Python 路径检测

在 WSL 中运行时，`sys.executable` 指向 WSL Python，需要检测 Windows 原生 Python：

```python
import sys
import os

if sys.platform == 'win32' or 'wsl' in os.uname().release.lower() if hasattr(os, 'uname') else False:
    # 尝试常见的 Windows Python 路径
    win_python_paths = [
        r'C:\Python314\python.exe',
        r'C:\Python313\python.exe',
        r'C:\Python312\python.exe',
        r'C:\Program Files\Python314\python.exe',
        r'C:\Program Files\Python313\python.exe',
    ]
    python_exe = None
    for p in win_python_paths:
        if os.path.exists(p):
            python_exe = p
            break
    if python_exe is None:
        python_exe = sys.executable
else:
    python_exe = sys.executable
```

## 测试

```python
import os

path = os.path.expanduser("~/.hermes")
print(f"原始路径: {path}")
print(f"绝对路径: {os.path.abspath(path)}")
print(f"存在: {os.path.exists(path)}")
```
