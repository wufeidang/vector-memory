"""
Vector-Memory 记忆系统 - 核心模块
负责配置、模型加载、TF-IDF、Reranker、模型热切换、摘要生成、混合检索权重
"""
import os
import sys
import time
import json
import re
import math
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

# 线程锁（全局变量并发安全）
_client_lock = threading.Lock()
_collection_lock = threading.Lock()
_model_lock = threading.Lock()
_vectorizer_lock = threading.Lock()
_reranker_lock = threading.Lock()

HERMES_HOME = os.path.abspath(os.path.expanduser("~/.hermes"))
MEMORY_MD = Path(os.path.expanduser("~/.hermes/memories/MEMORY.md"))
VECTOR_STORE_DIR = Path(os.path.expanduser("~/.hermes/vector_store"))
MODEL_NAME = "AI-ModelScope/bge-base-zh-v1.5"
MODEL_DIR = os.path.expanduser("~/.cache/modelscope/hub")
CHUNK_SIZE = 800

# ============================================================
# 可配置混合检索权重（默认 0.7 向量 + 0.3 TF-IDF）
# 可通过 set_hybrid_weights() 动态调整
# ============================================================
_hybrid_weights = {"vec": 0.7, "tfidf": 0.3, "rrf": False}

# ============================================================
# 模型热切换状态
# ============================================================
_model_switch_log = []

_client = None
_collection = None
_model = None
_vectorizer = None
_reranker = None
_reranker_model_path = None
_current_collection_name = "memories"


def _get_chroma_client():
    global _client
    if _client is not None:
        return _client
    with _client_lock:
        if _client is None:
            import chromadb
            CHROMA_PERSIST_DIR = os.path.join(os.path.expanduser("~"), ".hermes", "vector_store")
            os.makedirs(CHROMA_PERSIST_DIR, exist_ok=True)
            _client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    return _client


def _get_collection(collection_name=None):
    global _collection, _current_collection_name
    name = collection_name or _current_collection_name
    if _collection is not None and _current_collection_name == name:
        return _collection
    with _collection_lock:
        if _collection is None or _current_collection_name != name:
            client = _get_chroma_client()
            _collection = client.get_or_create_collection(name=name)
            _current_collection_name = name
    return _collection


def _check_local_model(model_name=MODEL_NAME):
    """检查本地是否有已下载的模型，使用扫描方式查找"""
    short = model_name.split("/")[-1]
    modelscope_base = os.path.expanduser("~/.cache/modelscope")

    # 首先检查标准路径
    standard_paths = [
        os.path.join(modelscope_base, "hub", "AI-ModelScope", short),
        os.path.join(modelscope_base, "hub", "AI-ModelScope", short.replace(".", "_")),
        os.path.join(modelscope_base, "AI-ModelScope", short),
        os.path.join(modelscope_base, "AI-ModelScope", short.replace(".", "_")),
    ]
    for path in standard_paths:
        path = os.path.abspath(path)
        if os.path.exists(path) and os.path.isdir(path):
            return path

    # 扫描整个 modelscope 目录查找匹配（无深度限制）
    if os.path.exists(modelscope_base):
        for root, dirs, files in os.walk(modelscope_base):
            # 跳过临时目录和锁文件
            if "._____temp" in root or ".lock" in root or "__pycache__" in root:
                continue
            for d in dirs:
                # 精确匹配模型名（支持点号和下划线变体）
                if short == d or short.replace(".", "_") == d:
                    full_path = os.path.join(root, d)
                    if os.path.isdir(full_path):
                        return full_path

    return None


def _get_preferred_model():
    # 检查多个可能路径（修复 Windows 路径问题）
    model_short = MODEL_NAME.split("/")[-1]
    modelscope_base = os.path.expanduser("~/.cache/modelscope")
    candidates = [
        # 标准路径：hub/AI-ModelScope/model-name
        os.path.join(modelscope_base, "hub", "AI-ModelScope", model_short),
        # 替代路径：AI-ModelScope/model-name（无 hub）
        os.path.join(modelscope_base, "AI-ModelScope", model_short),
        # 带下划线的模型名（某些下载工具会替换点）
        os.path.join(modelscope_base, "hub", "AI-ModelScope", model_short.replace(".", "_")),
        os.path.join(modelscope_base, "AI-ModelScope", model_short.replace(".", "_")),
        # 直接路径检查
        os.path.join(modelscope_base, "hub", MODEL_NAME.replace("/", os.sep).replace(".", "_")),
        os.path.join(modelscope_base, MODEL_NAME.replace("/", os.sep).replace(".", "_")),
    ]
    # 规范化路径
    candidates = [os.path.abspath(p) for p in candidates]
    for path in candidates:
        if os.path.exists(path) and os.path.isdir(path):
            return path
    return None


