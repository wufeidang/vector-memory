# Windows 终端工具编码问题排查

## 现象

在 Windows 主机上使用 `terminal` 工具执行命令时，输出显示为乱码：

```
\007c\u201cv\rg\u2019g\u0148\u00020 \u0000\r\u0000\n\u0000\u0019\u2026Bash/ERROR_SERVICE_DOES_NOT_EXIST\r\n
```

退出码为 1，但错误信息无法阅读。

## 根因

Windows 的 bash (git-bash / MSYS) 环境在 Hermes 容器中可能存在编码或终端模拟问题，导致 shell 输出被错误解码。

## 解决方案

1. **优先使用 `execute_code` 代替 `terminal`**：Python 脚本通过 `hermes_tools` 库调用工具，输出处理更可靠
2. **使用 `write_file` 而非 shell heredoc**：创建文件用 `write_file`，编辑用 `patch`
3. **使用 `read_file` 而非 `cat/head/tail`**：读取文件用 `read_file`
4. **使用 `search_files` 而非 `grep/find`**：搜索用 `search_files`

## 适用场景

- 需要执行 shell 命令时，先尝试 `execute_code` 中的 `terminal()` 调用
- 如果 `terminal()` 返回乱码，改用纯 Python 实现相同逻辑
- 文件操作一律使用 `read_file` / `write_file` / `patch` / `search_files`

## 备注

此问题仅影响 Windows 主机的 `terminal` 工具输出解码，不影响 `execute_code` 工具。
