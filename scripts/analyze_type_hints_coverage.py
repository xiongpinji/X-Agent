#!/usr/bin/env python3
"""
类型提示覆盖率分析工具 - Type Hints Coverage Analyzer
分析当前代码的类型提示覆盖率
"""

import ast
from pathlib import Path
from typing import Dict, List, Tuple, Any
from collections import defaultdict


class CoverageAnalyzer(ast.NodeVisitor):
    """分析类型提示覆盖率"""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.functions = []
        self.classes = []
        self.total_params = 0
        self.params_with_hints = 0
        self.total_functions = 0
        self.functions_with_return_hints = 0

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
        self.total_functions += 1

        # 检查返回类型提示
        has_return_hint = node.returns is not None
        if has_return_hint:
            self.functions_with_return_hints += 1

        # 检查参数类型提示
        params_count = 0
        params_with_hints_count = 0

        for arg in node.args.args:
            if arg.arg not in ("self", "cls"):
                params_count += 1
                if arg.annotation is not None:
                    params_with_hints_count += 1

        for arg in node.args.posonlyargs:
            params_count += 1
            if arg.annotation is not None:
                params_with_hints_count += 1

        for arg in node.args.kwonlyargs:
            params_count += 1
            if arg.annotation is not None:
                params_with_hints_count += 1

        if node.args.vararg:
            params_count += 1
            if node.args.vararg.annotation is not None:
                params_with_hints_count += 1

        if node.args.kwarg:
            params_count += 1
            if node.args.kwarg.annotation is not None:
                params_with_hints_count += 1

        self.total_params += params_count
        self.params_with_hints += params_with_hints_count

        self.functions.append({
            "name": node.name,
            "lineno": node.lineno,
            "params": params_count,
            "params_with_hints": params_with_hints_count,
            "has_return_hint": has_return_hint,
        })


def analyze_file(filepath: str) -> Dict[str, Any]:
    """分析单个文件"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        try:
            tree = ast.parse(content)
        except SyntaxError:
            return None

        analyzer = CoverageAnalyzer(filepath)
        analyzer.visit(tree)

        return {
            "filepath": filepath,
            "total_functions": analyzer.total_functions,
            "functions_with_return_hints": analyzer.functions_with_return_hints,
            "total_params": analyzer.total_params,
            "params_with_hints": analyzer.params_with_hints,
            "functions": analyzer.functions,
        }

    except Exception as e:
        print(f"Error analyzing {filepath}: {e}")
        return None


def analyze_directory(root_dir: str, patterns: List[str]) -> Dict[str, Any]:
    """分析目录中的所有Python文件"""
    results = {
        "total_files": 0,
        "total_functions": 0,
        "functions_with_return_hints": 0,
        "total_params": 0,
        "params_with_hints": 0,
        "files": [],
    }

    for pattern in patterns:
        for filepath in Path(root_dir).rglob(pattern):
            if "__pycache__" in str(filepath):
                continue

            file_result = analyze_file(str(filepath))
            if file_result:
                results["total_files"] += 1
                results["total_functions"] += file_result["total_functions"]
                results["functions_with_return_hints"] += file_result["functions_with_return_hints"]
                results["total_params"] += file_result["total_params"]
                results["params_with_hints"] += file_result["params_with_hints"]
                results["files"].append(file_result)

    return results


def print_report(results: Dict[str, Any], title: str = ""):
    """打印分析报告"""
    if not results["total_functions"]:
        print(f"  {title}: 没有找到函数")
        return

    param_coverage = (results["params_with_hints"] / results["total_params"] * 100
                      if results["total_params"] > 0 else 0)
    return_coverage = (results["functions_with_return_hints"] / results["total_functions"] * 100
                       if results["total_functions"] > 0 else 0)

    # 综合覆盖率：参数和返回类型都有提示的函数
    functions_fully_typed = sum(
        1 for f in results["files"]
        for func in f["functions"]
        if func["params_with_hints"] == func["params"] and func["has_return_hint"]
    )
    overall_coverage = (functions_fully_typed / results["total_functions"] * 100
                        if results["total_functions"] > 0 else 0)

    print(f"\n{title}")
    print("-" * 80)
    print(f"  文件数: {results['total_files']}")
    print(f"  函数总数: {results['total_functions']}")
    print(f"  参数总数: {results['total_params']}")
    print(f"  参数类型提示覆盖率: {param_coverage:.1f}% ({results['params_with_hints']}/{results['total_params']})")
    print(f"  返回类型提示覆盖率: {return_coverage:.1f}% ({results['functions_with_return_hints']}/{results['total_functions']})")
    print(f"  完全类型化函数: {functions_fully_typed}/{results['total_functions']} ({overall_coverage:.1f}%)")

    return overall_coverage


def main():
    """主函数"""
    project_root = Path(__file__).parent.parent

    # 重点文件目录
    focus_dirs = [
        ("Core", project_root / "backend" / "app" / "core"),
        ("API", project_root / "backend" / "app" / "api"),
        ("Services", project_root / "backend" / "app" / "services"),
    ]

    print("\n" + "=" * 80)
    print("类型提示覆盖率分析 - Type Hints Coverage Analysis")
    print("=" * 80)

    total_results = {
        "total_files": 0,
        "total_functions": 0,
        "functions_with_return_hints": 0,
        "total_params": 0,
        "params_with_hints": 0,
    }

    for title, focus_dir in focus_dirs:
        if not focus_dir.exists():
            print(f"\n跳过不存在的目录: {focus_dir}")
            continue

        results = analyze_directory(str(focus_dir), ["*.py"])

        total_results["total_files"] += results["total_files"]
        total_results["total_functions"] += results["total_functions"]
        total_results["functions_with_return_hints"] += results["functions_with_return_hints"]
        total_results["total_params"] += results["total_params"]
        total_results["params_with_hints"] += results["params_with_hints"]

        print_report(results, f"{title} 目录分析")

    # 总体报告
    print("\n" + "=" * 80)
    print("总体统计")
    print("=" * 80)

    overall_coverage = print_report(total_results, "全项目分析")

    print("\n" + "=" * 80)
    print("目标与进度")
    print("=" * 80)
    print(f"当前覆盖率: {overall_coverage:.1f}%")
    print(f"目标覆盖率: 98%+")

    if overall_coverage >= 98:
        print("✓ 已达成目标！")
    else:
        gap = 98 - overall_coverage
        print(f"还需提升: {gap:.1f}%")

    print("\n" + "=" * 80)
    print()


if __name__ == "__main__":
    main()
