"""
Vector-Memory 记忆系统 - 搜索模块
负责搜索、重排序、相关记忆检索
支持可配置混合权重、RRF、文件搜索
"""
import os
import sys
import time
import numpy as np
from typing import List, Dict, Optional

from core import (_get_collection, _get_model, _get_reranker, _init_tfidf_vectorizer,
                   _current_collection_name, _hybrid_weights)
from core import _sigmoid_to_score_100, _apply_decay_to_scores, _update_access_time


# 增量 TF-IDF 缓存
_tfidf_cache = {"doc_count": 0, "matrix": None, "vectorizer": None}


def _rebuild_tfidf_if_needed(collection):
    """增量更新 TF-IDF：仅当文档数量增长超过 50% 时全量重训练。"""
    global _tfidf_cache
    try:
        current_count = collection.count()
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


def _reciprocal_rank_fusion(scores_list, k=60):
    """
    Reciprocal Rank Fusion (RRF) 融合多路评分。
    参考: https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf
    
    Args:
        scores_list: 多个评分列表，每个列表包含 (doc_id, score) 元组，已按 score 降序排列
        k: RRF 平滑参数，默认 60
    
    Returns:
        dict: {doc_id: rrf_score}，分数越高排名越靠前
    """
    rrf_scores = {}
    for ranked_list in scores_list:
        for rank, (doc_id, score) in enumerate(ranked_list, 1):
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1.0 / (k + rank)
    return rrf_scores


def search_memories(args):
    text = args.get("text", "")
    top_k = args.get("top_k", 5)
    where = args.get("where")
    collection_name = args.get("collection")
    use_rrf = args.get("use_rrf", _hybrid_weights.get("rrf", False))

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

    # 2. 构建向量评分
    vec_results = {}
    for i, (mem_id, dist, doc, meta) in enumerate(zip(ids, distances, documents, metadatas)):
        vec_score = 1.0 - (dist / 2.0) if dist else 0.0
        vec_results[mem_id] = {
            "id": mem_id,
            "text": doc[:300],
            "metadata": meta,
            "vec_score": vec_score,
        }

    # 3. 混合评分
    weights = _hybrid_weights

    if use_rrf:
        # === RRF 模式 ===
        vec_ranked = [(m["id"], idx) for idx, m in enumerate(
            sorted(vec_results.values(), key=lambda x: x["vec_score"], reverse=True)
        )]

        rrf_inputs = [vec_ranked]

        _rebuild_tfidf_if_needed(collection)
        cache = _tfidf_cache
        if cache["matrix"] is not None and cache["all_docs"]:
            all_docs = cache["all_docs"]
            tfidf_matrix = cache["matrix"]
            vectorizer = cache["vectorizer"]
            query_vec = vectorizer.transform([text])
            tfidf_scores = (tfidf_matrix @ query_vec.T).toarray().flatten()

            doc_id_map = {d: i for i, d in enumerate(all_docs)}
            tfidf_ranked = []
            for mem_id, info in vec_results.items():
                tfidf_idx = doc_id_map.get(info["text"], -1)
                if tfidf_idx >= 0:
                    tfidf_ranked.append((mem_id, float(tfidf_scores[tfidf_idx])))

            tfidf_ranked.sort(key=lambda x: x[1], reverse=True)
            tfidf_ranked = [(tid, idx) for idx, (tid, _) in enumerate(tfidf_ranked)]
            rrf_inputs.append(tfidf_ranked)

        rrf_scores = _reciprocal_rank_fusion(rrf_inputs, k=60)

        for mem_id, info in vec_results.items():
            info["score"] = rrf_scores.get(mem_id, 0)
            info["rrf_score"] = rrf_scores.get(mem_id, 0)

    else:
        # === 传统线性加权模式 ===
        vec_w = weights.get("vec", 0.7)
        tfidf_w = weights.get("tfidf", 0.3)

        _rebuild_tfidf_if_needed(collection)
        cache = _tfidf_cache

        if cache["matrix"] is not None and cache["all_docs"]:
            all_docs = cache["all_docs"]
            tfidf_matrix = cache["matrix"]
            vectorizer = cache["vectorizer"]
            query_vec = vectorizer.transform([text])
            tfidf_scores = (tfidf_matrix @ query_vec.T).toarray().flatten()

            doc_id_map = {d: i for i, d in enumerate(all_docs)}

            for mem_id, info in vec_results.items():
                tfidf_idx = doc_id_map.get(info["text"], -1)
                tfidf_score = float(tfidf_scores[tfidf_idx]) if tfidf_idx >= 0 else 0.0
                info["tfidf_score"] = tfidf_score
                info["score"] = vec_w * info["vec_score"] + tfidf_w * tfidf_score
        else:
            for info in vec_results.values():
                info["score"] = info["vec_score"]

    results = sorted(vec_results.values(), key=lambda x: x.get("score", 0), reverse=True)
    results = results[:top_k]

    # 4. Reranker 重排序
    try:
        reranker = _get_reranker()
        pairs = [(text, r["text"]) for r in results]
        rerank_scores = reranker.predict(pairs)
        for i, r in enumerate(results):
            r["score"] = float(rerank_scores[i])
        results.sort(key=lambda x: x["score"], reverse=True)
    except Exception as e:
        print("  ⚠️ Reranker 重排序降级: %s" % str(e)[:80], file=sys.stderr)

    # 5. 应用衰减分数
    results = _apply_decay_to_scores(results, collection)

    # 6. 添加 0-100 分映射
    for r in results:
        r["relevance_score"] = _sigmoid_to_score_100(r.get("score", 0))
        _update_access_time(r["id"], collection)

    elapsed = time.time() - start
    elapsed_ms = round(elapsed * 1000, 2)

    debug = args.get("debug", False)
    if debug:
        for r in results:
            r["_debug"] = {
                "hybrid_weights": weights.copy(),
                "use_rrf": use_rrf,
            }

    # 自动记录监控数据
    try:
        from memory_monitor import record_search
        record_search(
            query=text,
            results_count=len(results),
            elapsed_ms=elapsed_ms,
            source="vector_memory",
            metadata={"top_k": top_k, "where": where, "hybrid_weights": weights, "use_rrf": use_rrf}
        )
    except Exception:
        pass

    return {"success": True, "results": results, "count": len(results), "elapsed_ms": elapsed_ms}


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


# ============================================================
# ✨ 功能C：文件搜索
# ============================================================

def search_files(args):
    """
    在文件索引中搜索文件。
    
    Args:
        text: 搜索文本
        top_k: 返回数量
        file_type: 按文件类型过滤 (image/document/text)
        collection: 按集合过滤
    
    Returns:
        dict: 文件搜索结果
    """
    from file_storage import search_files as _search_files
    return _search_files(args)