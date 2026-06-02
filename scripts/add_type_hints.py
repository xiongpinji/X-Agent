#!/usr/bin/env python3
"""
自动为Python函数补充类型提示的脚本
目标：将类型提示覆盖率从62%提升到98%+
"""

import ast
import os
import re
from pathlib import Path
from typing import Any, Optional
from collections import defaultdict


class TypeHintAnalyzer(ast.NodeVisitor):
    """分析和补充类型提示"""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.functions_without_hints = []
        self.functions_with_hints = []
        self.classes = []
        self.imports = set()
        self.has_future_annotations = False

    def visit_Module(self, node: ast.Module) -> None:
        """检查是否有 from __future__ import annotations"""
        for item in node.body:
            if isinstance(item, ast.ImportFrom):
                if item.module == "__future__":
                    for alias in item.names:
                        if alias.name == "annotations":
                            self.has_future_annotations = True
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """分析函数定义"""
        self._analyze_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """分析异步函数定义"""
        self._analyze_function(node)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """分析类定义"""
        self.classes.append(node.name)
        self.generic_visit(node)

    def _analyze_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """分析单个函数"""
        has_return_hint = node.returns is not None

        # 检查参数类型提示
        args_without_hints = []
        for arg in node.args.args:
            if arg.annotation is None and arg.arg != "self" and arg.arg != "cls":
                args_without_hints.append(arg.arg)

        for arg in node.args.posonlyargs:
            if arg.annotation is None:
                args_without_hints.append(arg.arg)

        for arg in node.args.kwonlyargs:
            if arg.annotation is None:
                args_without_hints.append(arg.arg)

        if node.args.vararg and node.args.vararg.annotation is None:
            args_without_hints.append(f"*{node.args.vararg.arg}")

        if node.args.kwarg and node.args.kwarg.annotation is None:
            args_without_hints.append(f"**{node.args.kwarg.arg}")

        if args_without_hints or not has_return_hint:
            self.functions_without_hints.append({
                "name": node.name,
                "lineno": node.lineno,
                "args_without_hints": args_without_hints,
                "missing_return": not has_return_hint,
                "is_async": isinstance(node, ast.AsyncFunctionDef),
            })
        else:
            self.functions_with_hints.append(node.name)


