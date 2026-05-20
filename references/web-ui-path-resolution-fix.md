# Web UI 路径解析与端口绑定修复

## 问题 1: Windows 混合路径导致脚本找不到

### 症状

Web UI 搜索记忆时报错：
```
搜索失败: 脚本不存在: vector_memory.py
```

### 根因

`os.path.expanduser("~/.hermes")` 在 Windows 上返回混合路径格式：
```
C:\Users\Nemo/.hermes  # 反斜杠 + 正斜杠混合
```

这导致 `os.path.exists()` 检查失败。

### 修复

```python
# 修复前
HERMES_HOME = os.path.expanduser("~/.hermes")

# 修复后
HERMES_HOME = os.path.abspath(os.path.expanduser("~/.hermes"))
```

### 调试技巧

```python
import os

hermes = os.path.expanduser("~/.hermes")
print(f"路径: {hermes!r}")
print(f"类型: {type(hermes)}")
print(f"存在: {os.path.exists(hermes)}")

# 检查 vector_memory.py
vm_path = os.path.join(hermes, "skills", "vector_memory", "scripts", "vector_memory.py")
print(f"vm_path: {vm_path!r}")
print(f"存在: {os.path.exists(vm_path)}")

# 使用绝对路径
abs_path = os.path.abspath(vm_path)
print(f"abs_path: {abs_path!r}")
print(f"存在: {os.path.exists(abs_path)}")
```

---

## 问题 2: Flask WSL 端口绑定不可访问

### 症状

Flask Web UI 启动后，Windows 浏览器无法访问 `http://localhost:5000`：
```
HTTPConnectionPool(host='localhost', port=5000): Max retries exceeded
[WinError 10061] 由于目标计算机积极拒绝，无法连接。
```

### 根因

通过 WSL (`bash.EXE`) 启动的 Flask 服务器，端口绑定在 WSL 内部网络，Windows 的 `localhost` 无法访问。

### 诊断

```python
import socket
import psutil

# 检查端口是否被占用
def check_port(port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    result = sock.connect_ex(('127.0.0.1', port))
    sock.close()
    return result == 0

print(f"端口 5000 是否被占用: {check_port(5000)}")

# 查找占用端口的进程
for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
    try:
        for conn in proc.connections():
            if conn.laddr.port == 5000:
                print(f"占用 5000 端口的进程: PID {proc.pid}, {proc.info['name']}, {proc.info['cmdline']}")
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
```

### 解决方案

1. **终止旧进程**：
```python
import psutil

for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
    try:
        for conn in proc.connections():
            if conn.laddr.port == 5000:
                proc.terminate()
                print(f"终止 PID {proc.pid}")
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
```

2. **Windows 原生启动**（不要通过 WSL）：
```cmd
cd C:\Users\Nemo\.hermes\scripts\memory_web
python app.py
```

3. **验证**：启动后检查端口是否被 Windows 原生 Python 占用。

---

## 问题 3: vector_memory.py 缺少命令行入口

### 症状

```
$ python vector_memory.py search 优化
(无输出，直接返回)
```

### 根因

脚本缺少 `if __name__ == '__main__':` 入口。

### 修复

添加以下代码到脚本末尾：

```python
if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python vector_memory.py <command> [args]")
        print("命令: search, list, add, create, backup, restore, stats")
        sys.exit(1)
    
    command = sys.argv[1]
    
    # 解析参数
    args = {}
    for arg in sys.argv[2:]:
        if '=' in arg:
            k, v = arg.split('=', 1)
            args[k] = v
        else:
            if 'text' not in args:
                args['text'] = arg
    
    # 执行命令
    if command == 'search':
        result = search_memories(args)
    elif command == 'list':
        result = list_memories(args)
    elif command == 'add':
        result = add_memory(args)
    elif command == 'create':
        result = create_collection(args)
    elif command == 'backup':
        result = backup_memory(args)
    elif command == 'restore':
        result = restore_memory(args)
    elif command == 'stats':
        result = get_stats(args)
    else:
        result = {"success": False, "message": f"未知命令: {command}"}
    
    # 输出结果
    if result.get('success'):
        if 'results' in result:
            for r in result['results']:
                text = r.get('text', '')[:200]
                score = r.get('score', r.get('distance', 'N/A'))
                print(f"[{score:.4f}] {text}")
        elif 'message' in result:
            print(result['message'])
        elif 'count' in result:
            print(f"共 {result['count']} 条记录")
        else:
            print("操作成功")
    else:
        print(f"失败: {result.get('message', result.get('error', '未知错误'))}")
        sys.exit(1)
```

### 验证

```
$ python vector_memory.py search 优化
[0.2570] Vector-Memory 10 项优化全部完成...
[0.0580] 无线网桥部署：视距计算...
[0.0040] iVMS-4200 客户端配置...
```

---

## 问题 4: WSL 中 sys.executable 指向错误 Python

### 症状

Flask `app.py` 的 `run_script()` 使用 `sys.executable` 调用 `vector_memory.py`，但 WSL 中 `sys.executable` 指向 WSL 内部的 Python（如 `/usr/bin/python3`），无法执行 Windows 路径的脚本。

### 根因

Hermes 的 `terminal` 工具在 Windows 上运行于 git-bash/WSL。`subprocess.Popen([r'C:\Python314\python.exe', ...])` 从 `execute_code`（沙箱 Python）调用可以正常工作，但 `app.py` 中的 `subprocess.run([sys.executable, ...])` 在 WSL 环境下会失败。

### 修复

在 `run_script()` 中添加 Windows 原生 Python 路径检测：

```python
def run_script(script_name, args=None):
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    if not os.path.exists(script_path) and script_name == 'vector_memory.py':
        script_path = os.path.join(VECTOR_MEMORY_SCRIPTS, script_name)
    if not os.path.exists(script_path):
        return {"success": False, "error": "脚本不存在: " + script_name}
    
    # Windows 原生 Python 路径检测
    if sys.platform == 'win32' or ('wsl' in os.uname().release.lower() if hasattr(os, 'uname') else False):
        win_python_paths = [
            r'C:\Python314\python.exe',
            r'C:\Python313\python.exe',
            r'C:\Python312\python.exe',
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
    
    cmd = [python_exe, script_path] + (args or [])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return {"success": result.returncode == 0, "stdout": result.stdout, "stderr": result.stderr}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

### 关键教训

- Hermes Agent 自身通过 `execute_code` 启动 Flask 时，必须用 Windows 原生 Python 路径（`C:\Python314\python.exe`），不能用 `terminal` 工具
- `app.py` 内部的 `run_script()` 也要做同样的检测，因为用户可能从 WSL 终端手动启动
- 启动前必须用 `psutil` 清理占用目标端口的旧进程
