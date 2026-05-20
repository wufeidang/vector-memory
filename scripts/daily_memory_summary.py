#!/usr/bin/env python3
"""
每日记忆摘要脚本 - 用于 vector_memory 技能的自动摘要功能

功能：
1. 扫描 MEMORY.md 中的记忆
2. 按主题/类别聚类（preference, project, learning, config, general）
3. 生成摘要报告
4. 保存报告到 ~/.hermes/reports/

使用方式：
- 手动运行: python ~/.hermes/scripts/daily_memory_summary.py
- 自动运行: 通过 hermes cron 调度（每天 8 点）

分类规则：
- preference: 包含"偏好"、"喜欢"、"习惯"、"风格"
- project: 包含"项目"、"任务"、"工作"、"开发"
- learning: 包含"学习"、"知识"、"教程"、"文档"
- config: 包含"配置"、"设置"、"环境"、"安装"
- general: 其他

输出格式：Markdown 报告，包含类别统计和详情
"""

import os
import json
import re
from datetime import datetime
from pathlib import Path

# 配置
MEMORY_FILE = os.path.join(os.path.expanduser('~'), '.hermes', 'memories', 'MEMORY.md')
REPORTS_DIR = os.path.join(os.path.expanduser('~'), '.hermes', 'reports')
os.makedirs(REPORTS_DIR, exist_ok=True)


def parse_memory_file(filepath):
    """解析 MEMORY.md，返回记忆列表。"""
    memories = []
    if not os.path.exists(filepath):
        return memories
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or not line.startswith('- ['):
                continue
            
            # 解析: - [timestamp] text {metadata}
            match = re.match(r'^- \[(.*?)\]\s+(.*?)(?:\s+(\{.*\}))?$', line)
            if match:
                timestamp_str, text, metadata_str = match.groups()
                try:
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                except:
                    timestamp = None
                metadata = json.loads(metadata_str) if metadata_str else {}
                memories.append({
                    'timestamp': timestamp,
                    'text': text,
                    'metadata': metadata
                })
    return memories


def categorize_memory(text, metadata):
    """简单分类：基于关键词。"""
    text_lower = text.lower()
    category = metadata.get('category', 'general')
    
    if category != 'general':
        return category
    
    # 基于关键词分类
    if any(k in text for k in ['偏好', '喜欢', '习惯', '风格']):
        return 'preference'
    elif any(k in text for k in ['项目', '任务', '工作', '开发']):
        return 'project'
    elif any(k in text for k in ['学习', '知识', '教程', '文档']):
        return 'learning'
    elif any(k in text for k in ['配置', '设置', '环境', '安装']):
        return 'config'
    else:
        return 'general'


def generate_summary(memories, days=7):
    """生成记忆摘要报告。"""
    now = datetime.now()
    cutoff = datetime(now.year, now.month, now.day)
    
    recent = []
    old = []
    
    for m in memories:
        if m['timestamp'] and m['timestamp'] >= cutoff:
            recent.append(m)
        else:
            old.append(m)
    
    # 按类别分组 - 对所有记忆分类
    categories = {}
    for m in memories:
        cat = categorize_memory(m['text'], m['metadata'])
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(m)
    
    # 生成报告
    report_lines = [
        f"# 记忆摘要报告",
        f"",
        f"**生成时间**: {now.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**统计范围**: 全部 {len(memories)} 条记忆",
        f"**今日新增**: {len(recent)} 条",
        f"**历史记忆**: {len(old)} 条",
        f"",
        f"---",
        f"",
        f"## 按类别统计",
        f"",
    ]
    
    for cat, items in sorted(categories.items(), key=lambda x: -len(x[1])):
        report_lines.append(f"- **{cat}**: {len(items)} 条")
    
    report_lines.extend([
        f"",
        f"---",
        f"",
        f"## 类别详情",
        f"",
    ])
    
    for cat, items in sorted(categories.items(), key=lambda x: -len(x[1])):
        report_lines.append(f"### {cat} ({len(items)} 条)")
        report_lines.append(f"")
        # 显示最近 5 条
        sorted_items = sorted(items, key=lambda x: x['timestamp'] or datetime.min, reverse=True)
        for m in sorted_items[:5]:
            ts = m['timestamp'].strftime('%Y-%m-%d %H:%M') if m['timestamp'] else 'unknown'
            text_preview = m['text'][:60] + '...' if len(m['text']) > 60 else m['text']
            report_lines.append(f"- [{ts}] {text_preview}")
        if len(items) > 5:
            report_lines.append(f"  ... 还有 {len(items) - 5} 条")
        report_lines.append(f"")
    
    return '\n'.join(report_lines)


def main():
    print("=== 记忆摘要脚本 ===")
    print(f"记忆文件: {MEMORY_FILE}")
    
    memories = parse_memory_file(MEMORY_FILE)
    print(f"解析到 {len(memories)} 条记忆")
    
    if not memories:
        print("无记忆可摘要")
        return
    
    report = generate_summary(memories)
    
    # 保存报告
    report_filename = f"memory_summary_{datetime.now().strftime('%Y%m%d')}.md"
    report_path = os.path.join(REPORTS_DIR, report_filename)
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"✅ 报告已保存: {report_path}")
    print(f"\n--- 报告预览 ---\n")
    print(report[:1000])
    if len(report) > 1000:
        print(f"... (共 {len(report)} 字符)")


if __name__ == '__main__':
    main()
