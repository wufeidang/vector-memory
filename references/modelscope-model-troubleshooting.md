# ModelScope 模型下载与使用指南

## 模型源对比

| 平台 | 地址 | 速度（国内） | 推荐模型 |
|------|------|-------------|----------|
| ModelScope（魔搭） | https://www.modelscope.cn | ⭐⭐⭐⭐⭐ 快 | AI-ModelScope/* |
| HuggingFace | https://huggingface.co | ⭐⭐ 慢/不稳定 | sentence-transformers/* |

## 已验证可用的中文模型

### BGE 系列（推荐）

| 模型 | ModelScope ID | 维度 | 大小 | 效果 |
|------|---------------|------|------|------|
| BGE Base 中文 v1.5 | `AI-ModelScope/bge-base-zh-v1.5` | 768 | ~391 MB | ⭐⭐⭐⭐⭐ |
| BGE Large 中文 v1.5 | `AI-ModelScope/bge-large-zh-v1.5` | 1024 | ~1.3 GB | ⭐⭐⭐⭐⭐+ |

### 下载命令

```bash
# BGE Base 中文（推荐，平衡速度与精度）
python -c "from modelscope.hub.snapshot_download import snapshot_download; snapshot_download('AI-ModelScope/bge-base-zh-v1.5')"

# BGE Large 中文（高精度，大文件）
python -c "from modelscope.hub.snapshot_download import snapshot_download; snapshot_download('AI-ModelScope/bge-large-zh-v1.5')"
```

## 目录名问题

ModelScope 下载的模型目录中，版本号中的点 `.` 会被替换为下划线 `_`：

| 原始名称 | 实际目录名 |
|----------|------------|
| `bge-base-zh-v1.5` | `bge-base-zh-v1___5` |
| `all-MiniLM-L6-v2` | `all-MiniLM-L6-v2`（无点，不变） |

**代码中检测模型时应处理此转换**：
```python
def _check_local_model(model_name):
    # ModelScope 目录名中的 '.' 被替换为 '___'
    modelscope_dir_name = model_name.replace('.', '___')
    modelscope_cache = os.path.join(
        os.path.expanduser('~'), '.cache', 'modelscope', 'hub',
        'AI-ModelScope', modelscope_dir_name
    )
    # ...
```

## BGE 模型特性

- **池化方式**: CLS token 池化
- **归一化**: L2 归一化
- **相似度范围**: [-1, 1]
- **中文优化**: 专为中文语义理解训练

## 与 all-MiniLM-L6-v2 对比

| 特性 | BGE Base 中文 | all-MiniLM-L6-v2 |
|------|---------------|------------------|
| 训练数据 | 中文为主 | 英文为主 |
| 中文搜索 | ✅ 准确 | ❌ 仅关键词匹配 |
| 维度 | 768 | 384 |
| 大小 | ~391 MB | ~932 MB (ModelScope 完整包) |
| 下载源 | ModelScope | HuggingFace / ModelScope |

**重要**: ModelScope 下载的 all-MiniLM-L6-v2 包含完整模型文件（~932 MB），远大于 HuggingFace 的 ~80 MB。BGE Base 中文（~391 MB）在中文搜索上效果显著更好，是更优选择。

## 搜索结果示例

使用 BGE Base 中文模型：

```
搜索 '用户偏好':
  [0.455] 用户偏好使用中文交流 ✅ 正确匹配
  [0.052] 用户对记忆系统的自动化维护感兴趣
  [-0.074] 需要实现双向同步功能

搜索 '数据库':
  [0.135] 项目使用 ChromaDB 作为向量数据库 ✅ 正确匹配
```

使用 all-MiniLM-L6-v2（英文模型）：

```
搜索 '用户偏好':
  [0.683] 用户对记忆系统的自动化维护感兴趣 ❌ 错误匹配（仅因含"用户"）
  [0.416] 用户偏好使用中文交流
```

## 故障排查

### 模型下载失败

1. 检查网络连接
2. 尝试使用 `hf-mirror.com` 镜像（HuggingFace）
3. 使用 ModelScope 作为备选（国内速度快）

### 模型加载失败

1. 检查 `pytorch_model.bin` 或 `model.safetensors` 是否存在
2. 检查 `config.json` 和 `1_Pooling/config.json` 是否存在
3. 确保 sentence-transformers 版本 >= 2.2.0

### 搜索结果不准确

1. 确认使用的是中文模型（BGE/M3E）而非英文模型
2. 检查相似度计算是否正确（BGE 使用 1 - distance）
3. 考虑使用 `bge-large-zh-v1.5` 获得更高精度

### ModelScope 模型目录名

ModelScope 下载的模型目录中，版本号中的点 `.` 会被替换为下划线 `_`：

| 原始名称 | 实际目录名 |
|----------|------------|
| `bge-base-zh-v1.5` | `bge-base-zh-v1___5` |
| `bge-large-zh-v1.5` | `bge-large-zh-v1___5` |

**代码中检测模型时应处理此转换**：
```python
def _check_local_model(model_name):
    # ModelScope 目录名中的 '.' 被替换为 '___'
    modelscope_dir_name = model_name.replace('.', '___')
    modelscope_cache = os.path.join(
        os.path.expanduser('~'), '.cache', 'modelscope', 'hub',
        'AI-ModelScope', modelscope_dir_name
    )
    # ...
```