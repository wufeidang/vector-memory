#!/usr/bin/env python3
"""
性能监控模块 - memory_monitor.py
记录记忆系统的检索耗时、命中数等指标
"""

import os
import json
import time
from datetime import datetime
from pathlib import Path
from collections import defaultdict

# 配置
HERMES_HOME = os.path.expanduser("~/.hermes")
MONITOR_DIR = os.path.join(HERMES_HOME, "monitor_data")
PERFORMANCE_LOG = os.path.join(MONITOR_DIR, "performance_log.json")
STATS_FILE = os.path.join(MONITOR_DIR, "stats.json")

def ensure_dirs():
    """确保目录存在"""
    os.makedirs(MONITOR_DIR, exist_ok=True)

def load_log():
    """加载性能日志"""
    ensure_dirs()
    if os.path.exists(PERFORMANCE_LOG):
        with open(PERFORMANCE_LOG, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"entries": [], "stats": {}}

def save_log(log_data):
    """保存性能日志"""
    ensure_dirs()
    with open(PERFORMANCE_LOG, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)

def record_search(query: str, results_count: int, elapsed_ms: float, 
                  source: str = "vector_memory", metadata: dict = None):
    """
    记录一次搜索操作
    
    Args:
        query: 搜索关键词
        results_count: 命中数量
        elapsed_ms: 耗时（毫秒）
        source: 数据来源
        metadata: 额外元数据
    """
    log_data = load_log()
    
    entry = {
        "timestamp": datetime.now().isoformat(),
        "query": query,
        "results_count": results_count,
        "elapsed_ms": round(elapsed_ms, 2),
        "source": source,
        "metadata": metadata or {}
    }
    
    log_data["entries"].append(entry)
    
    # 更新统计
    stats = log_data.get("stats", {})
    stats["total_searches"] = stats.get("total_searches", 0) + 1
    stats["total_results"] = stats.get("total_results", 0) + results_count
    
    # 计算平均耗时
    all_times = [e["elapsed_ms"] for e in log_data["entries"]]
    stats["avg_elapsed_ms"] = round(sum(all_times) / len(all_times), 2) if all_times else 0
    stats["max_elapsed_ms"] = max(all_times) if all_times else 0
    stats["min_elapsed_ms"] = min(all_times) if all_times else 0
    
    # 按来源统计
    source_stats = stats.get("by_source", {})
    if source not in source_stats:
        source_stats[source] = {"count": 0, "total_results": 0, "total_time_ms": 0}
    source_stats[source]["count"] += 1
    source_stats[source]["total_results"] += results_count
    source_stats[source]["total_time_ms"] += elapsed_ms
    stats["by_source"] = source_stats
    
    log_data["stats"] = stats
    save_log(log_data)
    
    return entry

def record_backup(duration_ms: float, items_count: int, success: bool = True):
    """记录备份操作"""
    log_data = load_log()
    
    entry = {
        "timestamp": datetime.now().isoformat(),
        "type": "backup",
        "duration_ms": round(duration_ms, 2),
        "items_count": items_count,
        "success": success
    }
    
    log_data["entries"].append(entry)
    
    # 更新备份统计
    stats = log_data.get("stats", {})
    backup_stats = stats.get("backups", {"count": 0, "total_items": 0, "avg_duration_ms": 0})
    backup_stats["count"] = backup_stats.get("count", 0) + 1
    backup_stats["total_items"] = backup_stats.get("total_items", 0) + items_count
    backup_stats["avg_duration_ms"] = round(
        (backup_stats.get("total_duration_ms", 0) + duration_ms) / backup_stats["count"], 2
    )
    backup_stats["total_duration_ms"] = backup_stats.get("total_duration_ms", 0) + duration_ms
    stats["backups"] = backup_stats
    
    log_data["stats"] = stats
    save_log(log_data)

def get_stats(hours: int = 24) -> dict:
    """获取最近N小时的统计"""
    log_data = load_log()
    entries = log_data.get("entries", [])
    
    if not entries:
        return {"message": "暂无数据"}
    
    # 过滤时间范围
    cutoff = datetime.now().timestamp() - (hours * 3600)
    recent = [e for e in entries if datetime.fromisoformat(e["timestamp"]).timestamp() > cutoff]
    
    if not recent:
        return {"message": f"最近{hours}小时无数据"}
    
    # 计算统计
    searches = [e for e in recent if "query" in e]
    backups = [e for e in recent if e.get("type") == "backup"]
    
    stats = {
        "period_hours": hours,
        "searches": {
            "count": len(searches),
            "total_results": sum(e.get("results_count", 0) for e in searches),
            "avg_elapsed_ms": round(sum(e.get("elapsed_ms", 0) for e in searches) / len(searches), 2) if searches else 0,
            "max_elapsed_ms": max(e.get("elapsed_ms", 0) for e in searches) if searches else 0
        },
        "backups": {
            "count": len(backups),
            "total_items": sum(e.get("items_count", 0) for e in backups),
            "avg_duration_ms": round(sum(e.get("duration_ms", 0) for e in backups) / len(backups), 2) if backups else 0
        }
    }
    
    return stats

def clear_old_data(days: int = 30):
    """清理超过N天的数据"""
    log_data = load_log()
    entries = log_data.get("entries", [])
    
    cutoff = datetime.now().timestamp() - (days * 86400)
    recent = [e for e in entries if datetime.fromisoformat(e["timestamp"]).timestamp() > cutoff]
    
    removed = len(entries) - len(recent)
    log_data["entries"] = recent
    save_log(log_data)
    
    return removed

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="记忆系统性能监控")
    parser.add_argument("action", choices=["stats", "clear", "test"], help="操作类型")
    parser.add_argument("--hours", type=int, default=24, help="统计时间范围（小时）")
    parser.add_argument("--days", type=int, default=30, help="清理数据天数")
    args = parser.parse_args()
    
    if args.action == "stats":
        stats = get_stats(args.hours)
        print(json.dumps(stats, indent=2, ensure_ascii=False))
    elif args.action == "clear":
        removed = clear_old_data(args.days)
        print(f"清理了 {removed} 条旧数据")
    elif args.action == "test":
        # 测试记录
        print("测试记录搜索...")
        record_search("测试查询", 5, 123.45, "test")
        print("✅ 测试完成，查看 stats 确认")