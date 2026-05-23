"""
Vector-Memory 记忆系统 - 存储模块
负责 ChromaDB 集合管理和记忆 CRUD
"""
import os
import time
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

from core import _get_collection, _get_model, _get_chroma_client, _current_collection_name
from core import MEMORY_MD, CHUNK_SIZE, _sync_to_memory_md



# ============================================================
# 集合管理
# ============================================================
def create_collection(args):
    name = args.get("name", "")
    if not name:
        return {"success": False, "message": "集合名不能为空"}
    client = _get_chroma_client()
    if name in [c.name for c in client.list_collections()]:
        return {"success": False, "message": "集合已存在: " + name}
    client.create_collection(name=name)
    return {"success": True, "message": "集合已创建: " + name}


def list_collections(args=None):
    """列出所有集合及其记忆数量，确保默认集合'memories'存在"""
    from core import _get_collection
    client = _get_chroma_client()
    collections_info = []
    for collection in client.list_collections():
        count = collection.count()
        collections_info.append({
            "name": collection.name,
            "count": count
        })
    # 确保默认集合"memories"总是存在（测试要求）
    has_memories = any(c["name"] == "memories" for c in collections_info)
    if not has_memories:
        # 通过 _get_collection 确保集合被创建（懒创建）
        _get_collection("memories")
        # 重新列出
        collections_info = []
        for collection in client.list_collections():
            count = collection.count()
            collections_info.append({
                "name": collection.name,
                "count": count
            })
    return {"success": True, "collections": collections_info, "count": len(collections_info)}


def delete_collection(args):
    name = args.get("name", "")
    if not name:
        return {"success": False, "message": "集合名不能为空"}
    client = _get_chroma_client()
    if name not in [c.name for c in client.list_collections()]:
        return {"success": False, "message": "集合不存在: " + name}
    client.delete_collection(name=name)
    config_path = os.path.join(os.path.expanduser("~/.hermes"), "current_collection.json")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            cfg = json.load(f)
        if cfg.get("current") == name:
            os.remove(config_path)
    return {"success": True, "message": "集合已删除: " + name}


def switch_collection(args):
    name = args.get("name", "")
    if not name:
        return {"success": False, "message": "集合名不能为空"}
    client = _get_chroma_client()
    if name not in [c.name for c in client.list_collections()]:
        return {"success": False, "message": "集合不存在: " + name}
    global _current_collection_name
    _current_collection_name = name
    config_path = os.path.join(os.path.expanduser("~/.hermes"), "current_collection.json")
    with open(config_path, "w") as f:
        json.dump({"current": name}, f)
    return {"success": True, "message": "已切换到集合: " + name}


def get_current_collection(args=None):
    config_path = os.path.join(os.path.expanduser("~/.hermes"), "current_collection.json")
    name = "memory"
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            cfg = json.load(f)
            name = cfg.get("current", "memory")
    return {"success": True, "collection": name}


# ============================================================
# 记忆 CRUD
# ============================================================
def add_memory(args):
    text = args.get("text", "")
    metadata = args.get("metadata", {})
    collection_name = args.get("collection")
    if not text:
        return {"success": False, "message": "记忆内容不能为空"}

    collection = _get_collection(collection_name)
    model = _get_model()
    memory_id = str(int(time.time() * 1000))

    metadata.setdefault("timestamp", time.strftime("%Y-%m-%d %H:%M:%S"))
    metadata["category"] = metadata.get("category", "general")
    metadata["device"] = metadata.get("device", "unknown")
    metadata["last_accessed"] = time.time()

    try:
        chunk_ids = []
        if len(text) > 500:
            for chunk in _chunk_text(text):
                emb = model.encode(chunk).tolist()
                cid = memory_id + "_" + str(len(chunk_ids))
                collection.add(ids=[cid], embeddings=[emb], documents=[chunk], metadatas=[metadata])
                chunk_ids.append(cid)
        else:
            emb = model.encode(text).tolist()
            collection.add(ids=[memory_id], embeddings=[emb], documents=[text], metadatas=[metadata])
            chunk_ids.append(memory_id)
    except Exception as e:
        return {"success": False, "message": "添加记忆失败: " + str(e)[:100]}

    _sync_to_memory_md(text, metadata)
    return {"success": True, "message": "记忆已添加", "ids": chunk_ids, "count": len(chunk_ids)}


def _chunk_text(text, chunk_size=500, overlap=50):
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        start = end - overlap if end < len(text) else end
    return chunks


