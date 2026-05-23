"""
Vector-Memory 记忆系统 - 核心模块
负责配置、模型加载、TF-IDF、Reranker 等核心功能
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
    
    # 扫描目录查找匹配
    for base_dir in [os.path.join(modelscope_base, "hub"), 
                     os.path.join(modelscope_base, "AI-ModelScope")]:
        if not os.path.exists(base_dir):
            continue
        for root, dirs, files in os.walk(base_dir):
            depth = root.replace(base_dir, "").count(os.sep)
            if depth > 3:
                continue
            for d in dirs:
                if short in d or short.replace(".", "_") in d:
                    full_path = os.path.join(root, d)
                    # 验证是有效的模型目录
                    if (os.path.exists(os.path.join(full_path, "config.json")) or
                        os.path.exists(os.path.join(full_path, "model_file.txt")) or
                        os.path.exists(os.path.join(full_path, "sentence_bert_config.json"))):
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
    
    # 扫描 hub 目录查找匹配
    hub_dir = os.path.join(modelscope_base, "hub")
    if os.path.exists(hub_dir):
        for root, dirs, files in os.walk(hub_dir):
            # 限制深度，避免扫描太深
            depth = root.replace(hub_dir, "").count(os.sep)
            if depth > 3:
                continue
            for d in dirs:
                if model_short in d or model_short.replace(".", "_") in d:
                    full_path = os.path.join(root, d)
                    # 验证是有效的模型目录（有 config.json 或 model_file.txt）
                    if (os.path.exists(os.path.join(full_path, "config.json")) or
                        os.path.exists(os.path.join(full_path, "model_file.txt")) or
                        os.path.exists(os.path.join(full_path, "sentence_bert_config.json"))):
                        return full_path
    
    # 扫描 AI-ModelScope 目录
    ai_dir = os.path.join(modelscope_base, "AI-ModelScope")
    if os.path.exists(ai_dir):
        for root, dirs, files in os.walk(ai_dir):
            depth = root.replace(ai_dir, "").count(os.sep)
            if depth > 2:
                continue
            for d in dirs:
                if model_short in d or model_short.replace(".", "_") in d:
                    full_path = os.path.join(root, d)
                    if (os.path.exists(os.path.join(full_path, "config.json")) or
                        os.path.exists(os.path.join(full_path, "model_file.txt")) or
                        os.path.exists(os.path.join(full_path, "sentence_bert_config.json"))):
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
                    snapshot_download(MODEL_NAME, local_dir=MODEL_DIR)
                except Exception as e:
                    print("❌ 模型下载失败: %s" % str(e), file=sys.stderr)
                    raise RuntimeError("模型下载失败: %s" % str(e))
                # After download, scan the directory to find the actual model path
                path = _find_downloaded_model()
                if path is None:
                    raise RuntimeError("模型下载后仍无法找到路径，请检查 ~/.cache/modelscope")
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
                print("\u2705 下载 reranker: %s" % reranker_name, file=sys.stderr)
                snapshot_download(reranker_name, local_dir=MODEL_DIR)
                reranker_path = _check_local_model(reranker_name)
            print("\u2705 加载 reranker: %s" % reranker_path, file=sys.stderr)
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
    """同步一条记忆到 MEMORY.md（从 management 移入 core 解决循环引用）。"""
    MEMORY_MD.parent.mkdir(parents=True, exist_ok=True)
    line = "- [ ] %s" % text
    with MEMORY_MD.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
