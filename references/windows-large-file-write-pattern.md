# Windows 大文件写入模式

## 问题

在 Windows 环境下，Hermes 的 `write_file` 工具写入大文件（>10KB）时可能超时失败，返回 `BASH_ERROR_SERVICE_DOES_NOT_EXIST` 错误。

## 解决方案

使用 `execute_code` 中的 Python `open()` 函数写入文件，稳定可靠。

### 推荐模式

```python
import os

# 确保目录存在
os.makedirs(os.path.dirname(path), exist_ok=True)

# 写入文件
with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"✅ 文件已写入: {path} ({len(content)} 字符)")
```

### 对比

| 方法 | 适用场景 | 稳定性 |
|------|----------|--------|
| `write_file` 工具 | 小文件（<10KB） | ⚠️ 大文件可能超时 |
| `execute_code` + `open()` | 任意大小文件 | ✅ 稳定可靠 |

### 示例：写入 20KB HTML 文章

```python
import os

article_path = r"C:\Users\Nemo\Desktop\work\monitor-tutorial-series\articles\article-08.html"
os.makedirs(os.path.dirname(article_path), exist_ok=True)

with open(article_path, 'w', encoding='utf-8') as f:
    f.write(html_content)  # 20KB+ 内容

print(f"✅ 文章已写入 ({len(html_content)} 字符)")
```

## 注意事项

1. **编码**：始终使用 `encoding='utf-8'`，避免中文乱码
2. **目录**：先 `os.makedirs(..., exist_ok=True)` 确保父目录存在
3. **路径**：Windows 上使用原始字符串 `r"..."` 避免转义问题
4. **验证**：写入后建议读取验证，或检查文件大小
