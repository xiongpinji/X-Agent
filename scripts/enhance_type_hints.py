#!/usr/bin/env python3
"""
高级类型提示补充工具 - Advanced Type Hints Enhancement Tool
使用AST分析和类型推断来自动补充缺失的类型提示
目标：将类型提示覆盖率从62%提升到98%+
"""

import ast
import os
import re
from pathlib import Path
from typing import Any, Optional, Dict, List, Set, Tuple
from collections import defaultdict
import json


class TypeInferencer:
    """类型推断引擎"""

    def __init__(self):
        self.common_patterns = {
            # 参数名称模式 -> 推断类型
            r".*_id$": "str",
            r".*_ids$": "list[str]",
            r".*_count$": "int",
            r".*_size$": "int",
            r".*_flag$": "bool",
            r".*_enabled$": "bool",
            r".*_disabled$": "bool",
            r".*_dict$": "dict[str, Any]",
            r".*_list$": "list[Any]",
            r".*_set$": "set[Any]",
            r".*_tuple$": "tuple[Any, ...]",
            r".*_map$": "dict[str, Any]",
            r".*_data$": "dict[str, Any]",
            r".*_config$": "dict[str, Any]",
            r".*_options$": "dict[str, Any]",
            r".*_params$": "dict[str, Any]",
            r".*_kwargs$": "dict[str, Any]",
            r".*_args$": "list[Any]",
            r".*_path$": "str | Path",
            r".*_url$": "str",
            r".*_uri$": "str",
            r".*_email$": "str",
            r".*_name$": "str",
            r".*_title$": "str",
            r".*_text$": "str",
            r".*_content$": "str",
            r".*_message$": "str",
            r".*_error$": "str | Exception",
            r".*_exception$": "Exception",
            r".*_timestamp$": "datetime",
            r".*_date$": "datetime | date",
            r".*_time$": "datetime | time",
            r".*_duration$": "timedelta",
            r".*_timeout$": "int | float",
            r".*_delay$": "int | float",
            r".*_interval$": "int | float",
            r".*_rate$": "float",
            r".*_score$": "float",
            r".*_value$": "Any",
            r".*_result$": "Any",
            r".*_response$": "dict[str, Any]",
            r".*_request$": "dict[str, Any]",
            r".*_payload$": "dict[str, Any]",
            r".*_body$": "dict[str, Any]",
            r".*_headers$": "dict[str, str]",
            r".*_metadata$": "dict[str, Any]",
            r".*_context$": "dict[str, Any]",
            r".*_state$": "dict[str, Any]",
            r".*_status$": "str",
            r".*_code$": "int | str",
            r".*_version$": "str",
            r".*_token$": "str",
            r".*_key$": "str",
            r".*_secret$": "str",
            r".*_password$": "str",
            r".*_username$": "str",
            r".*_user$": "str",
            r".*_owner$": "str",
            r".*_creator$": "str",
            r".*_author$": "str",
            r".*_callback$": "Callable[..., Any]",
            r".*_handler$": "Callable[..., Any]",
            r".*_func$": "Callable[..., Any]",
            r".*_function$": "Callable[..., Any]",
            r".*_logger$": "logging.Logger",
            r".*_log$": "logging.Logger",
        }

    def infer_type(self, param_name: str, context: Optional[str] = None) -> str:
        """根据参数名称推断类型"""
        param_lower = param_name.lower()

        # 检查模式匹配
        for pattern, inferred_type in self.common_patterns.items():
            if re.match(pattern, param_lower):
                return inferred_type

        # 默认类型
        if param_name.startswith("is_") or param_name.startswith("has_"):
            return "bool"
        elif param_name.startswith("get_") or param_name.startswith("fetch_"):
            return "Any"

        return "Any"

    def infer_return_type(self, func_name: str, is_async: bool = False) -> str:
        """根据函数名称推断返回类型"""
        func_lower = func_name.lower()

        if is_async:
            if func_lower.startswith("get_") or func_lower.startswith("fetch_"):
                return "Coroutine[Any, Any, Any]"
            elif func_lower.startswith("list_"):
                return "Coroutine[Any, Any, list[Any]]"
            elif func_lower.startswith("create_") or func_lower.startswith("save_"):
                return "Coroutine[Any, Any, dict[str, Any]]"
            elif func_lower.startswith("delete_") or func_lower.startswith("remove_"):
                return "Coroutine[Any, Any, bool]"
            elif func_lower.startswith("is_") or func_lower.startswith("has_"):
                return "Coroutine[Any, Any, bool]"
            else:
                return "Coroutine[Any, Any, Any]"
        else:
            if func_lower.startswith("get_") or func_lower.startswith("fetch_"):
                return "Any"
            elif func_lower.startswith("list_"):
                return "list[Any]"
            elif func_lower.startswith("create_") or func_lower.startswith("save_"):
                return "dict[str, Any]"
            elif func_lower.startswith("delete_") or func_lower.startswith("remove_"):
                return "bool"
            elif func_lower.startswith("is_") or func_lower.startswith("has_"):
                return "bool"
            else:
                return "Any"


