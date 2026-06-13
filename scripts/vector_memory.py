"""
Vector-Memory 记忆系统 v2.5.0（混合存储增强版）
日志全输出到 stderr，stdout 仅返回结果

新增功能：
  1. 嵌入模型热切换 + 自动 reindex
  2. 混合检索权重动态配置（线性加权 / RRF）
  3. 长文档自动摘要生成
  4. 增量备份（基于版本号的内容哈希比对）
  5. 混合文件存储（任意文件 → 物理存储 + ChromaDB 索引）
"""

__version__ = "2.5.0"
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
    CHUNK_SIZE, MODEL_NAME, MODEL_DIR, MEMORY_MD, VECTOR_STORE_DIR, HERMES_HOME,
    # ✨ 新增：热切换
    switch_model, get_model_info,
    # ✨ 新增：混合权重
    set_hybrid_weights, get_hybrid_weights,
    # ✨ 新增：摘要生成
    _generate_summary,
    # ✨ 新增：备份状态
    get_backup_state,
)
from storage import (
    create_collection, list_collections, delete_collection, switch_collection,
    get_current_collection, add_memory, add_batch, add_with_chunks,
    list_memories, clear_memories, import_from_memory_md, dedupe_memories,
    # ✨ 新增：文件操作
    add_file, list_files, get_file, delete_file, search_files, get_file_stats,
)
from search import search_memories, rerank_results, search_related
from management import (
    link_memory, unlink_memory, get_knowledge_chain,
    get_relations, clear_relations,
    get_memory_versions, rollback_memory, clear_version_history, get_version_stats,
    get_access_stats, get_expired_memories, prune_expired_memories,
    export_memories, list_exports, backup_memories, restore_memories, list_backups,
    backup_memories_incremental, restore_incremental,
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
    "get_stats",
    # ✨ 新增导出
    "switch_model", "get_model_info",
    "set_hybrid_weights", "get_hybrid_weights",
    "backup_memories_incremental", "restore_incremental",
    "get_backup_state",
    # ✨ 新增：文件操作导出
    "add_file", "list_files", "get_file", "delete_file", "search_files", "get_file_stats",
]


def _print_file_table(files, highlight=False):
    """以表格形式打印文件列表"""
    if not files:
        print("  (空)")
        return

    # 表头
    print("  {:<36} {:<10} {:<10} {:<8} {:<20} {}".format(
        "FILE_ID", "TYPE", "SIZE", "METHOD", "UPLOAD_TIME", "FILENAME"))
    print("  " + "-" * 110)

    for f in files:
        fid = f.get("file_id", "")[:36]
        ftype = f.get("file_type", "?")[:10]
        size = f.get("file_size_human", "?")[:10]
        method = f.get("extract_method", "?")[:8]
        upload = f.get("upload_time", "?")[:19]
        name = f.get("filename", "?")[:40]
        print("  {:<36} {:<10} {:<10} {:<8} {:<20} {}".format(
            fid, ftype, size, method, upload, name))


