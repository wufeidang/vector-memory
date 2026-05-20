# ChromaDB API 使用注意事项

## 版本信息

- **已测试版本**: ChromaDB 1.5.9
- **Python 版本**: 3.14

## 关键 API 差异

### 1. embeddings 不默认返回

`collection.get()` **不返回 embeddings**，需要显式指定：

```python
# ❌ 错误 - embeddings 为 None
data = collection.get()
print(data['embeddings'])  # None

# ✅ 正确 - 使用 peek() 或指定 include
data = collection.peek()
print(data['embeddings'])  # 返回嵌入向量

# ✅ 或者
data = collection.get(include=['embeddings', 'documents', 'metadatas'])
```

### 2. 距离与相似度转换

ChromaDB 返回的是**余弦距离**，不是相似度：

```python
# ChromaDB 返回的距离
results = collection.query(query_embeddings=[emb], n_results=5)
distances = results['distances'][0]  # 余弦距离

# 转换为相似度
similarities = [1 - d for d in distances]  # 相似度 = 1 - 距离
```

**余弦距离定义**: `distance = 1 - cosine_similarity`

### 3. metadata 不能为空字典

ChromaDB 要求 metadata 是非空字典：

```python
# ❌ 错误 - 空字典会被拒绝
collection.add(ids=["1"], embeddings=[emb], documents=["test"], metadatas=[{}])
# 错误: Expected metadata to be a non-empty dict

# ✅ 正确 - 使用非空字典
collection.add(ids=["1"], embeddings=[emb], documents=["test"], metadatas=[{"_empty": True}])
```

### 4. Collection 对象生命周期

当使用 `client.delete_collection()` 删除集合后，旧的 Collection 对象会失效：

```python
# ❌ 错误 - 旧对象失效
collection = _get_client()
client.delete_collection("memories")
collection.add(...)  # 错误: Collection does not exist

# ✅ 正确 - 清除全局缓存后重新获取
client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
client.delete_collection("memories")
# 清除全局缓存
global _client, _collection
_client = None
_collection = None
# 重新获取
_get_client()
```

### 5. `collection.get(include=...)` 参数限制

`ids` 是**默认返回**的字段，不能在 `include` 参数中指定：

```python
# ❌ 错误 - ChromaDB 报错: "Expected include item to be one of documents, embeddings, metadatas, distances, uris, data, got ids"
data = collection.get(include=['ids', 'embeddings', 'documents', 'metadatas'])

# ✅ 正确 - ids 始终返回，include 中不要写 ids
data = collection.get(include=['embeddings', 'documents', 'metadatas'])
ids = data['ids']  # ids 始终可用
```

### 6. numpy 数组 vs Python list

`collection.get()` 返回的 `embeddings` 是 **numpy 数组**，不是 Python list：

```python
# ❌ 错误 - numpy 数组没有 pop() 方法
embs = data.get('embeddings', [])  # 返回 numpy.ndarray
embs.pop(j)  # AttributeError: 'numpy.ndarray' object has no attribute 'pop'

# ✅ 正确 - 转换为 Python list
embs = [e.tolist() if hasattr(e, 'tolist') else list(e) for e in data.get('embeddings', [])]
embs.pop(j)  # OK
```

## 故障排查历史

### 2026-05-18 调试记录 — 向量化记忆系统完整测试

**场景**: 修复 `vector_memory.py` 脚本的多个 bug，完成 6 项功能测试（清空、添加、列表、搜索、去重、摘要）。

**发现的 Bug 及修复**:

| # | Bug | 原因 | 修复 |
|---|-----|------|------|
| 1 | `dedupe_memories` 缩进错误 | 函数被错误嵌套在 `import_from_memory_md` 内部（4 空格），应为模块级（0 空格） | 提升到模块级 |
| 2 | `generate_daily_summary` 函数名被截断 | 文件损坏，`def generate_daily_summary` 变成 `rate_daily_summary` | 补全 `def ` |
| 3 | `main` 函数名被截断 | 文件损坏，`def main` 变成 `(args):` | 补全 `def ` |
| 4 | `main` 中调用 `dedupe_memories` 缩进错误 | 调用语句缩进为 0（应为 8 空格，在 main 内部） | 修正为 8 空格 |
| 5 | 75 行缩进不一致 | 5/9/11/15 空格等非 4 倍数缩进 | 统一为 4 空格倍数 |
| 6 | `collection.get(include=['ids',...])` 报错 | ChromaDB 不支持 `ids` 在 include 中 | 移除 `ids` |
| 7 | `embs.pop(j)` 报错 | `embeddings` 是 numpy 数组，无 `pop()` 方法 | 转为 Python list |
| 8 | `delete_collection` 后 `collection.add` 报错 | 全局缓存 `_collection` 仍指向已删除的集合 | 清除 `_client` 和 `_collection` 为 None |
| 9 | `np.linalg.norm(embs[i])np.linalg.norm(embs[j])` 报错 | 缺少 `*` 乘号 | 补上 `*` |
| 10 | `import_from_memory_md` 返回 dict 缩进错误 | 返回语句缩进为 4 空格（应为函数内 8 空格） | 修正缩进 |