def _find_downloaded_model():
    """扫描目录找到实际下载的模型路径（用于 snapshot_download 后）"""
    model_short = MODEL_NAME.split("/")[-1]
    modelscope_base = os.path.expanduser("~/.cache/modelscope")

    # 首先检查标准路径
    standard_paths = [
        os.path.join(modelscope_base, "hub", "AI-ModelScope", model_short),
        os.path.join(modelscope_base, "hub", "AI-ModelScope", model_short.replace(".", "_")),
        os.path.join(modelscope_base, "AI-ModelScope", model_short),
        os.path.join(modelscope_base, "AI-ModelScope", model_short.replace(".", "_")),
    ]
    for path in standard_paths:
        if os.path.exists(path) and os.path.isdir(path):
            return path

    # 扫描整个 modelscope 目录查找匹配（无深度限制）
    if os.path.exists(modelscope_base):
        for root, dirs, files in os.walk(modelscope_base):
            # 跳过临时目录和锁文件
            if "._____temp" in root or ".lock" in root or "__pycache__" in root:
                continue
            for d in dirs:
                # 匹配模型名（支持点号和下划线变体）
                if model_short == d or model_short.replace(".", "_") == d:
                    full_path = os.path.join(root, d)
                    # 只要目录存在就返回，不验证内容
                    if os.path.isdir(full_path):
                        return full_path

    return None


def _get_model(model_path=None):
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is None:
            from sentence_transformers import SentenceTransformer
            path = model_path or _get_preferred_model()
            if path is None:
                from modelscope.hub.snapshot_download import snapshot_download
                print("✅ 下载模型: %s" % MODEL_NAME, file=sys.stderr)
                try:
                    # snapshot_download 返回实际下载路径，直接使用
                    path = snapshot_download(MODEL_NAME, local_dir=MODEL_DIR)
                    print("   下载路径: %s" % path, file=sys.stderr)
                except Exception as e:
                    print("❌ 模型下载失败: %s" % str(e), file=sys.stderr)
                    raise RuntimeError("模型下载失败: %s" % str(e))
                if path is None or not os.path.exists(path):
                    raise RuntimeError("模型下载失败：返回路径无效")
            print("✅ 加载嵌入模型: %s" % path, file=sys.stderr)
            try:
                _model = SentenceTransformer(path, device="cpu")
                _model.max_seq_length = 512
            except Exception as e:
                print("❌ 模型加载失败: %s" % str(e), file=sys.stderr)
                raise RuntimeError("模型加载失败: %s" % str(e))
    return _model


def _init_tfidf_vectorizer():
    global _vectorizer
    if _vectorizer is not None:
        return _vectorizer
    with _vectorizer_lock:
        if _vectorizer is None:
            from sklearn.feature_extraction.text import TfidfVectorizer
            _vectorizer = TfidfVectorizer(ngram_range=(1, 2), analyzer="char", min_df=1)
    return _vectorizer


def _get_reranker():
    global _reranker, _reranker_model_path
    if _reranker is not None:
        return _reranker
    with _reranker_lock:
        if _reranker is None:
            from sentence_transformers import CrossEncoder
            reranker_name = "AI-ModelScope/bge-reranker-v2-m3"
            reranker_path = _check_local_model(reranker_name)
            if reranker_path is None:
                from modelscope.hub.snapshot_download import snapshot_download
                print("✅ 下载 reranker: %s" % reranker_name, file=sys.stderr)
                # 直接使用 snapshot_download 返回值
                reranker_path = snapshot_download(reranker_name, local_dir=MODEL_DIR)
                if reranker_path is None or not os.path.exists(reranker_path):
                    raise RuntimeError("reranker 下载失败")
                print("   下载路径: %s" % reranker_path, file=sys.stderr)
            print("✅ 加载 reranker: %s" % reranker_path, file=sys.stderr)
            _reranker = CrossEncoder(reranker_path, device="cpu")
            _reranker_model_path = reranker_path
    return _reranker


def _sigmoid_to_score_100(score):
    return round(50 * (1 + math.tanh(score * 2)), 2)


def _compute_decay_weight(last_access, half_life_days=30):
    now = time.time()
    days_since_access = (now - last_access) / (24 * 3600)
    return math.exp(-days_since_access * math.log(2) / half_life_days)


def _update_access_time(memory_id, collection=None):
    if collection is None:
        collection = _get_collection()
    try:
        meta = collection.get(ids=[memory_id], include=["metadatas"])["metadatas"][0]
        meta["last_accessed"] = time.time()
        collection.update(ids=[memory_id], metadatas=[meta])
    except Exception as e:
        print("  ⚠️ _update_access_time 失败: %s" % str(e)[:60], file=sys.stderr)


