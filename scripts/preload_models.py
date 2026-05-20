#!/usr/bin/env python3
"""
模型预加载脚本 - 在 Hermes 启动时将向量模型加载到内存/GPU
"""
import sys
import os
import time

# 添加 vector_memory 脚本目录到 Python 路径
vm_scripts = os.path.expanduser(r'~/.hermes\skills\vector_memory\scripts')
if not os.path.exists(vm_scripts):
    vm_scripts = os.path.join(os.path.expanduser('~'), '.hermes', 'skills', 'vector_memory', 'scripts')
sys.path.insert(0, vm_scripts)

print("=" * 50)
print("预加载记忆系统模型")
print("=" * 50)

total_start = time.time()

# 1. 加载嵌入模型 (bge-base-zh-v1.5)
print("\n[1/2] 加载嵌入模型 bge-base-zh-v1.5...")
start = time.time()

try:
    import vector_memory
    model = vector_memory._get_model()
    elapsed = time.time() - start
    print(f"  ✅ 嵌入模型加载成功 ({elapsed:.1f}s)")
    print(f"  模型: {model}")
except Exception as e:
    print(f"  ❌ 嵌入模型加载失败: {str(e)[:200]}")
    sys.exit(1)

# 2. 加载重排序模型 (bge-reranker-v2-m3)
print(f"\n[2/2] 加载重排序模型 bge-reranker-v2-m3...")
start = time.time()

try:
    reranker = vector_memory._get_reranker()
    elapsed = time.time() - start
    print(f"  ✅ 重排序模型加载成功 ({elapsed:.1f}s)")
except Exception as e:
    print(f"  ⚠️ 重排序模型加载失败: {str(e)[:200]}")
    print("  搜索功能仍然可用（无重排序）")

# 3. 验证：执行一次空搜索确保一切正常
print(f"\n[验证] 执行测试搜索...")
start = time.time()
try:
    result = vector_memory.search_memories({'text': '测试', 'top_k': 1})
    elapsed = time.time() - start
    if result.get('success'):
        print(f"  ✅ 搜索测试通过 ({elapsed:.1f}s)")
    else:
        print(f"  ⚠️ 搜索返回异常: {result.get('message', 'unknown')}")
except Exception as e:
    print(f"  ⚠️ 搜索测试失败: {str(e)[:200]}")

total_time = time.time() - total_start
print(f"\n{'=' * 50}")
print(f"模型预加载完成，总耗时 {total_time:.1f}s")
print(f"{'=' * 50}")
print()
print("提示: 后续搜索仅需 0.5-0.6s，无需重复加载模型")
