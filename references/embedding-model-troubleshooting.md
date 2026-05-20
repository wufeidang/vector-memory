# 嵌入模型故障排查

## 下载源选择

| 源 | 地址 | 适用场景 |
|----|------|----------|
| ModelScope | `https://www.modelscope.cn` | 国内用户，速度快 ⭐推荐 |
| HuggingFace | `https://huggingface.co` | 国外用户，官方源 |
| HF Mirror | `https://hf-mirror.com` | 国内备用 |

## ModelScope 下载

```bash
# 使用 modelscope 库下载
python -c "from modelscope.hub.snapshot_download import snapshot_download; snapshot_download('AI-ModelScope/bge-base-zh-v1.5')"

# 或使用 hf 命令
hf download AI-ModelScope/bge-base-zh-v1.5 --local-dir ~/.cache/modelscope/hub/AI-ModelScope/bge-base-zh-v1.5
```

## 模型验证

```bash
# 检查关键文件
ls ~/.cache/modelscope/hub/AI-ModelScope/bge-base-zh-v1.5/
# 应包含: pytorch_model.bin 或 model.safetensors, config.json, 1_Pooling/config.json

# 测试加载
python -c "from sentence_transformers import SentenceTransformer; m = SentenceTransformer('~/.cache/modelscope/hub/AI-ModelScope/bge-base-zh-v1.5'); print(m.get_sentence_embedding_dimension())"
```

## 中文模型推荐

| 模型 | 来源 | 说明 |
|------|------|------|
| `AI-ModelScope/bge-base-zh-v1.5` | ModelScope | ⭐ 推荐，中文 BGE 模型，效果优秀 |
| `AI-ModelScope/bge-large-zh-v1.5` | ModelScope | 高精度，大模型（~1.3GB） |
| `AI-ModelScope/all-MiniLM-L6-v2` | ModelScope | 英文模型，中文支持有限 |

**注意**: `shibing624/text2vec-base-chinese` 在 ModelScope 上不存在，请使用 BGE 系列。

## sklearn TF-IDF 备选

当无法使用 sentence-transformers 时，技能自动切换到 sklearn TF-IDF：

```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# 字符级分析（支持中文）
vectorizer = TfidfVectorizer(
    analyzer='char',
    ngram_range=(1, 2),
    max_features=5000
)
```

**优点**: 无需下载模型，立即可用
**缺点**: 仅基于字符匹配，无语义理解