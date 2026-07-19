#!/usr/bin/env python3
"""
批量补充类型提示 - Batch Type Hints Enhancement
对所有Python文件进行自动类型提示补充
"""

import ast
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class TypeHintBatchProcessor:
    """批量处理类型提示"""

    def __init__(self):
        self.stats = {
            "files_processed": 0,
            "files_modified": 0,
            "functions_enhanced": 0,
            "total_functions": 0,
            "errors": 0,
        }

    def process_directory(self, root_dir: str) -> Dict[str, Any]:
        """处理目录中的所有Python文件"""
        root_path = Path(root_dir)

        # 重点目录
        focus_patterns = [
            "backend/app/core/*.py",
            "backend/app/api/*.py",
            "backend/app/services/**/*.py",
        ]

        for pattern in focus_patterns:
            for filepath in root_path.glob(pattern):
                if "__pycache__" in str(filepath) or "test" in str(filepath):
                    continue

                self.process_file(str(filepath))

        return self.stats

    def process_file(self, filepath: str) -> None:
        """处理单个文件"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # 解析AST
            try:
                tree = ast.parse(content)
            except SyntaxError:
                self.stats["errors"] += 1
                return

            self.stats["files_processed"] += 1

            # 分析函数
            analyzer = FunctionAnalyzer()
            analyzer.visit(tree)

            self.stats["total_functions"] += len(analyzer.functions)

            if not analyzer.functions:
                return

            # 补充类型提示
            new_content = self._enhance_content(content, analyzer)

            if new_content != content:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_content)
                self.stats["files_modified"] += 1
                self.stats["functions_enhanced"] += len(analyzer.functions)

        except Exception as e:
            print(f"Error processing {filepath}: {e}")
            self.stats["errors"] += 1

    def _enhance_content(self, content: str, analyzer: "FunctionAnalyzer") -> str:
        """增强内容中的类型提示"""
        lines = content.split("\n")

        # 确保有 from __future__ import annotations
        if not analyzer.has_future_annotations:
            lines = self._add_future_annotations(lines)

        # 处理每个函数（从后往前，避免行号偏移）
        for func_info in sorted(analyzer.functions, key=lambda x: x["lineno"], reverse=True):
            lineno = func_info["lineno"] - 1
            if lineno < len(lines):
                lines[lineno] = self._enhance_function_line(lines[lineno], func_info)

        return "\n".join(lines)

    def _add_future_annotations(self, lines: List[str]) -> List[str]:
        """添加 from __future__ import annotations"""
        # 找到第一个非注释、非空行
        insert_pos = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                insert_pos = i
                break

        # 检查是否已有 from __future__ import
        for i in range(insert_pos, min(insert_pos + 10, len(lines))):
            if "from __future__ import" in lines[i]:
                if "annotations" not in lines[i]:
                    lines[i] = lines[i].rstrip() + ", annotations"
                return lines

        # 插入新的导入
        lines.insert(insert_pos, "from __future__ import annotations")
        return lines

    def _enhance_function_line(self, line: str, func_info: Dict[str, Any]) -> str:
        """增强函数定义行"""
        if not re.search(r"(async\s+)?def\s+\w+\s*\(", line):
            return line

        modified = line

        # 添加参数类型提示
        for arg_name, arg_type in func_info.get("args_to_enhance", {}).items():
            pattern = rf"\b{re.escape(arg_name)}\b(?!\s*:)"
            replacement = f"{arg_name}: {arg_type}"
            modified = re.sub(pattern, replacement, modified)

        # 添加返回类型提示
        if func_info.get("needs_return_hint"):
            return_type = func_info.get("inferred_return_type", "Any")
            modified = re.sub(r"\)\s*:", f") -> {return_type}:", modified)

        return modified


class FunctionAnalyzer(ast.NodeVisitor):
    """分析函数定义"""

    def __init__(self):
        self.functions = []
        self.has_future_annotations = False

    def visit_Module(self, node: ast.Module) -> None:
        """检查模块级别的导入"""
        for item in node.body:
            if isinstance(item, ast.ImportFrom):
                if item.module == "__future__":
                    for alias in item.names:
                        if alias.name == "annotations":
                            self.has_future_annotations = True
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """分析函数定义"""
        self._analyze_function(node, is_async=False)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """分析异步函数定义"""
        self._analyze_function(node, is_async=True)
        self.generic_visit(node)

    def _analyze_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool) -> None:
        """分析单个函数"""
        args_to_enhance = {}
        needs_return_hint = node.returns is None

        # 分析参数
        for arg in node.args.args:
            if arg.arg not in ("self", "cls") and arg.annotation is None:
                args_to_enhance[arg.arg] = self._infer_type(arg.arg)

        for arg in node.args.kwonlyargs:
            if arg.annotation is None:
                args_to_enhance[arg.arg] = self._infer_type(arg.arg)

        if node.args.vararg and node.args.vararg.annotation is None:
            args_to_enhance[f"*{node.args.vararg.arg}"] = "tuple[Any, ...]"

        if node.args.kwarg and node.args.kwarg.annotation is None:
            args_to_enhance[f"**{node.args.kwarg.arg}"] = "dict[str, Any]"

        if args_to_enhance or needs_return_hint:
            self.functions.append({
                "name": node.name,
                "lineno": node.lineno,
                "args_to_enhance": args_to_enhance,
                "needs_return_hint": needs_return_hint,
                "inferred_return_type": self._infer_return_type(node.name, is_async),
            })

    def _infer_type(self, param_name: str) -> str:
        """推断参数类型"""
        param_lower = param_name.lower()

        # 基于名称的启发式推断
        if param_lower.endswith("_id"):
            return "str"
        elif param_lower.endswith("_ids"):
            return "list[str]"
        elif param_lower.endswith("_count") or param_lower.endswith("_size"):
            return "int"
        elif param_lower.startswith("is_") or param_lower.startswith("has_"):
            return "bool"
        elif param_lower.endswith("_dict") or param_lower.endswith("_data"):
            return "dict[str, Any]"
        elif param_lower.endswith("_list"):
            return "list[Any]"
        elif param_lower.endswith("_path"):
            return "str | Path"
        elif param_lower.endswith("_url") or param_lower.endswith("_uri"):
            return "str"
        else:
            return "Any"

    def _infer_return_type(self, func_name: str, is_async: bool) -> str:
        """推断返回类型"""
        func_lower = func_name.lower()

        if func_lower.startswith("get_") or func_lower.startswith("fetch_"):
            return "Coroutine[Any, Any, Any]" if is_async else "Any"
        elif func_lower.startswith("list_"):
            return "Coroutine[Any, Any, list[Any]]" if is_async else "list[Any]"
        elif func_lower.startswith("is_") or func_lower.startswith("has_"):
            return "Coroutine[Any, Any, bool]" if is_async else "bool"
        elif func_lower.startswith("create_") or func_lower.startswith("save_"):
            return "Coroutine[Any, Any, dict[str, Any]]" if is_async else "dict[str, Any]"
        else:
            return "Coroutine[Any, Any, Any]" if is_async else "Any"


def main():
    """主函数"""
    project_root = Path(__file__).parent.parent

    print("\n" + "=" * 100)
    print("批量补充类型提示 - Batch Type Hints Enhancement")
    print("=" * 100)
    print()

    processor = TypeHintBatchProcessor()
    stats = processor.process_directory(str(project_root))

    print("\n处理完成！")
    print("-" * 100)
    print(f"处理的文件数: {stats['files_processed']}")
    print(f"修改的文件数: {stats['files_modified']}")
    print(f"总函数数: {stats['total_functions']}")
    print(f"增强的函数数: {stats['functions_enhanced']}")
    print(f"错误数: {stats['errors']}")

    if stats["total_functions"] > 0:
        coverage = (stats["functions_enhanced"] / stats["total_functions"]) * 100
        print(f"\n类型提示增强率: {coverage:.1f}%")

    print("\n" + "=" * 100)
    print()


if __name__ == "__main__":
    main()
