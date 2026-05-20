# opt-10: 记忆导出/备份功能

## 功能目标

提供记忆数据的完整备份和增量备份功能，支持 JSON 和 Markdown 两种格式导出。

## 实现方案

### 1. 完整备份（JSON 格式）

导出所有集合的全部记忆数据：

```python
export_memories({"format": "json", "output_dir": "~/.hermes/backups"})
# → {"success": True, "output_path": "...", "count": N}
```

### 2. Markdown 导出

生成人类可读的 Markdown 格式文档：

```python
export_memories({"format": "markdown", "output_dir": "~/.hermes/exports"})
# → {"success": True, "output_path": "...", "count": N}
```

### 3. 按集合筛选导出

```python
export_memories({"format": "json", "filter_collection": "monitor"})
export_memories({"format": "json", "filter_category": "监控维修"})
```

### 4. 备份管理

```python
backup_memories({"include_vector_store": True, "include_exports": False})
# → {"success": True, "backup_dir": "...", "manifest": {...}}

list_backups()
# → {"success": True, "backups": [...], "count": N}

restore_memories({"backup_dir": "...", "dry_run": True})
# → {"success": True, "message": "...", "dry_run": True}
```

## 文件结构

```
~/.hermes/
├── exports/                    # 导出文件
│   ├── memory_export_20260519_230000.json
│   ├── memory_export_20260519_230500.md
│   └── relations_export_*.json
├── backups/                    # 备份目录
│   └── backup_20260519_231000/
│       ├── vector_store/       # 完整向量库备份
│       ├── memories/           # MEMORY.md 备份
│       ├── version_history.json
│       └── relations.json
└── vector_store/               # 原始数据
    ├── memories/               # ChromaDB
    ├── relations.json
    └── version_history.json
```

## 测试验证

| 测试项 | 结果 |
|--------|------|
| 导出 JSON（全部记忆） | ✅ 文件可读取，格式正确 |
| 导出 Markdown | ✅ 格式美观，按集合分类 |
| 筛选导出（按 category） | ✅ 正确过滤 |
| 列出导出文件 | ✅ 包含时间戳 |
| 完整备份（含 vector_store） | ✅ 目录结构完整 |
| 列出备份 | ✅ 包含 manifest |
| 恢复备份（干跑模式） | ✅ 预览正确 |

## 注意事项

1. **备份目录权限**：确保 `~/.hermes/backups/` 目录存在且可写
2. **备份大小**：完整备份包含整个向量库，可能较大（几十 MB）
3. **恢复风险**：恢复操作会覆盖现有数据，建议先干跑验证
4. **时间戳格式**：使用 `YYYYMMDD_HHMMSS` 格式，便于排序和管理