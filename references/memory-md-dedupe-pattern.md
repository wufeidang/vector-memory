# MEMORY.md 文本去重模式

## 问题背景

`storage.py` 中的 `dedupe_memories()` 函数**仅对 ChromaDB 向量数据库进行去重**，对 `~/.hermes/memories/MEMORY.md` 文本文件**完全无效**。

## 症状

```
✅ 向量库去重完成
   去重前: 563 条
   去重后: 563 条
   删除: 0 条

❌ 但 MEMORY.md 文件仍有严重重复：
   总条目: 890 条
   唯一条目: 54 条
   重复条目: 836 条（94% 重复率）
```

## 根本原因

- `dedupe_memories()` 使用 ChromaDB 的 `query` API 查找相似记录
- MEMORY.md 是纯文本文件，不受向量数据库操作影响
- 两个存储系统相互独立，去重操作不会跨系统同步

## MEMORY.md 重复模式

### 周期性重复

约 13 条条目块被重复复制约 68 次。典型重复块：

```
[2026-05-19 完成：Vector-Memory 记忆系统 10 项优化全部完成]
[2026-05-20 进度快照：监控教程系列 7/12 完成...]
[2026-05-20 更新：消防系列第02期文章已完成...]
[2026-05-20 技能更新：已更新 wechat-article-expert...]
[2026-05-20 更新：Vector-Memory 模型预加载优化完成...]
[Token 日报系统已搭建...]
[2026-05-21 监控第08期完成...]
[测试记忆 v3]
[2026-05-21 更新：Vector-Memory Web UI v3.0 专业级重构完成...]
...
```

### 重复率统计

| 指标 | 数值 |
|------|------|
| 总条目数 | 890 |
| 唯一条目数 | 54 |
| 重复条目数 | 836 |
| 重复率 | 94% |

## 解决方案

### 方案 A：手动去重（推荐）

1. 备份 MEMORY.md
2. 使用文本编辑器打开
3. 手动删除重复条目
4. 同步到向量数据库

### 方案 B：脚本去重

```python
import hashlib
from pathlib import Path

MEMORY_MD = Path.home() / ".hermes" / "memories" / "MEMORY.md"

def dedupe_memory_md():
    """对 MEMORY.md 进行文本去重"""
    content = MEMORY_MD.read_text(encoding="utf-8")
    lines = content.strip().split('\n')
    
    seen = set()
    unique_lines = []
    duplicates = 0
    
    for line in lines:
        # 跳过空行和分隔符
        if not line.strip() or line.strip() == '§':
            continue
        
        # 使用 MD5 哈希检测重复
        line_hash = hashlib.md5(line.strip().encode('utf-8')).hexdigest()
        if line_hash not in seen:
            seen.add(line_hash)
            unique_lines.append(line)
        else:
            duplicates += 1
    
    # 写入去重后的文件
    MEMORY_MD.write_text('\n§\n'.join(unique_lines) + '\n', encoding='utf-8')
    print(f"去重完成: {duplicates} 条重复被删除，剩余 {len(unique_lines)} 条唯一记录")
    return duplicates, len(unique_lines)
```

### 方案 C：迁移策略

将详细记录迁移到 Vector-Memory，原生记忆仅保留关键摘要：

```
Hermes 原生记忆（MEMORY.md）：
- 用户偏好（10-20 条）
- 当前项目状态摘要
- 关键配置信息

Vector-Memory（ChromaDB）：
- 故障记录（几百条）
- SOP 文档（几十条）
- 巡检日志（几百条）
- 技术参数（几十条）
```

## 操作流程

### 去重前准备

```bash
# 1. 备份原文件
cp ~/.hermes/memories/MEMORY.md ~/.hermes/memories/MEMORY.md.backup.$(date +%Y%m%d_%H%M%S)

# 2. 检查当前状态
python -c "
from pathlib import Path
content = Path.home() / '.hermes' / 'memories' / 'MEMORY.md'
lines = [l for l in content.read_text().split('\n') if l.strip() and l.strip() != '§']
print(f'总条目: {len(lines)}')
print(f'唯一条目: {len(set(lines))}')
print(f'重复条目: {len(lines) - len(set(lines))}')
"
```

### 执行去重

```bash
python -c "
import hashlib
from pathlib import Path

MEMORY_MD = Path.home() / '.hermes' / 'memories' / 'MEMORY.md'
content = MEMORY_MD.read_text(encoding='utf-8')
lines = content.strip().split('\n')

seen = set()
unique_lines = []
duplicates = 0

for line in lines:
    if not line.strip() or line.strip() == '§':
        continue
    line_hash = hashlib.md5(line.strip().encode('utf-8')).hexdigest()
    if line_hash not in seen:
        seen.add(line_hash)
        unique_lines.append(line)
    else:
        duplicates += 1

MEMORY_MD.write_text('\n§\n'.join(unique_lines) + '\n', encoding='utf-8')
print(f'✅ 去重完成: {duplicates} 条重复被删除，剩余 {len(unique_lines)} 条唯一记录')
"
```

### 去重后同步

```bash
# 将去重后的 MEMORY.md 同步到向量数据库
python ~/.hermes/scripts/vector_memory.py import --memory-md
```

## 验证

```bash
# 检查去重效果
python -c "
from pathlib import Path
content = Path.home() / '.hermes' / 'memories' / 'MEMORY.md'
lines = [l for l in content.read_text().split('\n') if l.strip() and l.strip() != '§']
print(f'去重后总条目: {len(lines)}')
print(f'去重后唯一条目: {len(set(lines))}')
print(f'重复率: {(len(lines) - len(set(lines))) / len(lines) * 100:.1f}%')
"
```

## 预防措施

1. **定期清理**：每周检查 MEMORY.md 重复情况
2. **及时同步**：添加记忆后及时同步到向量数据库
3. **精简原生记忆**：原生记忆仅保留关键信息，详细记录存入 Vector-Memory
4. **使用 § 分隔**：保持 § 分隔格式，便于解析和去重

## 相关文件

- `~/.hermes/memories/MEMORY.md` - 文本记忆文件
- `~/.hermes/vector_store/` - ChromaDB 向量数据库
- `~/.hermes/skills/vector_memory/scripts/storage.py` - dedupe_memories() 函数
- `~/.hermes/skills/vector_memory/scripts/sync_memory_reliable.py` - 可靠同步脚本