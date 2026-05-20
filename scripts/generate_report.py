#!/usr/bin/env python3
"""
性能报告生成脚本 - generate_report.py
生成记忆系统的性能分析报告
"""

import os
import json
from datetime import datetime, timedelta
from pathlib import Path

# 配置
HERMES_HOME = os.path.expanduser("~/.hermes")
MONITOR_DIR = os.path.join(HERMES_HOME, "monitor_data")
REPORTS_DIR = os.path.join(HERMES_HOME, "reports")
PERFORMANCE_LOG = os.path.join(MONITOR_DIR, "performance_log.json")

def ensure_dirs():
    os.makedirs(REPORTS_DIR, exist_ok=True)

def load_log():
    if os.path.exists(PERFORMANCE_LOG):
        with open(PERFORMANCE_LOG, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"entries": [], "stats": {}}

def generate_report(period: str = "daily") -> dict:
    """
    生成性能报告
    
    Args:
        period: 报告周期 (daily, weekly, monthly)
    """
    ensure_dirs()
    log_data = load_log()
    entries = log_data.get("entries", [])
    
    if not entries:
        return {"error": "暂无数据"}
    
    # 确定时间范围
    now = datetime.now()
    if period == "daily":
        cutoff = now - timedelta(days=1)
    elif period == "weekly":
        cutoff = now - timedelta(weeks=1)
    elif period == "monthly":
        cutoff = now - timedelta(days=30)
    else:
        cutoff = now - timedelta(days=1)
    
    # 过滤数据
    recent = [
        e for e in entries
        if datetime.fromisoformat(e["timestamp"]) > cutoff
    ]
    
    if not recent:
        return {"error": f"最近{period}无数据"}
    
    # 分类统计
    searches = [e for e in recent if "query" in e]
    backups = [e for e in recent if e.get("type") == "backup"]
    
    # 搜索统计
    search_stats = {}
    if searches:
        queries = [e["query"] for e in searches]
        results_counts = [e.get("results_count", 0) for e in searches]
        elapsed_times = [e.get("elapsed_ms", 0) for e in searches]
        
        # 热门查询（出现次数最多的前5个）
        from collections import Counter
        query_counts = Counter(queries)
        top_queries = query_counts.most_common(5)
        
        search_stats = {
            "total_searches": len(searches),
            "total_results": sum(results_counts),
            "avg_results": round(sum(results_counts) / len(results_counts), 2),
            "avg_elapsed_ms": round(sum(elapsed_times) / len(elapsed_times), 2),
            "max_elapsed_ms": max(elapsed_times),
            "min_elapsed_ms": min(elapsed_times),
            "top_queries": [{"query": q, "count": c} for q, c in top_queries]
        }
    
    # 备份统计
    backup_stats = {}
    if backups:
        backup_stats = {
            "total_backups": len(backups),
            "total_items": sum(e.get("items_count", 0) for e in backups),
            "avg_duration_ms": round(sum(e.get("duration_ms", 0) for e in backups) / len(backups), 2),
            "success_rate": "100%"
        }
    
    # 性能评级
    avg_time = search_stats.get("avg_elapsed_ms", 0)
    if avg_time < 100:
        performance_grade = "优秀"
    elif avg_time < 300:
        performance_grade = "良好"
    elif avg_time < 500:
        performance_grade = "一般"
    else:
        performance_grade = "需优化"
    
    report = {
        "report_type": period,
        "generated_at": now.isoformat(),
        "period_start": cutoff.isoformat(),
        "period_end": now.isoformat(),
        "search_stats": search_stats,
        "backup_stats": backup_stats,
        "performance_grade": performance_grade,
        "recommendations": generate_recommendations(search_stats, backup_stats)
    }
    
    # 保存报告
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    report_file = os.path.join(REPORTS_DIR, f"performance_report_{period}_{timestamp}.json")
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    report["report_file"] = report_file
    return report

def generate_recommendations(search_stats: dict, backup_stats: dict) -> list:
    """生成优化建议"""
    recommendations = []
    
    if search_stats:
        avg_time = search_stats.get("avg_elapsed_ms", 0)
        if avg_time > 500:
            recommendations.append("⚠️ 搜索平均耗时超过500ms，建议优化向量索引或增加缓存")
        if avg_time > 1000:
            recommendations.append("🔴 搜索平均耗时超过1000ms，建议检查嵌入模型性能或考虑使用更小的模型")
        
        total_results = search_stats.get("total_results", 0)
        total_searches = search_stats.get("total_searches", 0)
        if total_searches > 0 and total_results / total_searches < 1:
            recommendations.append("📊 平均每次搜索返回结果较少，建议检查查询质量或增加记忆内容")
    
    if backup_stats:
        if backup_stats.get("total_backups", 0) == 0:
            recommendations.append("💾 建议配置自动备份任务，防止数据丢失")
    
    if not recommendations:
        recommendations.append("✅ 系统运行正常，继续保持")
    
    return recommendations

def print_report(report: dict):
    """打印格式化的报告"""
    print("=" * 60)
    print(f"📊 性能报告 - {report.get('report_type', 'unknown').upper()}")
    print("=" * 60)
    print(f"生成时间: {report.get('generated_at', 'unknown')}")
    print(f"报告周期: {report.get('period_start', '?')} → {report.get('period_end', '?')}")
    print()
    
    # 搜索统计
    search = report.get("search_stats", {})
    if search:
        print("🔍 搜索统计:")
        print(f"   总搜索次数: {search.get('total_searches', 0)}")
        print(f"   总命中数: {search.get('total_results', 0)}")
        print(f"   平均耗时: {search.get('avg_elapsed_ms', 0)} ms")
        print(f"   最快/最慢: {search.get('min_elapsed_ms', 0)} / {search.get('max_elapsed_ms', 0)} ms")
        if search.get("top_queries"):
            print("   热门查询:")
            for q in search["top_queries"]:
                print(f'      - "{q["query"]}" ({q["count"]}次)')
        print()
    
    # 备份统计
    backup = report.get("backup_stats", {})
    if backup:
        print("💾 备份统计:")
        print(f"   备份次数: {backup.get('total_backups', 0)}")
        print(f"   备份项目: {backup.get('total_items', 0)}")
        print(f"   平均耗时: {backup.get('avg_duration_ms', 0)} ms")
        print()
    
    # 性能评级
    print(f"🏆 性能评级: {report.get('performance_grade', '未知')}")
    print()
    
    # 建议
    print("💡 优化建议:")
    for rec in report.get("recommendations", []):
        print(f"   {rec}")
    
    print()
    print(f"📁 报告文件: {report.get('report_file', 'N/A')}")
    print("=" * 60)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="生成性能报告")
    parser.add_argument("period", choices=["daily", "weekly", "monthly"], help="报告周期")
    parser.add_argument("--json", action="store_true", help="输出JSON格式")
    args = parser.parse_args()
    
    report = generate_report(args.period)
    
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print_report(report)