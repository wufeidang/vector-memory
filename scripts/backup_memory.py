#!/usr/bin/env python3
"""
自动化备份脚本 - backup_memory.py
备份记忆系统的所有关键数据
"""

import os
import shutil
import json
from datetime import datetime
from pathlib import Path

# 配置
HERMES_HOME = os.path.expanduser("~/.hermes")
BACKUP_DIR = os.path.join(HERMES_HOME, "backups")
MEMORY_FILES = [
    "memories/MEMORY.md",
    "memories/USER.md",
    "config.yaml",
]
SKILL_DIRS = [
    "skills/vector_memory",
    "skills/writing",
]
VECTOR_STORE = "vector_store"
SCRIPTS_DIR = "scripts"

def create_backup():
    """创建完整备份"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"backup_{timestamp}")
    
    os.makedirs(BACKUP_DIR, exist_ok=True)
    os.makedirs(backup_path, exist_ok=True)
    
    manifest = {
        "backup_time": datetime.now().isoformat(),
        "hermes_home": HERMES_HOME,
        "items": []
    }
    
    # 备份记忆文件
    for file_rel in MEMORY_FILES:
        src = os.path.join(HERMES_HOME, file_rel)
        if os.path.exists(src):
            dst = os.path.join(backup_path, file_rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            manifest["items"].append({"type": "file", "path": file_rel, "status": "ok"})
        else:
            manifest["items"].append({"type": "file", "path": file_rel, "status": "skipped"})
    
    # 备份技能目录
    for dir_rel in SKILL_DIRS:
        src = os.path.join(HERMES_HOME, dir_rel)
        if os.path.exists(src):
            dst = os.path.join(backup_path, dir_rel)
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
            manifest["items"].append({"type": "dir", "path": dir_rel, "status": "ok"})
        else:
            manifest["items"].append({"type": "dir", "path": dir_rel, "status": "skipped"})
    
    # 备份向量存储
    src = os.path.join(HERMES_HOME, VECTOR_STORE)
    if os.path.exists(src):
        dst = os.path.join(backup_path, VECTOR_STORE)
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        manifest["items"].append({"type": "dir", "path": VECTOR_STORE, "status": "ok"})
    else:
        manifest["items"].append({"type": "dir", "path": VECTOR_STORE, "status": "skipped"})
    
    # 备份脚本
    src = os.path.join(HERMES_HOME, SCRIPTS_DIR)
    if os.path.exists(src):
        dst = os.path.join(backup_path, SCRIPTS_DIR)
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        manifest["items"].append({"type": "dir", "path": SCRIPTS_DIR, "status": "ok"})
    else:
        manifest["items"].append({"type": "dir", "path": SCRIPTS_DIR, "status": "skipped"})
    
    # 写入manifest
    manifest_path = os.path.join(backup_path, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    
    # 清理旧备份（保留最近7个）
    cleanup_old_backups()
    
    return backup_path, manifest

def cleanup_old_backups(max_keep=7):
    """清理旧备份，保留最近N个"""
    if not os.path.exists(BACKUP_DIR):
        return
    backups = sorted([
        d for d in os.listdir(BACKUP_DIR)
        if d.startswith("backup_") and os.path.isdir(os.path.join(BACKUP_DIR, d))
    ])
    while len(backups) > max_keep:
        old_backup = backups.pop(0)
        old_path = os.path.join(BACKUP_DIR, old_backup)
        shutil.rmtree(old_path)
        print(f"清理旧备份: {old_backup}")

def list_backups():
    """列出所有备份"""
    if not os.path.exists(BACKUP_DIR):
        return []
    backups = sorted([
        d for d in os.listdir(BACKUP_DIR)
        if d.startswith("backup_") and os.path.isdir(os.path.join(BACKUP_DIR, d))
    ], reverse=True)
    result = []
    for b in backups:
        manifest_path = os.path.join(BACKUP_DIR, b, "manifest.json")
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            result.append({"name": b, "time": manifest.get("backup_time", "unknown"), "items": len(manifest.get("items", []))})
        else:
            result.append({"name": b, "time": "unknown", "items": 0})
    return result

def restore_backup(backup_name):
    """恢复指定备份"""
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    if not os.path.exists(backup_path):
        return False, f"备份不存在: {backup_name}"
    manifest_path = os.path.join(backup_path, "manifest.json")
    if not os.path.exists(manifest_path):
        return False, "备份缺少manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    restored = 0
    for item in manifest.get("items", []):
        if item["status"] == "skipped":
            continue
        src = os.path.join(backup_path, item["path"])
        dst = os.path.join(HERMES_HOME, item["path"])
        if os.path.isfile(src):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
        elif os.path.isdir(src):
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        restored += 1
    return True, f"恢复 {restored} 个项目成功"

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="记忆系统备份工具")
    parser.add_argument("action", choices=["create", "list", "restore"], help="操作类型")
    parser.add_argument("--backup", help="恢复时指定备份名称")
    args = parser.parse_args()
    
    if args.action == "create":
        path, manifest = create_backup()
        print(f"✅ 备份创建成功: {path}")
        print(f"   备份时间: {manifest['backup_time']}")
        print(f"   备份项目: {len(manifest['items'])}")
    elif args.action == "list":
        backups = list_backups()
        if backups:
            print("可用备份:")
            for b in backups:
                print(f"  - {b['name']} ({b['time']}, {b['items']}项)")
        else:
            print("无可用备份")
    elif args.action == "restore":
        if not args.backup:
            print("错误: 恢复操作需要指定 --backup 参数")
            exit(1)
        success, msg = restore_backup(args.backup)
        print(f"{'✅' if success else '❌'} {msg}")