class TypeHintEnhancer(ast.NodeVisitor):
    """增强型类型提示分析和补充"""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.functions = []
        self.classes = []
        self.imports = set()
        self.has_future_annotations = False
        self.inferencer = TypeInferencer()

    def visit_Module(self, node: ast.Module) -> None:
        """检查模块级别的导入"""
        for item in node.body:
            if isinstance(item, ast.ImportFrom):
                if item.module == "__future__":
                    for alias in item.names:
                        if alias.name == "annotations":
                            self.has_future_annotations = True
                # 收集导入
                if item.module:
                    self.imports.add(item.module)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """分析函数定义"""
        self._analyze_function(node, is_async=False)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """分析异步函数定义"""
        self._analyze_function(node, is_async=True)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """分析类定义"""
        self.classes.append(node.name)
        self.generic_visit(node)

    def _analyze_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool) -> None:
        """分析单个函数"""
        func_info = {
            "name": node.name,
            "lineno": node.lineno,
            "is_async": is_async,
            "args": [],
            "has_return_hint": node.returns is not None,
            "inferred_return_type": None,
        }

        # 分析参数
        for arg in node.args.args:
            if arg.arg not in ("self", "cls"):
                arg_info = {
                    "name": arg.arg,
                    "has_hint": arg.annotation is not None,
                    "inferred_type": None,
                }
                if not arg_info["has_hint"]:
                    arg_info["inferred_type"] = self.inferencer.infer_type(arg.arg)
                func_info["args"].append(arg_info)

        # 分析 *args 和 **kwargs
        if node.args.vararg:
            arg_info = {
                "name": f"*{node.args.vararg.arg}",
                "has_hint": node.args.vararg.annotation is not None,
                "inferred_type": "tuple[Any, ...]" if not node.args.vararg.annotation else None,
            }
            func_info["args"].append(arg_info)

        if node.args.kwarg:
            arg_info = {
                "name": f"**{node.args.kwarg.arg}",
                "has_hint": node.args.kwarg.annotation is not None,
                "inferred_type": "dict[str, Any]" if not node.args.kwarg.annotation else None,
            }
            func_info["args"].append(arg_info)

        # 推断返回类型
        if not func_info["has_return_hint"]:
            func_info["inferred_return_type"] = self.inferencer.infer_return_type(node.name, is_async)

        self.functions.append(func_info)


