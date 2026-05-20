# 自动化备份与性能监控配置指南

## 概述

本指南介绍如何为记忆系统配置自动化备份和性能监控。

## 备份系统

### 脚本位置

```
~/.hermes/skills/vector_memory/scripts/backup_memory.py
```

### 使用方法

```bash
# 创建备份
python ~/.hermes/skills/vector_memory/scripts/backup_memory.py create

# 列出备份
python ~/.hermes/skills/vector_memory/scripts/backup_memory.py list

# 恢复备份
python ~/.hermes/skills/vector_memory/scripts/backup_memory.py restore --backup backup_20260520_193048
```

### 备份内容

| 项目 | 路径 |
|------|------|
| 记忆文件 | `memories/MEMORY.md`, `memories/USER.md`, `config.yaml` |
| 技能目录 | `skills/vector_memory`, `skills/writing` |
| 向量存储 | `vector_store/` |
| 脚本目录 | `scripts/` |

### 自动清理

备份脚本自动保留最近 **7 个** 备份，超出部分自动清理。

## Cron 定时任务

### Linux/Mac

```bash
# 编辑 crontab
crontab -e

# 添加每日凌晨2点备份
0 2 * * * /bin/bash ~/.hermes/scripts/cron_backup.sh
```

### Windows

使用任务计划程序：
1. 打开"任务计划程序"
2. 创建基本任务：
   - 名称: `Hermes 每日备份`
   - 触发器: 每天，凌晨 2:00
   - 操作: 启动程序
     - 程序: `C:\Windows\System32\cmd.exe`
     - 参数: `/c C:\Users\Nemo\.hermes\scripts\cron_backup.bat`
     - 起始于: `C:\Users\Nemo\.hermes`

## 性能监控

### 脚本位置

```
~/.hermes/skills/vector_memory/scripts/memory_monitor.py
~/.hermes/skills/vector_memory/scripts/generate_report.py
```

### 记录搜索性能

```python
from scripts.memory_monitor import record_search

# 在搜索操作后记录
record_search(
    query="消防泵房",
    results_count=5,
    elapsed_ms=123.45,
    source="vector_memory"
)
```

### 生成报告

```bash
# 日报
python ~/.hermes/skills/vector_memory/scripts/generate_report.py daily

# 周报
python ~/.hermes/skills/vector_memory/scripts/generate_report.py weekly

# 月报
python ~/.hermes/skills/vector_memory/scripts/generate_report.py monthly

# JSON 格式输出
python ~/.hermes/skills/vector_memory/scripts/generate_report.py daily --json
```

### 性能评级标准

| 平均耗时 | 评级 |
|----------|------|
| < 100ms | 优秀 |
| 100-300ms | 良好 |
| 300-500ms | 一般 |
| > 500ms | 需优化 |

## 数据目录

```
~/.hermes/
├── backups/              # 备份存储
│   └── backup_YYYYMMDD_HHMMSS/
│       ├── manifest.json
│       └── ...
├── monitor_data/         # 性能监控数据
│   └── performance_log.json
└── reports/              # 性能报告
    └── performance_report_YYYYMMDD_HHMMSS.json
```