def _apply_decay_to_scores(results, collection=None):
    for r in results:
        memory_id = r.get("id")
        if memory_id:
            try:
                meta = collection.get(ids=[memory_id], include=["metadatas"])["metadatas"][0]
                last_access = meta.get("last_accessed", time.time())
                decay = _compute_decay_weight(last_access)
                r["score"] = r.get("score", 0) * decay
            except Exception as e:
                print("  ⚠️ 衰减计算失败: %s" % str(e)[:60], file=sys.stderr)
    return results


def _sync_to_memory_md(text, metadata=None):
    """同步一条记忆到 MEMORY.md（从 management 移入 core 解决循环引用）"""
    MEMORY_MD.parent.mkdir(parents=True, exist_ok=True)
    line = "- [ ] %s" % text
    with MEMORY_MD.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


# ============================================================
# 功能 1：嵌入模型热切换
# ============================================================

def switch_model(new_model_name, collection_name=None):
    """
    运行时更换嵌入模型并触发全量 reindex。
    
    Args:
        new_model_name: 新模型名称（如 "BAAI/bge-m3"）或本地路径
        collection_name: 要 reindex 的集合，None 表示所有集合
    
    Returns:
        dict: 操作结果，包含 reindex 统计信息
    """
    global MODEL_NAME, _model, _model_switch_log

    old_model_name = MODEL_NAME

    # 1. 卸载旧模型
    with _model_lock:
        _model = None

    # 2. 更新模型名称并加载新模型
    MODEL_NAME = new_model_name
    try:
        new_model = _get_model()
    except Exception as e:
        # 恢复旧模型
        MODEL_NAME = old_model_name
        _get_model()
        return {
            "success": False,
            "message": "新模型加载失败，已回退到旧模型: %s" % str(e)[:100]
        }

    # 3. 获取需要 reindex 的集合列表
    client = _get_chroma_client()
    if collection_name:
        collections_to_reindex = [collection_name]
    else:
        collections_to_reindex = [c.name for c in client.list_collections()]

    result = {
        "success": True,
        "old_model": old_model_name,
        "new_model": new_model_name,
        "collections_reindexed": {},
        "total_docs_reindexed": 0,
    }

    # 4. 逐集合 reindex
    old_collection_name = _current_collection_name
    for col_name in collections_to_reindex:
        try:
            # 切换到目标集合
            _current_collection_name = col_name
            collection = _get_collection(col_name)

            # 获取所有文档
            data = collection.get(include=["documents", "metadatas"])
            ids = data.get("ids", [])
            docs = data.get("documents", [])
            metadatas = data.get("metadatas", [])

            if not ids:
                result["collections_reindexed"][col_name] = {"count": 0, "status": "empty"}
                continue

            # 清除旧嵌入
            collection.delete(ids=ids)

            # 用新模型重新生成嵌入并写回
            batch_size = 100
            new_ids = []
            for i in range(0, len(ids), batch_size):
                batch_end = min(i + batch_size, len(ids))
                batch_docs = docs[i:batch_end]
                batch_meta = metadatas[i:batch_end]
                batch_ids = ids[i:batch_end]

                embeddings = new_model.encode(batch_docs).tolist()
                collection.add(
                    ids=batch_ids,
                    embeddings=embeddings,
                    documents=batch_docs,
                    metadatas=batch_meta
                )
                new_ids.extend(batch_ids)

            result["collections_reindexed"][col_name] = {
                "count": len(ids),
                "status": "success"
            }
            result["total_docs_reindexed"] += len(ids)

        except Exception as e:
            result["collections_reindexed"][col_name] = {
                "count": 0,
                "status": "failed",
                "error": str(e)[:100]
            }

    # 恢复原集合
    _current_collection_name = old_collection_name

    # 5. 记录切换日志
    _model_switch_log.append({
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "old_model": old_model_name,
        "new_model": new_model_name,
        "total_docs": result["total_docs_reindexed"],
    })

    result["switch_history"] = _model_switch_log[-5:]  # 保留最近5条
    return result


def get_model_info():
    """获取当前模型信息"""
    return {
        "current_model": MODEL_NAME,
        "model_loaded": _model is not None,
        "model_dir": MODEL_DIR,
        "switch_history": _model_switch_log[-5:],
    }


# ============================================================
# 功能 2：混合检索权重配置
# ============================================================