class TypeHintWriter:
    """类型提示写入器"""

    def __init__(self):
        self.inferencer = TypeInferencer()

    def enhance_file(self, filepath: str) -> Tuple[int, int, int]:
        """增强文件的类型提示，返回(修改的函数数, 总函数数, 修改的行数)"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # 解析AST
            try:
                tree = ast.parse(content)
            except SyntaxError as e:
                print(f"  语法错误 {filepath}: {e}")
                return 0, 0, 0

            enhancer = TypeHintEnhancer(filepath)
            enhancer.visit(tree)

            total_functions = len(enhancer.functions)
            if total_functions == 0:
                return 0, 0, 0

            # 确保有 from __future__ import annotations
            if not enhancer.has_future_annotations:
                content = self._add_future_annotations(content)

            # 处理每个函数
            lines = content.split("\n")
            modified_functions = 0
            modified_lines = 0

            # 按行号倒序处理，避免行号偏移
            for func_info in sorted(enhancer.functions, key=lambda x: x["lineno"], reverse=True):
                lineno = func_info["lineno"] - 1

                if lineno >= len(lines):
                    continue

                line = lines[lineno]
                new_line = self._enhance_function_line(line, func_info)

                if new_line != line:
                    lines[lineno] = new_line
                    modified_functions += 1
                    modified_lines += 1

            # 写回文件
            new_content = "\n".join(lines)
            if new_content != content:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_content)

            return modified_functions, total_functions, modified_lines

        except Exception as e:
            print(f"  处理错误 {filepath}: {e}")
            return 0, 0, 0

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
        lines.insert(insert_pos, "from __future__ import annotations")
        return "\n".join(lines)

    def _enhance_function_line(self, line: str, func_info: dict) -> str:
        """增强函数定义行"""
        # 检查是否是函数定义行
        if not re.search(r"(async\s+)?def\s+\w+\s*\(", line):
            return line

        modified = line

        # 添加参数类型提示
        for arg_info in func_info["args"]:
            if not arg_info["has_hint"] and arg_info["inferred_type"]:
                arg_name = arg_info["name"].lstrip("*")
                # 查找参数并添加类型提示
                pattern = rf"\b{re.escape(arg_name)}\b(?!\s*:)"
                replacement = f"{arg_name}: {arg_info['inferred_type']}"
                modified = re.sub(pattern, replacement, modified)

        # 添加返回类型提示
        if not func_info["has_return_hint"] and func_info["inferred_return_type"]:
            # 在 : 之前添加返回类型
            modified = re.sub(r"\)\s*:", f") -> {func_info['inferred_return_type']}:", modified)

        return modified


def process_directory(root_dir: str, patterns: List[str]) -> Dict[str, Any]:
    """处理目录中的所有Python文件"""
    results = {
        "total_files": 0,
        "modified_files": 0,
        "total_functions": 0,
        "enhanced_functions": 0,
        "total_lines_modified": 0,
        "files": []
    }

    writer = TypeHintWriter()

    for pattern in patterns:
        for filepath in Path(root_dir).rglob(pattern):
            if "__pycache__" in str(filepath) or "test" in str(filepath):
                continue

            results["total_files"] += 1
            modified_funcs, total_funcs, modified_lines = writer.enhance_file(str(filepath))

            if modified_funcs > 0:
                results["modified_files"] += 1
                coverage = (total_funcs - modified_funcs) / total_funcs * 100 if total_funcs > 0 else 0
                results["files"].append({
                    "path": str(filepath),
                    "modified": modified_funcs,
                    "total": total_funcs,
                    "coverage": coverage,
                    "lines_modified": modified_lines,
                })

            results["total_functions"] += total_funcs
            results["enhanced_functions"] += (total_funcs - modified_funcs)
            results["total_lines_modified"] += modified_lines

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

    print("\n" + "=" * 100)
    print("高级类型提示补充工具 - Advanced Type Hints Enhancement Tool")
    print("=" * 100)
    print()

    total_results = {
        "total_files": 0,
        "modified_files": 0,
        "total_functions": 0,
        "enhanced_functions": 0,
        "total_lines_modified": 0,
    }

    for focus_dir in focus_dirs:
        if not focus_dir.exists():
            print(f"跳过不存在的目录: {focus_dir}")
            continue

        print(f"\n处理目录: {focus_dir.name}")
        print("-" * 100)

        results = process_directory(str(focus_dir), ["*.py"])

        total_results["total_files"] += results["total_files"]
        total_results["modified_files"] += results["modified_files"]
        total_results["total_functions"] += results["total_functions"]
        total_results["enhanced_functions"] += results["enhanced_functions"]
        total_results["total_lines_modified"] += results["total_lines_modified"]

        print(f"  文件总数: {results['total_files']}")
        print(f"  修改文件数: {results['modified_files']}")
        print(f"  函数总数: {results['total_functions']}")
        print(f"  已有类型提示的函数: {results['enhanced_functions']}")
        print(f"  修改的行数: {results['total_lines_modified']}")

        if results["files"]:
            print(f"\n  修改最多的文件:")
            sorted_files = sorted(results["files"], key=lambda x: x["modified"], reverse=True)
            for file_info in sorted_files[:15]:
                print(f"    - {Path(file_info['path']).name}")
                print(f"      修改函数: {file_info['modified']}/{file_info['total']}")
                print(f"      覆盖率: {file_info['coverage']:.1f}%")

    print("\n" + "=" * 100)
    print("总体统计")
    print("=" * 100)
    print(f"文件总数: {total_results['total_files']}")
    print(f"修改文件数: {total_results['modified_files']}")
    print(f"函数总数: {total_results['total_functions']}")
    print(f"已有类型提示的函数: {total_results['enhanced_functions']}")
    print(f"修改的行数: {total_results['total_lines_modified']}")

    if total_results["total_functions"] > 0:
        coverage = total_results["enhanced_functions"] / total_results["total_functions"] * 100
        print(f"\n类型提示覆盖率: {coverage:.1f}%")
        print(f"目标覆盖率: 98%+")
        print(f"进度: {'✓ 已达成' if coverage >= 98 else f'还需提升 {98 - coverage:.1f}%'}")

    print("\n" + "=" * 100)
    print()


if __name__ == "__main__":
    main()
