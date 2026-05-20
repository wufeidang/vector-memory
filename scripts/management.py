"""
Vector-Memory 记忆系统 - 管理模块
负责知识链、版本管理、过期清理、导出备份
"""
import os
import sys
import time
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

from core import _get_collection, _get_model, _get_chroma_client, _current_collection_name
from core import MEMORY_MD, VECTOR_STORE_DIR

# ============================================================
# 持久化路径
# ============================================================
RELATIONS_PATH = VECTOR_STORE_DIR / "relations.json"
VERSION_HISTORY_PATH = VECTOR_STORE_DIR / "version_history.json"
ACCESS_LOG_PATH = VECTOR_STORE_DIR / "access_log.json"
BACKUP_DIR = Path(os.path.expanduser("~/.hermes/backups"))
EXPORT_DIR = Path(os.path.expanduser("~/.hermes/exports"))


def _load_relations():
    if RELATIONS_PATH.exists():
        try:
            return json.loads(RELATIONS_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_relations(data):
    RELATIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RELATIONS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_version_history():
    if VERSION_HISTORY_PATH.exists():
        try:
            return json.loads(VERSION_HISTORY_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_version_history(data):
    VERSION_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    VERSION_HISTORY_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _sync_to_memory_md(text, metadata=None):
    MEMORY_MD.parent.mkdir(parents=True, exist_ok=True)
    line = "- [ ] %s" % text
    with MEMORY_MD.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


# ============================================================
# 知识链（关系管理）
# ============================================================
def link_memory(args):
    from_id = args.get("from_id", "")
    to_id = args.get("to_id", "")
    relation = args.get("relation", "related")
    collection_name = args.get("collection")

    if from_id == to_id:
        return {"success": False, "message": "不能关联自己"}
    if not from_id or not to_id:
        return {"success": False, "message": "需要提供 from_id 和 to_id"}

    collection = _get_collection(collection_name)
    relations = _load_relations()

    if from_id not in relations:
        relations[from_id] = {"relations": [], "related_ids": []}
    if to_id not in relations.get(to_id, {}).get("related_ids", []) and to_id not in relations.get(from_id, {}).get("related_ids", []):
        relations[from_id]["relations"].append({"to": to_id, "type": relation})
        relations[from_id]["related_ids"].append(to_id)

    if to_id not in relations:
        relations[to_id] = {"relations": [], "related_ids": []}
    if from_id not in relations.get(to_id, {}).get("related_ids", []):
        relations[to_id]["relations"].append({"to": from_id, "type": "related_to"})
        relations[to_id]["related_ids"].append(from_id)

    _save_relations(relations)
    return {"success": True, "message": "已建立关联: %s <-> %s" % (from_id, to_id)}


def unlink_memory(args):
    from_id = args.get("from_id", "")
    to_id = args.get("to_id", "")
    if not from_id or not to_id:
        return {"success": False, "message": "需要提供 from_id 和 to_id"}

    relations = _load_relations()
    for doc_id in [from_id, to_id]:
        if doc_id in relations:
            if to_id in relations[doc_id].get("related_ids", []):
                relations[doc_id]["related_ids"].remove(to_id)
            relations[doc_id]["relations"] = [
                r for r in relations[doc_id].get("relations", []) if r.get("to") != to_id
            ]
    _save_relations(relations)
    return {"success": True, "message": "已移除关联: %s <-> %s" % (from_id, to_id)}


def get_knowledge_chain(args):
    doc_id = args.get("doc_id", "")
    depth = args.get("depth", 1)
    collection_name = args.get("collection")

    collection = _get_collection(collection_name)
    data = collection.get(ids=[doc_id], include=["documents", "metadatas"])
    if not data.get("ids"):
        return {"success": False, "message": "记忆不存在"}

    relations = _load_relations()
    rel = relations.get(doc_id, {})
    chain = {
        "id": doc_id,
        "text": (data.get("documents") or [""])[0][:100],
        "metadata": (data.get("metadatas") or [{}])[0],
        "relations": [],
        "depth": 0
    }
    for r in rel.get("relations", []):
        to_id = r.get("to")
        to_data = collection.get(ids=[to_id], include=["documents", "metadatas"])
        if to_data.get("ids"):
            chain["relations"].append({
                "to_id": to_id,
                "type": r.get("type", "related"),
                "text": (to_data.get("documents") or [""])[0][:60],
                "category": (to_data.get("metadatas") or [{}])[0].get("category", "?")
            })
    return {"success": True, "chain": chain}


def search_related(args):
    doc_id = args.get("doc_id", "")
    limit = args.get("limit", 5)
    collection_name = args.get("collection")

    collection = _get_collection(collection_name)
    try:
        data = collection.get(ids=[doc_id], include=["metadatas"])
        if not data.get("ids"):
            return {"success": True, "related": [], "count": 0}

        relations = _load_relations()
        rel = relations.get(doc_id, {})
        related_ids = rel.get("related_ids", [])
        if not related_ids:
            return {"success": True, "related": [], "count": 0}

        related_data = collection.get(ids=related_ids[:limit], include=["documents", "metadatas"])
        related = []
        for i, rid in enumerate(related_data.get("ids", [])):
            related.append({
                "id": rid,
                "text": (related_data.get("documents") or [""])[i][:80],
                "metadata": (related_data.get("metadatas") or [{}])[i]
            })
        return {"success": True, "related": related, "count": len(related)}
    except Exception as e:
        return {"success": False, "message": str(e)[:100]}


def get_relations(args=None):
    return {"success": True, "relations": _load_relations()}


def clear_relations(args=None):
    if RELATIONS_PATH.exists():
        RELATIONS_PATH.unlink()
    return {"success": True, "message": "关系已清空"}


# ============================================================
# 版本管理
# ============================================================
def _compute_text_hash(text):
    import hashlib
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def get_memory_versions(args):
    category = args.get("category", "general")
    device = args.get("device", "unknown")
    collection_name = args.get("collection")

    collection = _get_collection(collection_name)
    versions = _load_version_history()
    key = "%s::%s" % (category, device)
    return {"success": True, "versions": versions.get(key, []), "count": len(versions.get(key, []))}


def rollback_memory(args):
    category = args.get("category", "general")
    device = args.get("device", "unknown")
    version_idx = args.get("version", -1)
    collection_name = args.get("collection")

    collection = _get_collection(collection_name)
    versions = _load_version_history()
    key = "%s::%s" % (category, device)

    if key not in versions or not versions[key]:
        return {"success": False, "message": "无历史版本"}
    if version_idx < 0:
        version_idx = len(versions[key]) - 1
    if version_idx >= len(versions[key]):
        return {"success": False, "message": "版本索引超出范围"}

    version = versions[key][version_idx]
    text = version.get("text", "")
    metadata = version.get("metadata", {})
    result = add_memory({"text": text, "metadata": metadata, "collection": collection_name})
    if result.get("success"):
        return {"success": True, "message": "已回滚到版本 %d" % version_idx}
    return result


def clear_version_history(args):
    if VERSION_HISTORY_PATH.exists():
        VERSION_HISTORY_PATH.unlink()
    return {"success": True, "message": "版本历史已清空"}


def get_version_stats(args=None):
    versions = _load_version_history()
    total = sum(len(v) for v in versions.values())
    return {"success": True, "stats": {"total_versions": total, "memories_with_history": len(versions)}}


# ============================================================
# 记忆过期机制
# ============================================================
def _load_access_log():
    if ACCESS_LOG_PATH.exists():
        try:
            return json.loads(ACCESS_LOG_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {"entries": []}
    return {"entries": []}


def _save_access_log(data):
    ACCESS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    ACCESS_LOG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_access_stats(args=None):
    log = _load_access_log()
    entries = log.get("entries", [])
    return {"success": True, "stats": {"total_entries": len(entries)}}


def get_expired_memories(args):
    half_life_days = args.get("half_life_days", 30)
    threshold = args.get("threshold", 0.5)
    collection_name = args.get("collection")

    collection = _get_collection(collection_name)
    try:
        data = collection.get(include=["metadatas", "documents"])
        now = time.time()
        expired = []
        for i, mem_id in enumerate(data.get("ids", [])):
            meta = (data.get("metadatas") or [{}])[i]
            last_access = meta.get("last_accessed", 0)
            from core import _compute_decay_weight
            weight = _compute_decay_weight(last_access, half_life_days)
            if weight < threshold:
                expired.append({
                    "id": mem_id,
                    "text": (data.get("documents") or [""])[i][:100],
                    "weight": round(weight, 4)
                })
        return {"success": True, "expired": expired, "count": len(expired)}
    except Exception as e:
        return {"success": False, "message": str(e)[:100]}


def prune_expired_memories(args):
    half_life_days = args.get("half_life_days", 30)
    threshold = args.get("threshold", 0.5)
    collection_name = args.get("collection")

    result = get_expired_memories({
        "half_life_days": half_life_days,
        "threshold": threshold,
        "collection": collection_name
    })
    if not result.get("success"):
        return result

    expired = result.get("expired", [])
    if not expired:
        return {"success": True, "pruned": 0}

    collection = _get_collection(collection_name)
    ids_to_delete = [e["id"] for e in expired]
    try:
        collection.delete(ids=ids_to_delete)
        return {"success": True, "pruned": len(ids_to_delete)}
    except Exception as e:
        return {"success": False, "message": str(e)[:100]}


# ============================================================
# 导出/备份
# ============================================================
def export_memories(args):
    fmt = args.get("format", "json")
    collection_name = args.get("collection")
    collection = _get_collection(collection_name)

    data = collection.get(include=["documents", "metadatas"])
    export = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "collection": collection_name or _current_collection_name,
        "total": len(data.get("ids", [])),
        "items": []
    }
    for i, mem_id in enumerate(data.get("ids", [])):
        export["items"].append({
            "id": mem_id,
            "text": (data.get("documents") or [""])[i],
            "metadata": (data.get("metadatas") or [{}])[i]
        })

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    if fmt == "markdown":
        md_lines = ["# 记忆导出 (%s)" % export["timestamp"], "", "| ID | 内容 | 分类 |", "|---|---|---|"]
        for item in export["items"]:
            cat = item["metadata"].get("category", "?")
            md_lines.append("| %s | %s | %s |" % (item["id"][:8], item["text"][:60].replace("|", "\\|"), cat))
        content = "\n".join(md_lines)
        out_path = EXPORT_DIR / ("memory_export_%s.md" % timestamp)
    else:
        content = json.dumps(export, ensure_ascii=False, indent=2)
        out_path = EXPORT_DIR / ("memory_export_%s.json" % timestamp)

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    return {"success": True, "path": str(out_path), "count": export["total"]}


def list_exports(args=None):
    if not EXPORT_DIR.exists():
        return {"success": True, "exports": [], "count": 0}
    files = sorted([f.name for f in EXPORT_DIR.iterdir() if f.name.startswith("memory_export_")], reverse=True)
    return {"success": True, "exports": files, "count": len(files)}


def backup_memories(args=None):
    collection_name = args.get("collection") if args else None
    collection = _get_collection(collection_name)
    data = collection.get(include=["documents", "metadatas", "embeddings"])

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_name = "backup_" + timestamp
    backup_path = BACKUP_DIR / backup_name
    backup_path.mkdir(parents=True, exist_ok=True)

    # 保存数据
    import shutil
    data_file = backup_path / "data.json"
    data_file.write_text(json.dumps({
        "ids": data.get("ids", []),
        "documents": data.get("documents", []),
        "metadatas": data.get("metadatas", []),
        "embeddings": data.get("embeddings", []),
        "collection": collection_name or _current_collection_name,
        "backup_time": time.strftime("%Y-%m-%d %H:%M:%S")
    }, ensure_ascii=False, cls=_NumpyEncoder), encoding="utf-8")

    # 备份元数据
    meta = {
        "backup_name": backup_name,
        "backup_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "items_count": len(data.get("ids", [])),
        "items": [{"id": i, "text": t[:50]} for i, t in zip(data.get("ids", []), data.get("documents", []))]
    }
    (backup_path / "manifest.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"success": True, "message": "备份已创建: " + backup_name, "backup_name": backup_name, "count": meta["items_count"]}


class _NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        import numpy as np
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.float32):
            return float(obj)
        return super().default(obj)


def restore_memories(args):
    backup_name = args.get("backup", "")
    if not backup_name:
        return {"success": False, "message": "需要备份名"}
    backup_path = BACKUP_DIR / backup_name
    if not backup_path.exists():
        return {"success": False, "message": "备份不存在: " + backup_name}

    data_file = backup_path / "data.json"
    if not data_file.exists():
        return {"success": False, "message": "备份数据文件不存在"}

    data = json.loads(data_file.read_text(encoding="utf-8"))
    collection_name = data.get("collection", "memory")
    collection = _get_collection(collection_name)

    # 清空现有数据
    try:
        existing = collection.get()["ids"]
        if existing:
            collection.delete(ids=existing)
    except Exception as e:
        print("  ⚠️ 清空现有数据失败: %s" % str(e)[:60], file=sys.stderr)

    # 恢复
    ids = data.get("ids", [])
    documents = data.get("documents", [])
    metadatas = data.get("metadatas", [])
    embeddings = data.get("embeddings", [])

    if embeddings:
        batch_size = 50
        for i in range(0, len(ids), batch_size):
            batch_end = min(i + batch_size, len(ids))
            collection.add(
                ids=ids[i:batch_end],
                embeddings=embeddings[i:batch_end],
                documents=documents[i:batch_end],
                metadatas=metadatas[i:batch_end]
            )
    return {"success": True, "message": "已恢复 %d 条记录" % len(ids), "count": len(ids)}


def list_backups(args=None):
    if not BACKUP_DIR.exists():
        return {"success": True, "backups": [], "count": 0}
    backups = sorted([d.name for d in BACKUP_DIR.iterdir() if d.name.startswith("backup_")], reverse=True)
    result = []
    for b in backups:
        manifest = BACKUP_DIR / b / "manifest.json"
        if manifest.exists():
            try:
                m = json.loads(manifest.read_text(encoding="utf-8"))
                result.append({
                    "name": b,
                    "time": m.get("backup_time", "unknown"),
                    "items": m.get("items_count", len(m.get("items", [])))
                })
            except Exception:
                result.append({"name": b, "time": "unknown", "items": 0})
        else:
            result.append({"name": b, "time": "unknown", "items": 0})
    return {"success": True, "backups": result, "count": len(result)}


# ============================================================
# 统计
# ============================================================
def get_stats(args=None):
    collection = _get_collection()
    try:
        count = collection.count()
    except Exception:
        count = 0

    client = _get_chroma_client()
    try:
        collections = [c.name for c in client.list_collections()]
    except Exception:
        collections = []

    return {
        "success": True,
        "count": count,
        "collections": collections,
        "current_collection": _current_collection_name,
        "model": "bge-base-zh-v1.5",
        "config": {"chunk_size": 800, "hybrid_alpha": 0.7}
    }
