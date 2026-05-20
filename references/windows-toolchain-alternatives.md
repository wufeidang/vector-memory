# Windows 环境下工具链替代方案

## 问题背景

在 Windows 上使用 Hermes Agent 时，`terminal` 工具通过 git-bash (MSYS2) 执行命令，存在以下问题：

1. **编码问题**：输出中可能出现 null bytes (`\x00`)、乱码
2. **ripgrep 缺失**：`search_files` 工具依赖的 ripgrep 可能未安装
3. **pip 安装超时**：网络问题导致 pip 安装超时

## 解决方案

### 1. ripgrep 替代方案

当 `search_files` 或 `rg` 不可用时，使用 Python 版替代脚本：

**脚本位置**: `~/.hermes/scripts/rg.py`

**使用方法**:
```bash
# 搜索文件内容
python ~/.hermes/scripts/rg.py "关键词" /path/to/search -n

# 只列出匹配文件
python ~/.hermes/scripts/rg.py "关键词" /path/to/search --files

# 计数模式
python ~/.hermes/scripts/rg.py "关键词" /path/to/search -c

# 按文件类型过滤
python ~/.hermes/scripts/rg.py "import" . -g "*.py"
```

**支持的参数**:
| 参数 | 说明 |
|------|------|
| `-n` | 显示行号（默认） |
| `--no-line-numbers` | 不显示行号 |
| `-c` | 只输出匹配数量 |
| `-l` | 只输出文件名 |
| `-i` | 忽略大小写 |
| `--case-sensitive` | 区分大小写 |
| `-C <n>` | 显示 n 行上下文 |
| `-g <pattern>` | 文件模式过滤 |
| `--files` | 列出所有匹配文件 |

### 2. 编码安全命令执行器

**脚本位置**: `~/.hermes/scripts/safe_terminal.py`

**用途**: 解决 terminal 工具的编码问题

**使用方法**:
```bash
# 执行命令（自动处理编码）
python ~/.hermes/scripts/safe_terminal.py "echo 测试中文"

# 指定工作目录
python ~/.hermes/scripts/safe_terminal.py "dir /b" -d "C:\Users\Nemo\.hermes"

# 自定义超时
python ~/.hermes/scripts/safe_terminal.py "long_command" -t 120
```

### 3. 最佳实践

| 场景 | 推荐方案 |
|------|----------|
| 文件搜索 | `execute_code` + Python `os.walk()` 或 `rg.py` |
| 内容搜索 | `execute_code` + Python `open().read()` |
| 系统命令 | `safe_terminal.py` 或 `execute_code` + `subprocess` |
| 文件读写 | `execute_code` + Python `open()` |
| 配置解析 | `execute_code` + Python `yaml.safe_load()` |

### 4. 示例：搜索记忆文件

```python
# 使用 execute_code 替代 terminal
from hermes_tools import execute_code

code = '''
import os
import re

def search_memories(query, path="~/.hermes/memories"):
    path = os.path.expanduser(path)
    results = []
    for root, dirs, files in os.walk(path):
        for f in files:
            if f.endswith(".md"):
                fpath = os.path.join(root, f)
                try:
                    with open(fpath, "r", encoding="utf-8") as fh:
                        content = fh.read()
                        if re.search(query, content, re.IGNORECASE):
                            results.append(fpath)
                except:
                    pass
    return results

print(search_memories("消防"))
'''

result = execute_code(code)
print(result)
```

## 注意事项

1. **不要声称工具永久损坏**：问题可能是环境配置问题，可通过替代方案解决
2. **优先使用 execute_code**：Python 环境更稳定，编码处理更好
3. **绝对路径**：Windows 上使用绝对路径（如 `C:\Users\Nemo\.hermes\...`）
4. **编码参数**：Python 文件操作时显式指定 `encoding="utf-8"`

## 测试验证

```bash
# 测试 rg.py
python ~/.hermes/scripts/rg.py "Nemo" ~/.hermes/memories -n

# 测试 safe_terminal.py
python ~/.hermes/scripts/safe_terminal.py "echo 测试编码"

# 验证备份功能
python ~/.hermes/skills/vector_memory/scripts/backup_memory.py create
```