# 代码审查助手 / Code Review Assistant

**版本**: 1.0.0
**作者**: X-Agent Team
**描述**: 基于 Python AST 的确定性静态审查，帮你发现 Python 代码中的常见问题。
**关键词**: 代码, 审查, 质量, 调试, 优化, 最佳实践
**能力**: 代码分析, 质量检查, 安全审查, 最佳实践建议
**图标**: 🔍

## 这个技能是干什么的？

对 **Python 源代码** 做确定性静态检查（基于标准库 `ast`，无 AI 调用、无网络依赖），
输出结构化问题清单与 Markdown 审查报告。

可检测的问题类型：

- ❌ `eval()` / `exec()` 任意代码执行风险
- ❌ 可变默认参数（如 `def f(x=[])`）
- ⚠️ 裸 `except:` 吞异常
- ⚠️ 通配符导入（`from x import *`）
- ⚠️ 函数过长（>50 行）
- 💡 公共函数缺少文档字符串
- 💡 公共函数缺少返回类型注解

## 适合谁用？

- 新手程序员：学习写出更好的代码
- 团队leader：快速审查团队 Python 代码
- 自学者：没人帮忙看代码时用

## 怎么用？

技能接受一个必需参数：

- `code` (string)：待审查的 Python 源代码

输出：`summary`（问题统计）、`issues`（逐条问题：严重级别/规则/行号/说明）、
`report_markdown`（Markdown 格式审查报告）。

## 使用示例

```python
# 输入代码
def add(a, b=[]):
    try:
        return a + b
    except:
        eval("1+1")

# 审查结果（节选）：
# ❌ 第 1 行 [mutable-default-argument] 使用可变默认参数
# ❌ 第 5 行 [no-eval-exec] eval() 可执行任意代码
# ⚠️ 第 4 行 [bare-except] 裸 except 会吞掉所有异常
# 💡 第 1 行 [missing-docstring] 公共函数 add() 缺少文档字符串
```

## 能力边界（重要）

- **仅支持 Python**：基于 `ast` 解析，非 Python 输入会显式报错并说明原因，
  不会假装完成审查。
- **不做 AI 语义审查**：本技能是确定性静态规则检查，不评估业务逻辑正确性。
- 审查需要多长时间？毫秒级，取决于代码长度。