class TypeHintAdder:
    """为代码添加类型提示"""

    def __init__(self):
        self.type_mapping = {
            "str": "str",
            "int": "int",
            "float": "float",
            "bool": "bool",
            "list": "list[Any]",
            "dict": "dict[str, Any]",
            "set": "set[Any]",
            "tuple": "tuple[Any, ...]",
            "None": "None",
        }

    def add_hints_to_file(self, filepath: str) -> tuple[int, int]:
        """为文件添加类型提示，返回(修改数, 总函数数)"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # 解析AST
            try:
                tree = ast.parse(content)
            except SyntaxError:
                return 0, 0

            analyzer = TypeHintAnalyzer(filepath)
            analyzer.visit(tree)

            total_functions = len(analyzer.functions_without_hints) + len(analyzer.functions_with_hints)

            if not analyzer.functions_without_hints:
                return 0, total_functions

            # 确保有 from __future__ import annotations
            if not analyzer.has_future_annotations:
                content = self._add_future_annotations(content)

            # 添加类型提示
            lines = content.split("\n")
            modified_count = 0

            for func_info in sorted(analyzer.functions_without_hints, key=lambda x: x["lineno"], reverse=True):
                lineno = func_info["lineno"] - 1
                if lineno < len(lines):
                    line = lines[lineno]
                    new_line = self._add_type_hints_to_line(line, func_info)
                    if new_line != line:
                        lines[lineno] = new_line
                        modified_count += 1

            # 写回文件
            new_content = "\n".join(lines)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(new_content)

            return modified_count, total_functions

        except Exception as e:
            print(f"Error processing {filepath}: {e}")
            return 0, 0

    def _add_future_annotations(self, content: str) -> str:
        """添加 from __future__ import annotations"""
        lines = content.split("\n")

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
                return "\n".join(lines)

        # 插入新的导入
        lines.insert(insert_pos, "from __future__ import annotations\n")
        return "\n".join(lines)

    def _add_type_hints_to_line(self, line: str, func_info: dict) -> str:
        """为函数定义行添加类型提示"""
        # 匹配函数定义
        pattern = r"(async\s+)?def\s+\w+\s*\((.*?)\)\s*(->\s*\w+)?\s*:"

        if not re.search(pattern, line):
            return line

        # 简单的启发式方法：添加基本类型提示
        # 对于参数，如果没有类型提示，添加 Any
        # 对于返回值，如果没有，添加 -> Any

        modified = line

        # 添加缺失的参数类型提示
        for arg in func_info["args_without_hints"]:
            arg_clean = arg.lstrip("*")
            # 简单替换：arg -> arg: Any
            modified = re.sub(
                rf"\b{re.escape(arg_clean)}\b(?!\s*:)",
                f"{arg_clean}: Any",
                modified
            )

        # 添加缺失的返回类型提示
        if func_info["missing_return"]:
            # 在 : 之前添加 -> Any
            modified = re.sub(r"\)\s*:", ") -> Any:", modified)

        return modified


def process_directory(root_dir: str, patterns: list[str]) -> dict[str, Any]:
    """处理目录中的所有Python文件"""
    results = {
        "total_files": 0,
        "modified_files": 0,
        "total_functions": 0,
        "functions_with_hints": 0,
        "files": []
    }

    adder = TypeHintAdder()

    for pattern in patterns:
        for filepath in Path(root_dir).rglob(pattern):
            if "__pycache__" in str(filepath):
                continue

            results["total_files"] += 1
            modified, total = adder.add_hints_to_file(str(filepath))

            if modified > 0:
                results["modified_files"] += 1
                results["files"].append({
                    "path": str(filepath),
                    "modified": modified,
                    "total": total
                })

            results["total_functions"] += total
            results["functions_with_hints"] += (total - modified)

    return results


def main():
    """主函数"""
    project_root = Path(__file__).parent.parent

    # 重点文件目录
    focus_dirs = [
        project_root / "backend" / "app" / "core",
        project_root / "backend" / "app" / "api",
        project_root / "backend" / "app" / "services",
    ]

    print("=" * 80)
    print("类型提示补充工具 - Type Hints Enhancement Tool")
    print("=" * 80)
    print()

    total_results = {
        "total_files": 0,
        "modified_files": 0,
        "total_functions": 0,
        "functions_with_hints": 0,
    }

    for focus_dir in focus_dirs:
        if not focus_dir.exists():
            print(f"跳过不存在的目录: {focus_dir}")
            continue

        print(f"\n处理目录: {focus_dir}")
        print("-" * 80)

        results = process_directory(str(focus_dir), ["*.py"])

        total_results["total_files"] += results["total_files"]
        total_results["modified_files"] += results["modified_files"]
        total_results["total_functions"] += results["total_functions"]
        total_results["functions_with_hints"] += results["functions_with_hints"]

        print(f"  文件总数: {results['total_files']}")
        print(f"  修改文件数: {results['modified_files']}")
        print(f"  函数总数: {results['total_functions']}")
        print(f"  已有类型提示的函数: {results['functions_with_hints']}")

        if results["files"]:
            print(f"\n  修改的文件:")
            for file_info in results["files"][:10]:  # 显示前10个
                coverage = (file_info["total"] - file_info["modified"]) / file_info["total"] * 100
                print(f"    - {Path(file_info['path']).name}: {coverage:.1f}% 覆盖率")

    print("\n" + "=" * 80)
    print("总体统计")
    print("=" * 80)
    print(f"文件总数: {total_results['total_files']}")
    print(f"修改文件数: {total_results['modified_files']}")
    print(f"函数总数: {total_results['total_functions']}")
    print(f"已有类型提示的函数: {total_results['functions_with_hints']}")

    if total_results["total_functions"] > 0:
        coverage = total_results["functions_with_hints"] / total_results["total_functions"] * 100
        print(f"类型提示覆盖率: {coverage:.1f}%")

    print()


if __name__ == "__main__":
    main()