def main():
    if len(sys.argv) < 2:
        print("用法: python vector_memory.py <command> [args...]")
        print("命令:")
        print("  记忆:    search, list, add, clear, import, dedupe")
        print("  集合:    create, collections")
        print("  管理:    stats, backup, backup-inc, restore, link, unlink, chain")
        print("  模型:    switch-model, model-info, set-weights")
        print("  摘要:    summary")
        print("  文件:    file-upload, file-list, file-get, file-delete, file-search, file-stats")
        print("  恢复:    restore-inc, backup-state")
        sys.exit(1)

    command = sys.argv[1]
    # 解析 args：key=value 形式，剩余参数作为 text
    args = {}
    text_parts = []
    for a in sys.argv[2:]:
        if "=" in a and not a.startswith("="):
            k, v = a.split("=", 1)
            k = k.lstrip("-")
            args[k] = v
        else:
            text_parts.append(a)

    # ============================================================
    # 记忆相关命令
    # ============================================================
    if command == "search":
        text = args.get("text") or " ".join(text_parts)
        top_k = int(args.get("top_k", 5))
        result = search_memories({"text": text, "top_k": top_k})
        if result.get("success"):
            for r in result.get("results", []):
                score = r.get("score", 0)
                rel = r.get("relevance_score", "")
                txt = r.get("text", "")[:200]
                summary = r.get("metadata", {}).get("summary", "")
                line = "[%.4f | rel:%s] %s" % (score, rel, txt)
                if summary:
                    line += "\n    └─ 摘要: %s" % summary[:100]
                print(line)
            print("--- 共 %d 条结果，耗时 %sms" % (result.get("count", 0), result.get("elapsed_ms", 0)))
        else:
            print(json.dumps(result, ensure_ascii=False), file=sys.stderr)

    elif command == "list":
        print(json.dumps(list_memories({"limit": int(args.get("limit", 20))}), ensure_ascii=False))

    elif command == "add":
        text = args.get("text") or " ".join(sys.argv[2:])
        print(json.dumps(add_memory({"text": text}), ensure_ascii=False))

    elif command == "clear":
        collection = args.get("collection")
        print(json.dumps(clear_memories({"collection": collection}), ensure_ascii=False))

    elif command == "import":
        print(json.dumps(import_from_memory_md({}), ensure_ascii=False))

    elif command == "dedupe":
        threshold = float(args.get("threshold", 0.95))
        limit = int(args.get("limit", 1000))
        print(json.dumps(dedupe_memories({"threshold": threshold, "limit": limit}), ensure_ascii=False))

    # ============================================================
    # 集合相关命令
    # ============================================================
    elif command == "create":
        print(json.dumps(create_collection({"name": args.get("name", "")}), ensure_ascii=False))

    elif command == "collections":
        print(json.dumps(list_collections(), ensure_ascii=False, indent=2))

    # ============================================================
    # 管理命令
    # ============================================================
    elif command == "stats":
        print(json.dumps(get_stats(), ensure_ascii=False, indent=2))

    elif command == "backup":
        print(json.dumps(backup_memories(), ensure_ascii=False))

    elif command == "backup-inc":
        result = backup_memories_incremental()
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif command == "restore":
        print(json.dumps(restore_memories({"backup": args.get("backup", "")}), ensure_ascii=False))

    elif command == "restore-inc":
        result = restore_incremental(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif command == "backup-state":
        result = get_backup_state()
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif command == "link":
        result = link_memory({
            "from_id": args.get("from", ""),
            "to_id": args.get("to", ""),
            "relation": args.get("relation", "related"),
        })
        print(json.dumps(result, ensure_ascii=False))

    elif command == "unlink":
        result = unlink_memory({"from_id": args.get("from", ""), "to_id": args.get("to", "")})
        print(json.dumps(result, ensure_ascii=False))

    elif command == "chain":
        result = get_knowledge_chain({"doc_id": args.get("doc_id", ""), "depth": int(args.get("depth", 1))})
        print(json.dumps(result, ensure_ascii=False, indent=2))

    # ============================================================
    # ✨ 模型热切换
    # ============================================================
    elif command == "switch-model":
        new_model = args.get("model", "")
        if not new_model:
            # 显示当前模型信息
            info = get_model_info()
            print(json.dumps(info, ensure_ascii=False, indent=2))
            print("\n用法: switch-model --model=<新模型名或路径> [--collection=<集合名>]", file=sys.stderr)
            print("示例: switch-model --model=BAAI/bge-m3", file=sys.stderr)
            print("示例: switch-model --model=/path/to/model", file=sys.stderr)
            sys.exit(0)
        collection = args.get("collection")
        kwargs = {"new_model_name": new_model}
        if collection:
            kwargs["collection_name"] = collection
        result = switch_model(**kwargs)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif command == "model-info":
        print(json.dumps(get_model_info(), ensure_ascii=False, indent=2))

    # ============================================================
    # ✨ 混合权重
    # ============================================================
    elif command == "set-weights":
        vec_w = float(args.get("vec", 0.7))
        tfidf_w = float(args.get("tfidf", 0.3))
        use_rrf = args.get("rrf", "false").lower() in ("true", "1", "yes")
        result = set_hybrid_weights(vec_weight=vec_w, tfidf_weight=tfidf_w, use_rrf=use_rrf)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("✅ 权重已更新（当前生效，立即影响后续搜索）", file=sys.stderr)

    # ============================================================
    # ✨ 摘要生成
    # ============================================================
    elif command == "summary":
        text = args.get("text") or " ".join(text_parts)
        if not text:
            print("用法: summary --text=<长文本>", file=sys.stderr)
            sys.exit(1)
        max_sent = int(args.get("max_sentences", 3))
        summary = _generate_summary(text, max_sentences=max_sent)
        print("摘要 (%d 字):" % len(summary))
        print(summary)

    # ============================================================
    # ✨ 混合文件存储
    # ============================================================
    elif command == "file-upload":
        file_path = args.get("file") or args.get("file_path", "")
        if not file_path:
            # 支持位置参数
            file_path = sys.argv[2] if len(sys.argv) > 2 else ""
        if not file_path or not os.path.exists(file_path):
            print("错误: 文件不存在: %s" % file_path, file=sys.stderr)
            sys.exit(1)
        result = add_file({
            "file_path": file_path,
            "description": args.get("description", ""),
            "category": args.get("category", "general"),
            "tags": args.get("tags", "").split(",") if args.get("tags") else [],
            "collection": args.get("collection"),
        })
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif command == "file-list":
        result = list_files({
            "limit": int(args.get("limit", 20)),
            "offset": int(args.get("offset", 0)),
            "collection": args.get("collection"),
            "file_type": args.get("file_type"),
        })
        if result.get("success"):
            files = result.get("files", [])
            total = result.get("total", 0)
            print("共 %d 个文件 (显示 %d):" % (total, len(files)))
            _print_file_table(files)
        else:
            print(json.dumps(result, ensure_ascii=False))

    elif command == "file-get":
        file_id = args.get("file_id", "")
        if not file_id:
            print("用法: file-get --file_id=<id>", file=sys.stderr)
            sys.exit(1)
        result = get_file({"file_id": file_id})
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif command == "file-delete":
        file_id = args.get("file_id", "")
        if not file_id:
            print("用法: file-delete --file_id=<id>", file=sys.stderr)
            sys.exit(1)
        result = delete_file({"file_id": file_id})
        print(json.dumps(result, ensure_ascii=False))

    elif command == "file-search":
        text = args.get("text") or " ".join(text_parts)
        if not text:
            print("用法: file-search --text=<关键词>", file=sys.stderr)
            sys.exit(1)
        result = search_files({
            "text": text,
            "top_k": int(args.get("top_k", 10)),
            "file_type": args.get("file_type"),
            "collection": args.get("collection"),
        })
        if result.get("success"):
            hits = result.get("results", [])
            print("搜索 '%s' → 命中 %d 个文件:" % (text, len(hits)))
            _print_file_table(hits, highlight=True)
        else:
            print(json.dumps(result, ensure_ascii=False))

    elif command == "file-stats":
        result = get_file_stats()
        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        print("未知命令: " + command, file=sys.stderr)
        print("可用命令:", file=sys.stderr)
        print("  记忆:    search, list, add, clear, import, dedupe", file=sys.stderr)
        print("  集合:    create, collections", file=sys.stderr)
        print("  管理:    stats, backup, backup-inc, restore, link, unlink, chain", file=sys.stderr)
        print("  模型:    switch-model, model-info", file=sys.stderr)
        print("  权重:    set-weights", file=sys.stderr)
        print("  摘要:    summary", file=sys.stderr)
        print("  文件:    file-upload, file-list, file-get, file-delete, file-search, file-stats", file=sys.stderr)
        print("  恢复:    restore-inc, backup-state", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()