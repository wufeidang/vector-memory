"""
Vector-Memory 记忆系统 v2.1（模块化重构版）
日志全输出到 stderr，stdout 仅返回结果
"""

__version__ = "2.1.0"
import os, sys, time, json, hashlib, re, math

_scripts_dir = os.path.dirname(os.path.abspath(__file__))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from core import (
    _sync_to_memory_md,
    _get_chroma_client, _get_collection, _get_model, _get_reranker,
    _get_preferred_model, _check_local_model,
    _init_tfidf_vectorizer, _sigmoid_to_score_100,
    _compute_decay_weight, _update_access_time, _apply_decay_to_scores,
    _current_collection_name,
    _client, _collection, _model, _vectorizer, _reranker, _reranker_model_path,
    CHUNK_SIZE, MODEL_NAME, MODEL_DIR, MEMORY_MD, VECTOR_STORE_DIR, HERMES_HOME
)
from storage import (
    create_collection, list_collections, delete_collection, switch_collection,
    get_current_collection, add_memory, add_batch, add_with_chunks,
    list_memories, clear_memories, import_from_memory_md, dedupe_memories
)
from search import search_memories, rerank_results, search_related
from management import (
    link_memory, unlink_memory, get_knowledge_chain,
    get_relations, clear_relations,
    get_memory_versions, rollback_memory, clear_version_history, get_version_stats,
    get_access_stats, get_expired_memories, prune_expired_memories,
    export_memories, list_exports, backup_memories, restore_memories, list_backups,
    get_stats
)

__all__ = [
    "create_collection", "list_collections", "delete_collection", "switch_collection",
    "get_current_collection",
    "add_memory", "add_batch", "add_with_chunks", "list_memories", "clear_memories",
    "import_from_memory_md", "dedupe_memories",
    "search_memories", "rerank_results", "search_related",
    "link_memory", "unlink_memory", "get_knowledge_chain", "get_relations", "clear_relations",
    "get_memory_versions", "rollback_memory", "clear_version_history", "get_version_stats",
    "get_access_stats", "get_expired_memories", "prune_expired_memories",
    "export_memories", "list_exports", "backup_memories", "restore_memories", "list_backups",
    "get_stats"
]


def main():
    if len(sys.argv) < 2:
        print("\u7528\u6cd5: python vector_memory.py <command> [args...]")
        print("\u547d\u4ee4: search, list, add, stats, backup, create, restore")
        sys.exit(1)

    command = sys.argv[1]
    # 解析 args：key=value 形式，剩余参数作为 text
    args = {}
    text_parts = []
    for a in sys.argv[2:]:
        if "=" in a and not a.startswith("="):
            k, v = a.split("=", 1)
            args[k] = v
        else:
            text_parts.append(a)

    if command == "search":
        text = args.get("text") or " ".join(text_parts)
        result = search_memories({"text": text, "top_k": 5})
        if result.get("success"):
            for r in result.get("results", []):
                score = r.get("score", 0)
                txt = r.get("text", "")[:200]
                print("[%.4f] %s" % (score, txt))
        else:
            print(json.dumps(result, ensure_ascii=False))
    elif command == "list":
        print(json.dumps(list_memories({"limit": int(args.get("limit", 20))}), ensure_ascii=False))
    elif command == "add":
        text = args.get("text") or " ".join(sys.argv[2:])
        print(json.dumps(add_memory({"text": text}), ensure_ascii=False))
    elif command == "stats":
        print(json.dumps(get_stats(), ensure_ascii=False))
    elif command == "backup":
        print(json.dumps(backup_memories(), ensure_ascii=False))
    elif command == "create":
        print(json.dumps(create_collection({"name": args.get("name", "")}), ensure_ascii=False))
    elif command == "restore":
        print(json.dumps(restore_memories({"backup": args.get("backup", "")}), ensure_ascii=False))
    else:
        print("\u672a\u77e5\u547d\u4ee4: " + command, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
