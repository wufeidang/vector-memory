#!/usr/bin/env python
"""
记忆同步脚本 - 可靠版
支持 § 分隔格式和 - [ 格式，带 MD5 去重
"""
import os
import sys
import hashlib

# 添加脚本目录到路径
_scripts_dir = os.path.dirname(os.path.abspath(__file__))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from core import MEMORY_MD
from storage import add_memory, list_memories


def sync_memory(force=False, limit=None):
    """
    同步 MEMORY.md 到向量库
    
    Args:
        force: 强制重新导入所有条目（忽略去重）
        limit: 限制同步的条目数（用于测试）
    
    Returns:
        dict: 同步结果统计
    """
    if not MEMORY_MD.exists():
        return {"success": False, "message": "MEMORY.md 不存在"}
    
    # 读取 MEMORY.md
    content = MEMORY_MD.read_text(encoding="utf-8")
    
    # 解析 - [ 格式的行（带时间戳的正式条目）
    lines = [l.strip() for l in content.split('\n') if l.strip().startswith('- [')]
    
    if not lines:
        return {"success": True, "message": "没有找到 - [ 格式的记忆条目", "imported": 0}
    
    # 获取现有记忆哈希用于去重
    existing_hashes = set()
    if not force:
        result = list_memories({"limit": 5000})
        if result.get("success"):
            for m in result.get("memories", []):
                text = m.get("text", "")
                h = hashlib.md5(text.encode('utf-8')).hexdigest()
                existing_hashes.add(h)
    
    # 同步新记忆
    added = 0
    skipped = 0
    errors = 0
    
    for i, line in enumerate(lines):
        if limit and added >= limit:
            break
            
        text = line[3:].strip() if line.startswith('- [') else line
        
        # 跳过太短的条目
        if len(text) < 10:
            skipped += 1
            continue
        
        # 去重检查
        h = hashlib.md5(text.encode('utf-8')).hexdigest()
        if not force and h in existing_hashes:
            skipped += 1
            continue
        
        result = add_memory({"text": text, "metadata": {"imported": True}})
        if result.get("success"):
            added += 1
            existing_hashes.add(h)
        else:
            errors += 1
        
        # 每 50 条输出进度
        if (i + 1) % 50 == 0:
            print(f"  进度: {i+1}/{len(lines)}, 已添加: {added}, 跳过: {skipped}, 错误: {errors}", 
                  file=sys.stderr)
    
    return {
        "success": True,
        "imported": added,
        "skipped": skipped,
        "errors": errors,
        "total_in_memory_md": len(lines)
    }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="同步 MEMORY.md 到向量记忆库")
    parser.add_argument("--force", action="store_true", help="强制重新导入所有条目")
    parser.add_argument("--limit", type=int, help="限制同步的条目数（用于测试）")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    
    args = parser.parse_args()
    
    print("=== 开始同步记忆 ===", file=sys.stderr)
    result = sync_memory(force=args.force, limit=args.limit)
    
    if result.get("success"):
        print(f"\n✅ 同步完成!", file=sys.stderr)
        print(f"   导入: {result.get('imported', 0)} 条", file=sys.stderr)
        print(f"   跳过: {result.get('skipped', 0)} 条", file=sys.stderr)
        print(f"   错误: {result.get('errors', 0)} 条", file=sys.stderr)
        print(f"   MEMORY.md 总条目: {result.get('total_in_memory_md', 0)} 条", file=sys.stderr)
    else:
        print(f"\n❌ 同步失败: {result.get('message')}", file=sys.stderr)
        sys.exit(1)
