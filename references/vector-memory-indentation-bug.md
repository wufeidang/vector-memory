# Vector Memory - 缩进 Bug 修复记录

## 问题描述

`scripts/vector_memory.py` 中 `dedupe_memories()` 和 `generate_daily_summary()` 两个函数被错误地嵌套在 `import_from_memory_md()` 函数内部（4 空格缩进），导致：

1. **语法错误**：`invalid syntax (line 481)`
2. **运行时错误**：`NameError: name 'dedupe_memories' is not defined`
3. **main 函数调用错误**：`return dedupe_memories(args)` 缩进为 0 空格，应为 8 空格（在 main 函数内）

## 根因

代码从 SKILL.md 的示例片段复制到实际脚本时，`dedupe_memories` 和 `generate_daily_summary` 被放在了 `import_from_memory_md` 函数体内部，而不是与 `add_memory`、`search_memories` 等函数并列的模块级位置。

## 修复步骤

1. 使用 `execute_code` 读取文件，逐行用 `repr()` 查看精确缩进
2. 将 `dedupe_memories` 和 `generate_daily_summary` 的函数定义及全部函数体去掉 4 个前导空格
3. 将 `main` 函数中对这两个函数的 `return` 调用加上 8 空格缩进
4. 用 `compile()` 验证语法正确后再运行测试

## 验证命令

```python
# 语法检查
compile(open(path, 'r', encoding='utf-8').read(), path, 'exec')

# 功能测试
import vector_memory as vm
vm.main({"action": "clear"})
vm.main({"action": "add", "text": "测试内容", "metadata": {"category": "test"}})
vm.main({"action": "search", "text": "测试", "top_k": 3})
vm.main({"action": "dedupe"})
vm.main({"action": "generate_daily_summary", "date_str": "2026-05-18"})
```

## 教训

- 技能文档中的代码示例与实际脚本文件必须保持同步
- Python 缩进错误不会在导入时报错，而是在执行到该函数时才暴露
- 调试缩进问题时，`repr(line)` 比肉眼观察更可靠
