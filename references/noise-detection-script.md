# 噪声检测脚本（daily_noise_summary.py）

## 功能

检测向量库中的重复/相似记忆，生成检测报告。

## 脚本位置

`~/.hermes/scripts/daily_noise_summary.py`

## 使用

```bash
# 手动运行
python ~/.hermes/scripts/daily_noise_summary.py
```

## 输出

报告保存在 `~/.hermes/reports/noise_summary_YYYYMMDD_HHMMSS.md`

## 实现要点

### 1. 使用本地模型

脚本使用本地 BGE 中文模型，**不依赖网络**：

```python
from pathlib import Path
SKILL_DIR = Path.home() / ".hermes" / "skills" / "vector_memory"
sys.path.insert(0, str(SKILL_DIR))
from scripts.vector_memory import list_memories
```

### 2. API 调用格式

```python
# ✅ 正确：传入字典
result = list_memories({"limit": 1000})

# ❌ 错误：关键字参数
result = list_memories(limit=1000)  # TypeError
```

### 3. 解析返回结果

```python
memories = []
for item in result.get("results", []):
    memories.append({
        "content": item.get("text", ""),
        "category": item.get("metadata", {}).get("category", "uncategorized"),
        "timestamp": item.get("metadata", {}).get("timestamp", ""),
        "id": item.get("metadata", {}).get("id", ""),
    })
```

### 4. 重复检测

- **精确匹配**：内容完全相同
- **相似度匹配**：需要 embedding，当前版本仅检测精确重复

## 故障排查

### 文件损坏问题

Windows 上文件可能被损坏为二进制数据。检查方法：

```python
with open("daily_noise_summary.py", "rb") as f:
    content = f.read()
    print(content[:100])  # 应该是 Python 代码，不是乱码
```

如果文件损坏，直接删除并重新创建：

```python
import os
os.remove("daily_noise_summary.py")
# 然后重新写入正确内容
```

### 模型加载失败

确保 BGE 模型已下载：

```python
from pathlib import Path
model_path = Path.home() / ".cache" / "modelscope" / "hub" / "AI-ModelScope" / "bge-base-zh-v1.5"
print(f"模型存在: {model_path.exists()}")
```