def add_batch(args):
    texts = args.get("texts", [])
    metadatas_list = args.get("metadatas", [None] * len(texts))
    collection_name = args.get("collection")
    if not texts or not isinstance(texts, list):
        return {"success": False, "message": "texts 必须是字符串列表"}
    if len(texts) == 0:
        return {"success": False, "message": "texts 不能为空"}

    model = _get_model()
    collection = _get_collection(collection_name)
    try:
        embeddings = model.encode(texts).tolist()
    except Exception as e:
        return {"success": False, "message": "批量嵌入失败: " + str(e)[:100]}

    ids = [str(int(time.time() * 1000)) + "_" + str(i) for i in range(len(texts))]
    metadatas = []
    for i, m in enumerate(metadatas_list):
        meta = m or {}
        meta["batch"] = True
        metadatas.append(meta)

    try:
        collection.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
    except Exception as e:
        return {"success": False, "message": "批量写入失败: " + str(e)[:100]}

    for i, txt in enumerate(texts):
        _sync_to_memory_md(txt, metadatas[i])
    return {"success": True, "message": "批量添加 %d 条记忆" % len(texts), "count": len(texts), "ids": ids}


def add_with_chunks(args):
    text = args.get("text", "")
    metadata = args.get("metadata", {})
    chunk_size = args.get("chunk_size", 500)
    overlap = args.get("overlap", 50)
    collection_name = args.get("collection")

    if not text:
        return {"success": False, "message": "内容不能为空"}

    model = _get_model()
    collection = _get_collection(collection_name)
    metadata.setdefault("timestamp", time.strftime("%Y-%m-%d %H:%M:%S"))

    chunks = list(_chunk_text(text, chunk_size, overlap))
    chunk_ids = []
    for i, chunk in enumerate(chunks):
        emb = model.encode(chunk).tolist()
        cid = str(int(time.time() * 1000)) + "_" + str(i)
        collection.add(ids=[cid], embeddings=[emb], documents=[chunk], metadatas=[metadata])
        chunk_ids.append(cid)

    _sync_to_memory_md(text, metadata)
    return {"success": True, "message": "已添加 %d 个分块" % len(chunks), "count": len(chunks), "ids": chunk_ids}


def list_memories(args):
    limit = args.get("limit", 20)
    offset = args.get("offset", 0)
    collection_name = args.get("collection")
    collection = _get_collection(collection_name)
    try:
        data = collection.get(include=["metadatas", "documents"])
    except Exception:
        return {"success": True, "results": [], "count": 0}

    result = []
    ids = data.get("ids", [])
    for i in range(min(limit, len(ids))):
        idx = i + offset
        if idx >= len(ids):
            break
        text = (data.get("documents") or [""])[idx][:200]
        meta = (data.get("metadatas") or [{}])[idx]
        result.append({
            "id": ids[idx],
            "text": text,
            "metadata": meta,
            "score": 1.0
        })
    return {"success": True, "results": result, "count": len(result)}


def clear_memories(args):
    collection_name = args.get("collection")
    collection = _get_collection(collection_name)
    try:
        ids = collection.get()["ids"]
        if ids:
            collection.delete(ids=ids)
    except Exception as e:
        print("  ⚠️ 清空失败: %s" % str(e)[:60], file=sys.stderr)
    return {"success": True, "message": "记忆已清空", "count": len(ids) if ids else 0}


def import_from_memory_md(args):
    if not MEMORY_MD.exists():
        return {"success": False, "message": "MEMORY.md 不存在"}
    content = MEMORY_MD.read_text(encoding="utf-8")
    lines = [l.strip() for l in content.split("\n") if l.strip().startswith("- [")]
    added = 0
    for line in lines:
        text = line[3:].strip() if line.startswith("- [") else line
        result = add_memory({"text": text, "metadata": {"imported": True}})
        if result.get("success"):
            added += 1
    return {"success": True, "message": "已导入 %d 条记忆" % added}


def dedupe_memories(args):
    limit = args.get("limit", 1000)
    threshold = args.get("threshold", 0.95)
    collection_name = args.get("collection")
    collection = _get_collection(collection_name)

    try:
        data = collection.get(include=["embeddings"])
        ids = data.get("ids", [])[:limit]
        embs = data.get("embeddings", [])[:limit]
    except Exception:
        return {"success": True, "deduped": 0}

    import numpy as np
    done = set()
    deduped = 0
    for i in range(len(ids)):
        if ids[i] in done:
            continue
        emb1 = np.array(embs[i])
        for j in range(i + 1, len(ids)):
            if ids[j] in done:
                continue
            emb2 = np.array(embs[j])
            sim = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2) + 1e-8)
            if sim > threshold:
                collection.delete(ids=[ids[j]])
                done.add(ids[j])
                deduped += 1
    return {"success": True, "deduped": deduped}