**修复后测试通过**:
- ✅ 清空记忆
- ✅ 添加 6 条记忆
- ✅ 列出所有记忆（6 条，分类正确）
- ✅ 语义搜索（3 个查询，召回准确）
- ✅ 去重（7→6 条，删除 1 条重复）
- ✅ 生成每日摘要（统计正确）

**关键修复代码**:

```python
# 去重函数中，清除全局缓存
client = collection._client
client.delete_collection("memories")
global _client, _collection
_client = None
_collection = None
if ids:
    _get_client().add(ids=ids, embeddings=embs, documents=docs, metadatas=metas)

# 将 numpy 数组转为 list
embs = [e.tolist() if hasattr(e, 'tolist') else list(e) for e in data.get('embeddings', [])]

# include 参数不要写 ids
data = collection.get(include=['embeddings', 'documents', 'metadatas'])
```

## sklearn TF-IDF 备选模式

当 sentence-transformers 模型不可用时，自动切换到 sklearn TF-IDF：

```python
# 字符级 TF-IDF（支持中文）
vectorizer = TfidfVectorizer(
    max_features=5000,
    analyzer='char',
    ngram_range=(1, 2),
    min_df=1
)
```

**特点**:
- 无需下载模型
- 字符级匹配，对中文有效
- 搜索效果不如语义模型，但比无模型好
- 相似度计算使用 `cosine_similarity`

**使用场景**: 网络不稳定、无法下载模型时的备选方案。

## 最佳实践

### 添加记忆

```python
def add_memory(text, metadata):
    collection = _get_client()
    
    # 确保 metadata 非空
    if not metadata:
        metadata = {"_empty": True}
    
    # 生成嵌入
    emb = _embed(text)
    
    # 添加
    doc_id = str(int(time.time() * 1000))
    collection.add(
        ids=[doc_id],
        embeddings=[emb],
        documents=[text],
        metadatas=[metadata]
    )
```

### 搜索记忆

```python
def search_memories(query, top_k=5):
    model = _get_model()
    collection = _get_client()
    
    # 生成查询嵌入
    query_emb = model.encode(query).tolist()
    
    # 搜索
    results = collection.query(
        query_embeddings=[query_emb],
        n_results=top_k
    )
    
    # 转换距离为相似度
    formatted = []
    for i, doc in enumerate(results['documents'][0]):
        score = 1 - results['distances'][0][i]  # 相似度 = 1 - 距离
        formatted.append({
            "text": doc,
            "score": score
        })
    
    return formatted
```

### 清空集合

```python
def clear_memories():
    client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    
    # 删除集合
    try:
        client.delete_collection("memories")
    except:
        pass
    
    # 重置全局变量
    global _client, _collection
    _client = None
    _collection = None
    
    # 重新创建
    _get_client()
```

## 常见问题

### Q: 为什么 `get()` 返回的 embeddings 是 None？

A: ChromaDB 默认不返回 embeddings 以节省内存。使用 `peek()` 或 `get(include=['embeddings'])`。

### Q: 为什么搜索结果相似度是负数？

A: BGE 等模型使用 L2 归一化，余弦相似度范围是 [-1, 1]。负值表示不相似。

### Q: 为什么删除集合后添加失败？

A: 旧的 Collection 对象已失效。需要清除全局缓存 `_client` 和 `_collection` 为 None，然后重新获取。

### Q: 为什么 metadata 为空字典会报错？

A: ChromaDB 要求 metadata 至少有一个键值对。使用 `{"_empty": True}` 作为占位符。

### Q: 为什么 `get(include=['ids', ...])` 报错？

A: `ids` 是默认返回的字段，不能在 `include` 参数中指定。ChromaDB 只接受 `documents, embeddings, metadatas, distances, uris, data`。