def set_hybrid_weights(vec_weight=0.7, tfidf_weight=0.3, use_rrf=False):
    """
    动态设置混合检索权重。
    
    Args:
        vec_weight: 向量检索权重（0-1）
        tfidf_weight: TF-IDF 权重（0-1）
        use_rrf: 是否使用 Reciprocal Rank Fusion 替代线性加权
    
    Returns:
        dict: 当前权重配置
    """
    global _hybrid_weights
    total = vec_weight + tfidf_weight
    if total > 0:
        vec_weight = round(vec_weight / total, 4)
        tfidf_weight = round(tfidf_weight / total, 4)
    _hybrid_weights = {
        "vec": vec_weight,
        "tfidf": tfidf_weight,
        "rrf": use_rrf,
    }
    return _hybrid_weights


def get_hybrid_weights():
    """获取当前混合检索权重配置"""
    return _hybrid_weights.copy()


# ============================================================
# 功能 3：长文档摘要生成
# ============================================================

def _generate_summary(text, max_sentences=3):
    """
    从长文本中提取关键句子作为摘要。
    使用简单的基于句子位置+长度的启发式方法，
    不依赖外部摘要模型以避免额外依赖。
    
    Args:
        text: 原始文本
        max_sentences: 最多提取的句子数
    
    Returns:
        str: 生成的摘要
    """
    if len(text) <= 500:
        return text[:200]

    # 按句号、问号、感叹号分割句子
    sentences = re.split(r'(?<=[。！？.!?])\s*', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if len(sentences) <= max_sentences:
        return text[:300]

    # 启发式评分：
    # 1. 靠前句子权重更高（信息密度大）
    # 2. 包含数字/专有名词的句子更可能是关键信息
    # 3. 较长但不冗长的句子更可能是主题句
    scored = []
    for i, sent in enumerate(sentences):
        if len(sent) < 10 or len(sent) > 500:
            continue
        score = 0.0

        # 位置权重：越靠前分越高
        position_score = max(0, 1.0 - (i / len(sentences)) * 0.6)
        score += position_score * 0.4

        # 长度适中（接近 chunk_size/3 最佳）
        ideal_len = CHUNK_SIZE // 3
        len_ratio = min(len(sent), ideal_len * 2) / (ideal_len * 2)
        score += len_ratio * 0.2

        # 包含数字（通常是参数、型号等关键信息）
        has_numbers = bool(re.search(r'\d+', sent))
        if has_numbers:
            score += 0.2

        # 包含技术关键词
        tech_keywords = ['型号', '配置', '参数', '版本', '故障', '解决',
                        '设置', '问题', '错误', '代码', '接口', '协议',
                        '型号', '品牌', '芯片', '内存', '硬盘', '网络',
                        'device', 'model', 'version', 'error', 'config',
                        'IP', 'MAC', 'CPU', 'RAM', 'ROM', 'USB']
        keyword_count = sum(1 for kw in tech_keywords if kw.lower() in sent.lower())
        score += min(keyword_count * 0.05, 0.2)

        scored.append((score, i, sent))

    # 按评分排序，取 top N
    scored.sort(key=lambda x: x[0], reverse=True)
    selected = sorted(scored[:max_sentences], key=lambda x: x[1])  # 保持原文顺序
    summary = "。".join(s[2] for s in selected)

    # 确保摘要不超过 300 字
    if len(summary) > 300:
        summary = summary[:297] + "..."

    return summary


def _summarize_if_needed(text, metadata=None):
    """
    根据文本长度决定是否生成摘要，并将摘要存入 metadata。
    不会覆盖已有的摘要。
    """
    meta = metadata.copy() if metadata else {}
    if "summary" not in meta and len(text) > 500:
        meta["summary"] = _generate_summary(text)
    elif "summary" not in meta:
        meta["summary"] = text[:200]
    return meta


# ============================================================
# 功能 4：增量备份状态管理
# ============================================================

_BACKUP_STATE_PATH = VECTOR_STORE_DIR / "backup_state.json"


def _load_backup_state():
    """加载上次备份状态"""
    if _BACKUP_STATE_PATH.exists():
        try:
            return json.loads(_BACKUP_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_backup_state(state):
    """保存备份状态"""
    _BACKUP_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _BACKUP_STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def get_backup_state():
    """获取当前备份状态"""
    state = _load_backup_state()
    return {
        "success": True,
        "last_full_backup": state.get("last_full_backup"),
        "last_full_backup_time": state.get("last_full_backup_time"),
        "incremental_count": len(state.get("incremental_backups", [])),
        "last_incremental": state.get("incremental_backups", [{}])[-1] if state.get("incremental_backups") else None,
        "tracked_doc_count": len(state.get("backed_up_ids", {})),
    }