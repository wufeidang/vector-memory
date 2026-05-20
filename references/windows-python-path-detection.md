# Windows Python 路径检测模式

## 问题

在 WSL 环境中启动 Flask Web UI，`sys.executable` 指向 WSL Python，导致子进程无法找到正确的 Python 解释器。

## 症状

```
FileNotFoundError: [Errno 2] No such file or directory: '/usr/bin/python3'
```

或端口绑定成功但 Windows 浏览器无法访问（WSL 的 localhost 与 Windows 的 localhost 不互通）。

## 原因

WSL 和 Windows 是两个独立的操作系统环境：
- WSL 的 `/usr/bin/python3` 在 Windows 中不存在
- WSL 绑定的端口（如 5000）在 Windows 浏览器中不可访问

## 解决方案

### 检测 Windows 原生 Python

```python
import sys
import os

def get_windows_python():
    """获取 Windows 原生 Python 路径。"""
    # 常见 Windows Python 安装路径
    possible_paths = [
        r'C:\Python314\python.exe',
        r'C:\Python313\python.exe',
        r'C:\Python312\python.exe',
        r'C:\Program Files\Python314\python.exe',
        r'C:\Program Files\Python313\python.exe',
        r'C:\Program Files\Python312\python.exe',
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    # 尝试从注册表获取（需要 winreg）
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Python\PythonCore')
        # 解析注册表获取安装路径
        # ... (略)
    except ImportError:
        pass
    
    return None

# 使用示例
windows_python = get_windows_python()
if windows_python:
    print(f"使用 Windows Python: {windows_python}")
    # 启动子进程时使用 Windows Python
    subprocess.run([windows_python, 'script.py'])
```

### WSL 中访问 Windows 服务

如果必须在 WSL 中启动服务，需要：

1. **绑定到 0.0.0.0**（而非 127.0.0.1）
   ```python
   app.run(host='0.0.0.0', port=5000)
   ```

2. **通过 WSL 网关访问**
   ```bash
   # WSL 中访问 Windows 服务
   curl http://host.docker.internal:5000
   
   # 或
   curl http://172.x.x.x:5000  # WSL 虚拟网络 IP
   ```

3. **端口转发**
   ```bash
   # 在 WSL 中转发端口
   sudo iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 5000
   ```

## 最佳实践

1. **优先使用 Windows 原生 Python**：对于需要访问 Windows 文件系统的脚本
2. **WSL 用于开发，Windows 用于部署**：开发时使用 WSL 的 Linux 工具链，部署时使用 Windows 原生环境
3. **统一使用 `hermes` 命令**：通过 Hermes CLI 启动，自动处理环境差异

## 相关文件

- `scripts/memory_web/app.py` → Web UI Flask 应用
- `gateway-service/Hermes_Gateway.cmd` → Hermes 启动脚本