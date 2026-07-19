"""代码审查助手 - 可执行实现

基于 Python 标准库 ast 的确定性静态审查（仅支持 Python 源代码）。
非 Python 输入会显式报错降级，不假装完成审查。

契约：backend.app.core.skills.Skill（目录技能须导出 SkillImplementation）。
"""

from __future__ import annotations

import ast
import textwrap
from typing import Any, Dict, List

from backend.app.core.skills import Skill, SkillContext, SkillMetadata, SkillResult


class _ReviewVisitor(ast.NodeVisitor):
    """收集常见代码问题的 AST 访问器"""

    def __init__(self) -> None:
        self.issues: List[Dict[str, Any]] = []
        self._function_stack: List[ast.FunctionDef | ast.AsyncFunctionDef] = []

    # ---- 规则实现 ----

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_function(node)
        self._function_stack.append(node)
        self.generic_visit(node)
        self._function_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_function(node)
        self._function_stack.append(node)
        self.generic_visit(node)
        self._function_stack.pop()

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is None:
            self.issues.append({
                "severity": "warning",
                "rule": "bare-except",
                "line": node.lineno,
                "message": "裸 except 会吞掉所有异常（包括 KeyboardInterrupt），请指明异常类型",
            })
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name == "*" or alias.asname == "*":
                self.issues.append({
                    "severity": "warning",
                    "rule": "wildcard-import",
                    "line": node.lineno,
                    "message": "避免通配符导入，污染命名空间且阻碍静态分析",
                })
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name == "*":
                self.issues.append({
                    "severity": "warning",
                    "rule": "wildcard-import",
                    "line": node.lineno,
                    "message": f"避免 from {node.module} import *，污染命名空间且阻碍静态分析",
                })
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # eval / exec 风险提示
        func = node.func
        name = func.id if isinstance(func, ast.Name) else None
        if name in ("eval", "exec"):
            self.issues.append({
                "severity": "error",
                "rule": "no-eval-exec",
                "line": node.lineno,
                "message": f"{name}() 可执行任意代码，存在安全风险，请使用更安全的替代",
            })
        self.generic_visit(node)

    # ---- 内部 ----

    def _check_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        # 缺文档字符串
        if ast.get_docstring(node) is None and not node.name.startswith("_"):
            self.issues.append({
                "severity": "info",
                "rule": "missing-docstring",
                "line": node.lineno,
                "message": f"公共函数 {node.name}() 缺少文档字符串",
            })
        # 缺类型提示
        if node.returns is None and not node.name.startswith("_"):
            self.issues.append({
                "severity": "info",
                "rule": "missing-return-annotation",
                "line": node.lineno,
                "message": f"公共函数 {node.name}() 缺少返回类型注解",
            })
        # 可变默认参数
        for default in node.args.defaults + node.args.kw_defaults:
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                self.issues.append({
                    "severity": "error",
                    "rule": "mutable-default-argument",
                    "line": node.lineno,
                    "message": f"函数 {node.name}() 使用可变默认参数，请改为 None 并在函数体内初始化",
                })
        # 函数过长（>50 行）
        body_lines = (node.end_lineno or node.lineno) - node.lineno
        if body_lines > 50:
            self.issues.append({
                "severity": "warning",
                "rule": "function-too-long",
                "line": node.lineno,
                "message": f"函数 {node.name}() 约 {body_lines} 行，建议拆分为更小的函数",
            })


class SkillImplementation(Skill):
    """代码审查技能：对 Python 源代码做确定性静态检查"""

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            name="code-review-skill",
            version="1.0.0",
            description="基于 AST 的 Python 代码静态审查：bug 风险、安全、可维护性建议",
            author="X-Agent Team",
            capabilities=["代码分析", "质量检查", "安全审查", "最佳实践建议"],
            tags=["code-review", "python", "static-analysis"],
        )

    # LLM 工具调用参数 schema（供 skill_agent_adapter 使用）
    parameters_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "待审查的 Python 源代码",
            },
        },
        "required": ["code"],
    }

    async def validate(self, context: SkillContext, **kwargs) -> bool:
        return isinstance(kwargs.get("code"), str) and bool(kwargs["code"].strip())

    async def execute(self, context: SkillContext, **kwargs) -> SkillResult:
        code = kwargs.get("code")
        if not isinstance(code, str) or not code.strip():
            return SkillResult(
                success=False,
                error="缺少必需参数 code（Python 源代码字符串）",
            )

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            # 显式降级：语法错误或非 Python 输入，不假装完成审查
            return SkillResult(
                success=False,
                error=(
                    f"输入不是可解析的 Python 源代码（第 {e.lineno} 行: {e.msg}）。"
                    f"本技能基于 Python AST 实现，仅支持 Python；其他语言请使用对应工具。"
                ),
                data={"syntax_error": {"line": e.lineno, "message": e.msg}},
            )

        visitor = _ReviewVisitor()
        visitor.visit(tree)

        severity_order = {"error": 0, "warning": 1, "info": 2}
        issues = sorted(visitor.issues, key=lambda i: (severity_order.get(i["severity"], 3), i["line"]))
        summary = {
            "total_issues": len(issues),
            "errors": sum(1 for i in issues if i["severity"] == "error"),
            "warnings": sum(1 for i in issues if i["severity"] == "warning"),
            "info": sum(1 for i in issues if i["severity"] == "info"),
        }

        report_lines = ["# 代码审查报告", ""]
        report_lines.append(
            f"共 {summary['total_issues']} 项发现："
            f"{summary['errors']} 错误 / {summary['warnings']} 警告 / {summary['info']} 建议"
        )
        report_lines.append("")
        for issue in issues:
            icon = {"error": "❌", "warning": "⚠️", "info": "💡"}[issue["severity"]]
            report_lines.append(f"- {icon} 第 {issue['line']} 行 [{issue['rule']}] {issue['message']}")
        if not issues:
            report_lines.append("✓ 未发现本规则集覆盖的问题")

        return SkillResult(
            success=True,
            data={
                "language": "python",
                "summary": summary,
                "issues": issues,
                "report_markdown": "\n".join(report_lines),
            },
        )


if __name__ == "__main__":
    # 手动冒烟：python skills/code-review-skill/main.py
    import asyncio

    sample = textwrap.dedent(
        """
        def add(a, b=[]):
            try:
                return a + b
            except:
                eval("1+1")
        """
    )

    async def _smoke() -> None:
        skill = SkillImplementation()
        ctx = SkillContext(skill_name="code-review-skill", execution_id="smoke")
        result = await skill.execute(ctx, code=sample)
        print(result.data["report_markdown"] if result.success else result.error)

    asyncio.run(_smoke())
