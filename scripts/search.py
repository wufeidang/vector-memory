"""
Vector-Memory 记忆系统 - 搜索模块
负责搜索、重排序、相关记忆检索
"""
import os
import sys
import time
import numpy as np
from typing import List, Dict, Optional

from core import _get_collection, _get_model, _get_reranker, _init_tfidf_vectorizer, _current_collection_name
from core import _sigmoid_to_score_100, _apply_decay_to_scores, _update_access_time


# 增量 TF-IDF 缓存
_tfidf_cache = {"doc_count": 0, "matrix": None, "vectorizer": None}

def _rebuild_tfidf_if_needed(collection):
    """增量更新 TF-IDF：仅当文档数量增长超过 50% 时全量重训练。"""
    global _tfidf_cache
    try:
        current_count = collection.count()
        # 首次或无缓存 / 增长超过 50% / 减少超过 10%
        if (_tfidf_cache["matrix"] is None
                or current_count == 0
                or (_tfidf_cache["doc_count"] > 0
                    and abs(current_count - _tfidf_cache["doc_count"]) / max(_tfidf_cache["doc_count"], 1) > 0.5)):
            all_docs = collection.get(include=["documents"])["documents"]
            if all_docs and len(all_docs) > 1:
                vectorizer = _init_tfidf_vectorizer()
                matrix = vectorizer.fit_transform(all_docs)
                _tfidf_cache.update({
                    "doc_count": current_count,
                    "matrix": matrix,
                    "vectorizer": vectorizer,
                    "all_docs": all_docs
                })
                return True
        return False
    except Exception:
        return False


def search_memories(args):
    text = args.get("text", "")
    top_k = args.get("top_k", 5)
    where = args.get("where")
    collection_name = args.get("collection")

    if not text:
        return {"success": False, "message": "搜索关键词不能为空"}

    collection = _get_collection(collection_name)
    model = _get_model()

    start = time.time()

    # 1. 向量检索
    try:
        vec = model.encode(text).tolist()
        n_results = top_k * 3
        raw = collection.query(
            query_embeddings=[vec],
            n_results=n_results,
            where=where,
            include=["distances", "metadatas", "documents"]
        )
    except Exception as e:
        return {"success": False, "message": "搜索失败: " + str(e)[:100]}

    ids = raw.get("ids", [[]])[0]
    distances = raw.get("distances", [[]])[0]
    documents = raw.get("documents", [[]])[0]
    metadatas = raw.get("metadatas", [[]])[0]

    if not ids:
        return {"success": True, "results": [], "count": 0}

    # 2. 增量 TF-IDF 后排序
    results = []
    try:
        _rebuild_tfidf_if_needed(collection)
        cache = _tfidf_cache

        if cache["matrix"] is not None and cache["all_docs"]:
            all_docs = cache["all_docs"]
            tfidf_matrix = cache["matrix"]
            vectorizer = cache["vectorizer"]

            # query 向量总是 transform（不会改变词表）
            query_vec = vectorizer.transform([text])
            tfidf_scores = (tfidf_matrix @ query_vec.T).toarray().flatten()

            doc_id_map = {}
            for i, d in enumerate(all_docs):
                doc_id_map[d] = i

            for i, (mem_id, dist, doc, meta) in enumerate(zip(ids, distances, documents, metadatas)):
                vec_score = 1.0 - (dist / 2.0) if dist else 0.0
                tfidf_idx = doc_id_map.get(doc, -1)
                tfidf_score = float(tfidf_scores[tfidf_idx]) if tfidf_idx >= 0 else 0.0
                combined = 0.7 * vec_score + 0.3 * tfidf_score
                results.append({
                    "id": mem_id,
                    "text": doc[:300],
                    "metadata": meta,
                    "score": combined,
                    "vec_score": vec_score,
                    "tfidf_score": tfidf_score
                })
        else:
            for i, (mem_id, dist, doc, meta) in enumerate(zip(ids, distances, documents, metadatas)):
                vec_score = 1.0 - (dist / 2.0) if dist else 0.0
                results.append({
                    "id": mem_id,
                    "text": doc[:300],
                    "metadata": meta,
                    "score": vec_score
                })
    except Exception as e:
        print("  ⚠️ TF-IDF 后排序降级: %s" % str(e)[:80], file=sys.stderr)
        for i, (mem_id, dist, doc, meta) in enumerate(zip(ids, distances, documents, metadatas)):
            vec_score = 1.0 - (dist / 2.0) if dist else 0.0
            results.append({
                "id": mem_id,
                "text": doc[:300],
                "metadata": meta,
                "score": vec_score
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    results = results[:top_k]

    # 3. Reranker 重排序
    try:
        reranker = _get_reranker()
        pairs = [(text, r["text"]) for r in results]
        rerank_scores = reranker.predict(pairs)
        for i, r in enumerate(results):
            r["score"] = float(rerank_scores[i])
        results.sort(key=lambda x: x["score"], reverse=True)
    except Exception as e:
        print("  ⚠️ Reranker 重排序降级: %s" % str(e)[:80], file=sys.stderr)

    # 4. 应用衰减分数
    results = _apply_decay_to_scores(results, collection)

    # 5. 添加 0-100 分映射
    for r in results:
        r["relevance_score"] = _sigmoid_to_score_100(r.get("score", 0))
        _update_access_time(r["id"], collection)

    elapsed = time.time() - start
    return {"success": True, "results": results, "count": len(results), "elapsed_ms": round(elapsed * 1000, 2)}


def rerank_results(query, docs_scores, top_k=5):
    try:
        reranker = _get_reranker()
        pairs = [(query, ds["text"]) for ds in docs_scores]
        scores = reranker.predict(pairs)
        for i, s in enumerate(scores):
            docs_scores[i]["rerank_score"] = float(s)
        docs_scores.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
    except Exception as e:
        print("Rerank failed: %s" % str(e)[:80], file=sys.stderr)
    return docs_scores[:top_k]


def search_related(args):
    doc_id = args.get("doc_id", "")
    limit = args.get("limit", 5)
    collection_name = args.get("collection")

    collection = _get_collection(collection_name)
    try:
        data = collection.get(ids=[doc_id], include=["metadatas"])
        if not data.get("ids"):
            return {"success": True, "related": [], "count": 0}
        related_ids = data["metadatas"][0].get("related_ids", [])
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
