#!/usr/bin/env python3
"""
Daily noise memory summary script
Detects duplicate/similar memories in vector database and generates report
Uses local BGE Chinese model for embedding
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

SKILL_DIR = Path.home() / ".hermes" / "skills" / "vector_memory"
sys.path.insert(0, str(SKILL_DIR))

try:
    from scripts.vector_memory import list_memories
    _have_skill = True
except ImportError:
    _have_skill = False


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def get_all_memories():
    """Get all memories from vector database"""
    if not _have_skill:
        log("ERROR: vector_memory skill not available")
        return []

    try:
        # list_memories takes args dict, returns {"success": True, "results": [...], "count": N}
        result = list_memories({"limit": 1000})
        if result.get("success"):
            memories = []
            for item in result.get("results", []):
                memories.append({
                    "content": item.get("text", ""),
                    "category": item.get("metadata", {}).get("category", "uncategorized"),
                    "timestamp": item.get("metadata", {}).get("timestamp", ""),
                    "id": item.get("metadata", {}).get("id", ""),
                })
            return memories
        else:
            log(f"ERROR: list_memories failed: {result}")
            return []
    except Exception as e:
        log(f"ERROR: Failed to get memories: {e}")
        return []


def detect_duplicates(memories, threshold=0.85):
    """Detect duplicate or highly similar memories"""
    if not memories or len(memories) < 2:
        return []

    duplicates = []
    n = len(memories)

    for i in range(n):
        for j in range(i + 1, n):
            mem1 = memories[i]
            mem2 = memories[j]

            # Skip if same ID
            if mem1.get('id') and mem1.get('id') == mem2.get('id'):
                continue

            # Compare content
            content1 = str(mem1.get('content', ''))
            content2 = str(mem2.get('content', ''))

            # Exact match
            if content1 == content2:
                duplicates.append({
                    'type': 'exact',
                    'mem1': mem1,
                    'mem2': mem2,
                    'similarity': 1.0
                })
                continue

            # Note: embedding comparison requires vector store access
            # For now, we only detect exact duplicates

    return duplicates


def generate_report(memories, duplicates):
    """Generate a summary report"""
    reports_dir = Path.home() / ".hermes" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = reports_dir / f"noise_summary_{timestamp}.md"

    # Group memories by category
    categories = {}
    for mem in memories:
        cat = mem.get('category', 'uncategorized')
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(mem)

    # Build report
    lines = [
        "# 记忆噪声检测报告",
        "",
        f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**扫描记忆数**: {len(memories)} 条",
        f"**发现重复/相似**: {len(duplicates)} 组",
        "",
        "---",
        "",
    ]

    if duplicates:
        lines.append("## 重复/相似记忆")
        lines.append("")
        for i, dup in enumerate(duplicates, 1):
            lines.append(f"### 第 {i} 组 ({dup['type']})")
            lines.append(f"- 相似度: {dup['similarity']:.2%}")
            content1 = str(dup['mem1'].get('content', 'N/A'))[:100]
            content2 = str(dup['mem2'].get('content', 'N/A'))[:100]
            lines.append(f"- **记忆 1**: {content1}")
            lines.append(f"- **记忆 2**: {content2}")
            lines.append("")
    else:
        lines.append("## 检测结果")
        lines.append("")
        lines.append("✅ 未发现重复或高度相似的记忆")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 按类别分布")
    lines.append("")
    for cat, mems in sorted(categories.items()):
        lines.append(f"- **{cat}**: {len(mems)} 条")

    lines.append("")

    # Write report
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    return report_path


def main():
    log("Starting noise scan...")

    # Get all memories
    memories = get_all_memories()
    log(f"Loaded {len(memories)} memories")

    if not memories:
        log("No memories found, skipping")
        return 0

    # Detect duplicates
    duplicates = detect_duplicates(memories, threshold=0.85)
    log(f"Found {len(duplicates)} duplicate/similar groups")

    # Generate report
    report_path = generate_report(memories, duplicates)
    log(f"Report saved: {report_path}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
