"""
Vector-Memory 记忆系统 - 管理模块
负责知识链、版本管理、过期清理、导出备份、增量备份（功能4）、文件管理（功能C）
"""
import os
import sys
import time
import json
import hashlib
from pathlib import Path
from typing import Optional, List, Dict, Any

from core import _get_collection, _get_model, _get_chroma_client, _current_collection_name
from core import MEMORY_MD, VECTOR_STORE_DIR, _load_backup_state, _save_backup_state

# ============================================================
# 持久化路径
# ============================================================
RELATIONS_PATH = VECTOR_STORE_DIR / "relations.json"
VERSION_HISTORY_PATH = VECTOR_STORE_DIR / "version_history.json"
ACCESS_LOG_PATH = VECTOR_STORE_DIR / "access_log.json"
BACKUP_DIR = Path(os.path.expanduser("~/.hermes/backups"))
EXPORT_DIR = Path(os.path.expanduser("~/.hermes/exports"))


# ============================================================
# 知识链（关系管理）
# ============================================================
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
# 知识链
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
# 导出
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


# ============================================================
# 备份 & 增量备份（功能4）
# ============================================================

def backup_memories(args=None):
    """全量备份 + 更新增量基准"""
    collection_name = args.get("collection") if args else None
    collection = _get_collection(collection_name)
    data = collection.get(include=["documents", "metadatas", "embeddings"])

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_name = "backup_" + timestamp
    backup_path = BACKUP_DIR / backup_name
    backup_path.mkdir(parents=True, exist_ok=True)

    import shutil
    data_file = backup_path / "data.json"
    data_file.write_text(json.dumps({
        "ids": data.get("ids", []),
        "documents": data.get("documents", []),
        "metadatas": data.get("metadatas", []),
        "embeddings": data.get("embeddings", []),
        "collection": collection_name or _current_collection_name,
        "backup_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "backup_type": "full"
    }, ensure_ascii=False, cls=_NumpyEncoder), encoding="utf-8")

    meta = {
        "backup_name": backup_name,
        "backup_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "items_count": len(data.get("ids", [])),
        "backup_type": "full",
        "collection": collection_name or _current_collection_name,
        "items": [{"id": i, "text": t[:50]} for i, t in zip(data.get("ids", []), data.get("documents", []))]
    }
    (backup_path / "manifest.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    _update_backup_baseline(data, collection_name)

    return {"success": True, "message": "备份已创建: " + backup_name, "backup_name": backup_name, "count": meta["items_count"]}


def _update_backup_baseline(data, collection_name):
    """更新增量备份基准状态"""
    state = _load_backup_state()

    ids = data.get("ids", [])
    docs = data.get("documents", [])
    metas = data.get("metadatas", [])

    backed_up_ids = state.get("backed_up_ids", {})
    for i, mem_id in enumerate(ids):
        doc_hash = _compute_doc_hash(mem_id, docs[i] if i < len(docs) else "", metas[i] if i < len(metas) else {})
        backed_up_ids[mem_id] = {
            "hash": doc_hash,
            "last_backup_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "collection": collection_name or _current_collection_name,
        }

    state["backed_up_ids"] = backed_up_ids
    state["last_full_backup"] = time.strftime("%Y-%m-%d %H:%M:%S")
    state["last_full_backup_time"] = time.time()
    state["last_collection"] = collection_name or _current_collection_name

    _save_backup_state(state)


def backup_memories_incremental(args=None):
    """
    增量备份：仅备份新增/变更的文档。
    首次调用自动创建全量备份作为基准。
    """
    collection_name = args.get("collection") if args else None
    collection = _get_collection(collection_name)
    state = _load_backup_state()

    data = collection.get(include=["documents", "metadatas", "embeddings"])
    ids = data.get("ids", [])
    docs = data.get("documents", [])
    metas = data.get("metadatas", [])
    embeddings = data.get("embeddings", [])

    backed_up_ids = state.get("backed_up_ids", {})

    changed_ids = []
    changed_docs = []
    changed_metas = []
    changed_embs = []
    new_count = 0
    modified_count = 0

    for i, mem_id in enumerate(ids):
        doc_hash = _compute_doc_hash(mem_id, docs[i] if i < len(docs) else "", metas[i] if i < len(metas) else {})

        if mem_id not in backed_up_ids:
            changed_ids.append(mem_id)
            changed_docs.append(docs[i] if i < len(docs) else "")
            changed_metas.append(metas[i] if i < len(metas) else {})
            changed_embs.append(embeddings[i] if embeddings is not None and i < len(embeddings) else [])
            new_count += 1
        elif backed_up_ids[mem_id].get("hash") != doc_hash:
            changed_ids.append(mem_id)
            changed_docs.append(docs[i] if i < len(docs) else "")
            changed_metas.append(metas[i] if i < len(metas) else {})
            changed_embs.append(embeddings[i] if embeddings is not None and i < len(embeddings) else [])
            modified_count += 1

    if not changed_ids:
        return {
            "success": True,
            "message": "没有需要增量备份的变更",
            "added": 0,
            "modified": 0,
            "total": 0,
            "is_first_backup": False
        }

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_name = "inc_backup_" + timestamp
    backup_path = BACKUP_DIR / backup_name
    backup_path.mkdir(parents=True, exist_ok=True)

    import shutil
    data_file = backup_path / "data.json"
    data_file.write_text(json.dumps({
        "ids": changed_ids,
        "documents": changed_docs,
        "metadatas": changed_metas,
        "embeddings": changed_embs,
        "collection": collection_name or _current_collection_name,
        "backup_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "backup_type": "incremental",
        "base_backup": state.get("last_full_backup", "none"),
        "stats": {
            "added": new_count,
            "modified": modified_count,
        }
    }, ensure_ascii=False, cls=_NumpyEncoder), encoding="utf-8")

    meta = {
        "backup_name": backup_name,
        "backup_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "items_count": len(changed_ids),
        "backup_type": "incremental",
        "collection": collection_name or _current_collection_name,
        "base_backup": state.get("last_full_backup", "none"),
        "added": new_count,
        "modified": modified_count,
        "items": [{"id": i, "text": t[:50]} for i, t in zip(changed_ids, changed_docs)]
    }
    (backup_path / "manifest.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    inc_chain = state.get("incremental_backups", [])
    inc_chain.append({
        "name": backup_name,
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "added": new_count,
        "modified": modified_count,
    })
    state["incremental_backups"] = inc_chain[-50:]

    for i, mem_id in enumerate(changed_ids):
        doc_hash = _compute_doc_hash(mem_id, changed_docs[i], changed_metas[i])
        backed_up_ids[mem_id] = {
            "hash": doc_hash,
            "last_backup_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "collection": collection_name or _current_collection_name,
        }
    state["backed_up_ids"] = backed_up_ids
    state["last_incremental"] = backup_name
    _save_backup_state(state)

    return {
        "success": True,
        "message": "增量备份已创建: " + backup_name,
        "backup_name": backup_name,
        "added": new_count,
        "modified": modified_count,
        "total": len(changed_ids),
    }


def restore_incremental(args):
    """按顺序恢复全量备份 + 所有增量备份"""
    base_backup = args.get("base", "")
    target_time = args.get("before", "")

    state = _load_backup_state()
    all_backups = state.get("incremental_backups", [])

    if not base_backup:
        base_backup = state.get("last_full_backup", "")

    base_path = BACKUP_DIR / base_backup
    if not base_path.exists():
        return {"success": False, "message": "全量备份不存在: " + base_backup}

    result_chain = [base_backup]

    inc_to_apply = []
    for inc in all_backups:
        inc_path = BACKUP_DIR / inc["name"]
        if inc_path.exists():
            if target_time and inc["time"] > target_time:
                continue
            inc_to_apply.append(inc["name"])

    inc_to_apply.sort()
    result_chain.extend(inc_to_apply)

    return {
        "success": True,
        "chain": result_chain,
        "total_steps": len(result_chain),
        "message": "恢复链: %d 全量 + %d 增量" % (1, len(inc_to_apply)),
        "instructions": "请按 chain 顺序依次执行 restore_memories()，增量备份需在全量基础上叠加恢复"
    }


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

    # 如果是全量备份（或旧版无类型标记），先清空
    if data.get("backup_type", "full") == "full":
        try:
            existing = collection.get()["ids"]
            if existing:
                collection.delete(ids=existing)
        except Exception as e:
            print("  ⚠️ 清空现有数据失败: %s" % str(e)[:60], file=sys.stderr)

    # 恢复数据
    ids = data.get("ids", [])
    documents = data.get("documents", [])
    metadatas = data.get("metadatas", [])
    embeddings = data.get("embeddings", [])

    if embeddings and embeddings[0]:
        batch_size = 50
        for i in range(0, len(ids), batch_size):
            batch_end = min(i + batch_size, len(ids))
            collection.add(
                ids=ids[i:batch_end],
                embeddings=embeddings[i:batch_end],
                documents=documents[i:batch_end],
                metadatas=metadatas[i:batch_end]
            )
    else:
        model = _get_model()
        batch_size = 50
        for i in range(0, len(ids), batch_size):
            batch_end = min(i + batch_size, len(ids))
            batch_docs = documents[i:batch_end]
            batch_embs = model.encode(batch_docs).tolist()
            collection.add(
                ids=ids[i:batch_end],
                embeddings=batch_embs,
                documents=batch_docs,
                metadatas=metadatas[i:batch_end]
            )

    return {"success": True, "message": "已恢复 %d 条记录（%s）" % (len(ids), data.get("backup_type", "unknown")), "count": len(ids)}


def list_backups(args=None):
    if not BACKUP_DIR.exists():
        return {"success": True, "backups": [], "count": 0}
    backups = sorted([d for d in BACKUP_DIR.iterdir()
                      if d.name.startswith(("backup_", "inc_backup_")) and d.is_dir()],
                     reverse=True)
    result = []
    for b in backups:
        manifest = b / "manifest.json"
        if manifest.exists():
            try:
                m = json.loads(manifest.read_text(encoding="utf-8"))
                result.append({
                    "name": b.name,
                    "time": m.get("backup_time", "unknown"),
                    "items": m.get("items_count", len(m.get("items", []))),
                    "type": m.get("base_backup", "full") if "base_backup" in m else "full",
                })
            except Exception:
                result.append({"name": b.name, "time": "unknown", "items": 0, "type": "unknown"})
        else:
            result.append({"name": b.name, "time": "unknown", "items": 0, "type": "unknown"})
    return {"success": True, "backups": result, "count": len(result)}


# ============================================================
# ✨ 功能C：文件管理
# ============================================================

def add_file(args):
    """添加文件到混合存储"""
    from file_storage import store_file
    return store_file(args)


def list_files(args=None):
    """列出所有已索引的文件"""
    from file_storage import list_files
    return list_files(args)


def get_file(args):
    """获取文件详情"""
    from file_storage import get_file
    return get_file(args)


def delete_file(args):
    """删除文件及其索引"""
    from file_storage import delete_file
    return delete_file(args)


def search_files(args):
    """搜索文件"""
    from file_storage import search_files as _search_files
    return _search_files(args)


def get_file_stats(args=None):
    """获取文件存储统计"""
    from file_storage import get_file_stats
    return get_file_stats(args)


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

    backup_state = _load_backup_state()
    file_stats = get_file_stats()

    return {
        "success": True,
        "count": count,
        "collections": collections,
        "current_collection": _current_collection_name,
        "model": "bge-base-zh-v1.5",
        "config": {"chunk_size": 800, "hybrid_alpha": 0.7},
        "backup_state": {
            "last_full": backup_state.get("last_full_backup"),
            "incremental_count": len(backup_state.get("incremental_backups", [])),
            "tracked_docs": len(backup_state.get("backed_up_ids", {})),
        },
        "file_stats": file_stats if file_stats.get("success") else None,
    }


class _NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        import numpy as np
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.float32):
            return float(obj)
        return super().default(obj)


def _compute_doc_hash(doc_id, text, metadata):
    """计算文档的内容哈希，用于增量备份变更检测"""
    content = "%s||%s||%s" % (doc_id, text, json.dumps(metadata, sort_keys=True, ensure_ascii=False))
    return hashlib.md5(content.encode("utf-8")).hexdigest()