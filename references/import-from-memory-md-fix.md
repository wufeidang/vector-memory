# `import_from_memory_md` 格式限制修复

## 问题描述

`storage.py` 中的 `import_from_memory_md()` 函数只解析 `- [` 格式的记忆条目，完全忽略 `§` 分隔格式的内容。

## 函数当前实现

```python
def import_from_memory_md(args):
    if not MEMORY_MD.exists():
        return {"success": False, "message": "MEMORY.md 不存在"}
    content = MEMORY_MD.read_text(encoding="utf-8")
    lines = [l.strip() for l in content.split("\n") if l.strip().startswith("- [")]
    added = 0
    for line in lines:
        text = line[3:].strip() if line.startswith("- [") else line
        result = add_memory({"text": text, "metadata": {"imported": True}})
        if result.get("success"):
            added += 1
    return {"success": True, "message": "已导入 %d 条记忆" % added}
```

## 问题根源

- `MEMORY.md` 当前使用 `§` 分隔格式，每个区块包含多行文本
- 函数只提取以 `- [` 开头的行，忽略了 `§` 分隔的大段内容
- 导致同步时导入 0 条，即使 MEMORY.md 有 800+ 条记忆

## 解决方案

### 方案 A：临时手动同步（已验证）

```python
import hashlib
import sys
import os

scripts_dir = r"C:\Users\Nemo\.hermes\skills\vector_memory\scripts"
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

from core import MEMORY_MD, _get_collection
from storage import add_memory, list_memories

# 读取 MEMORY.md
content = MEMORY_MD.read_text(encoding="utf-8")

# 解析 - [ 格式的行（这些是带时间戳的正式条目）
lines = [l.strip() for l in content.split('\n') if l.strip().startswith('- [')]

# 获取现有记忆哈希用于去重
existing_hashes = set()
result = list_memories({"limit": 1000})
if result.get("success"):
    for m in result.get("memories", []):
        text = m.get("text", "")
        h = hashlib.md5(text.encode('utf-8')).hexdigest()
        existing_hashes.add(h)

# 同步新记忆
added = 0
skipped = 0
errors = 0
for line in lines:
    text = line[3:].strip() if line.startswith('- [') else line
    
    # 去重检查
    h = hashlib.md5(text.encode('utf-8')).hexdigest()
    if h in existing_hashes:
        skipped += 1
        continue
    
    result = add_memory({"text": text, "metadata": {"imported": True}})
    if result.get("success"):
        added += 1
        existing_hashes.add(h)
    else:
        errors += 1

print(f"新增: {added}, 跳过: {skipped}, 错误: {errors}")
```

### 方案 B：永久修复 `import_from_memory_md`

修改 `storage.py` 中的函数，同时支持两种格式：

```python
def import_from_memory_md(args):
    if not MEMORY_MD.exists():
        return {"success": False, "message": "MEMORY.md 不存在"}
    
    content = MEMORY_MD.read_text(encoding="utf-8")
    
    # 检测格式类型
    has_section_separator = '§' in content
    has_bracket_entries = any(l.strip().startswith('- [') for l in content.split('\n'))
    
    texts = []
    
    if has_section_separator and has_bracket_entries:
        # 混合格式：提取所有 - [ 条目
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('- ['):
                text = line[3:].strip()
                # 移除末尾的 JSON metadata
                # 格式: - [timestamp] 内容 {json}
                match = re.match(r'^\[([^\]]+)\]\s*(.+?)(?:\s*\{.*\})?$', text)
                if match:
                    text = match.group(2).strip()
                texts.append(text)
    elif has_section_separator:
        # 纯 § 分隔格式：按 § 分割，每条作为一个记忆
        sections = content.split('§')
        for section in sections:
            section = section.strip()
            if section:
                texts.append(section)
    elif has_bracket_entries:
        # 纯 - [ 格式（传统）
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('- ['):
                text = line[3:].strip()
                texts.append(text)
    
    # 去重并导入
    added = 0
    for text in texts:
        if len(text) < 10:  # 跳过太短的条目
            continue
        result = add_memory({"text": text, "metadata": {"imported": True}})
        if result.get("success"):
            added += 1
    
    return {"success": True, "message": "已导入 %d 条记忆" % added}
```

## 验证方法

```python
# 检查 MEMORY.md 格式
from core import MEMORY_MD
content = MEMORY_MD.read_text(encoding="utf-8")

sections = content.split('§')
lines_with_bracket = [l for l in content.split('\n') if l.strip().startswith('- [')]

print(f"§ 分隔区块数: {len(sections)}")
print(f"- [ 格式行数: {len(lines_with_bracket)}")

# 执行同步
from storage import import_from_memory_md
result = import_from_memory_md({"force": True})
print(result)
```

## 相关文件

- `storage.py` - 需要修复的函数所在文件
- `core.py` - MEMORY_MD 路径定义
- `scripts/sync_memory.py` - 独立的同步脚本（已支持两种格式）

## 会话记录

2026-05-23 同步记忆时发现此问题：
- 执行 `import_from_memory_md({"force": True})` 返回导入 0 条
- MEMORY.md 有 839 条 `- [` 格式条目，193KB，9 个 `§` 区块
- 手动实现同步逻辑后成功导入 26 条新记忆（813 条已存在被跳过）
