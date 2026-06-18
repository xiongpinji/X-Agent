"""Tests for codebase index module."""

import pytest
from pathlib import Path
from datetime import datetime, timezone
import time

from backend.app.core.context.code_index import (
    CodebaseIndex,
    CodeMatch,
    FileNode,
    DependencyEdge,
    DependencyGraph,
    IndexStats,
    get_codebase_index,
    set_codebase_index,
)


class TestCodebaseIndex:
    """CodebaseIndex 类的测试套件。"""

    @pytest.fixture
    def temp_codebase(self, tmp_path):
        """创建临时代码库结构。"""
        # 创建 Python 文件
        py_file1 = tmp_path / "module1.py"
        py_file1.write_text("""
def function1():
    pass

class Class1:
    pass

import os
from pathlib import Path
""")

        py_file2 = tmp_path / "module2.py"
        py_file2.write_text("""
def function2():
    pass

class Class2:
    pass

import sys
from module1 import function1
""")

        # 创建子目录
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        py_file3 = subdir / "module3.py"
        py_file3.write_text("""
def function3():
    pass

import json
from ..module1 import Class1
""")

        # 创建 JavaScript 文件
        js_file = tmp_path / "script.js"
        js_file.write_text("""
function jsFunction() {
    return 42;
}

class JsClass {
    constructor() {}
}

import { something } from './module1.js';
""")

        return tmp_path

    @pytest.fixture
    def index(self):
        """创建索引实例。"""
        return CodebaseIndex()

    def test_build_index(self, index, temp_codebase):
        """测试构建索引。

        验证能够扫描代码库并构建完整的索引。
        """
        stats = index.build_index(temp_codebase)

        assert isinstance(stats, IndexStats)
        assert stats.indexed_files > 0
        assert stats.total_symbols > 0
        assert stats.index_time_seconds >= 0

    def test_build_index_nonexistent_path(self, index):
        """测试不存在的路径。

        验证对不存在的路径返回空统计信息。
        """
        nonexistent = Path("/nonexistent/path/to/codebase")
        stats = index.build_index(nonexistent)

        assert stats.indexed_files == 0
        assert stats.total_symbols == 0

    def test_update_index(self, index, temp_codebase):
        """测试增量更新索引。

        验证能够更新已修改的文件。
        """
        # 首先构建索引
        index.build_index(temp_codebase)
        initial_files = index._stats.indexed_files

        # 修改一个文件
        py_file = temp_codebase / "module1.py"
        py_file.write_text("""
def function1():
    pass

def new_function():
    pass

class Class1:
    pass

class NewClass:
    pass

import os
from pathlib import Path
""")

        # 更新索引
        stats = index.update_index([py_file])

        assert stats.indexed_files >= initial_files

    def test_search_basic(self, index, temp_codebase):
        """测试基本搜索。

        验证能够根据查询词搜索代码。
        """
        index.build_index(temp_codebase)

        results = index.search("function", limit=10)

        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(match, CodeMatch) for match in results)

    def test_search_with_file_types(self, index, temp_codebase):
        """测试按文件类型过滤搜索。

        验证能够按文件类型过滤搜索结果。
        """
        index.build_index(temp_codebase)

        # 搜索 Python 文件
        results_py = index.search("function", file_types=["python"], limit=10)
        assert all(match.file_path.suffix == ".py" for match in results_py)

        # 搜索 JavaScript 文件
        results_js = index.search("function", file_types=["javascript"], limit=10)
        assert all(match.file_path.suffix == ".js" for match in results_js)

    def test_search_limit(self, index, temp_codebase):
        """测试搜索结果限制。

        验证 limit 参数能够正确限制返回结果数量。
        """
        index.build_index(temp_codebase)

        results_1 = index.search("function", limit=1)
        results_5 = index.search("function", limit=5)

        assert len(results_1) <= 1
        assert len(results_5) <= 5
        assert len(results_1) <= len(results_5)

    def test_get_dependencies(self, index, temp_codebase):
        """测试获取依赖。

        验证能够获取文件的依赖关系。
        """
        index.build_index(temp_codebase)

        py_file = temp_codebase / "module2.py"
        graph = index.get_dependencies(py_file)

        assert isinstance(graph, DependencyGraph)
        assert py_file in graph.nodes

    def test_get_dependents(self, index, temp_codebase):
        """测试获取被依赖。

        验证能够获取依赖某个文件的其他文件。
        """
        index.build_index(temp_codebase)

        py_file = temp_codebase / "module1.py"
        dependents = index.get_dependents(py_file)

        assert isinstance(dependents, list)
        # module1 被 module2 依赖
        assert any("module2" in str(dep) for dep in dependents)

    def test_get_stats(self, index, temp_codebase):
        """测试获取统计信息。

        验证能够获取索引的统计信息。
        """
        index.build_index(temp_codebase)
        stats = index.get_stats()

        assert isinstance(stats, IndexStats)
        assert stats.indexed_files > 0
        assert stats.total_symbols > 0
        assert stats.index_time_seconds >= 0

    def test_get_file_info(self, index, temp_codebase):
        """测试获取文件信息。

        验证能够获取单个文件的详细信息。
        """
        index.build_index(temp_codebase)

        py_file = temp_codebase / "module1.py"
        info = index.get_file_info(py_file)

        assert info is not None
        assert "path" in info
        assert "file_type" in info
        assert "symbols" in info
        assert "imports" in info
        assert "size" in info
        assert "last_modified" in info

    def test_get_file_info_nonexistent(self, index, temp_codebase):
        """测试获取不存在文件的信息。

        验证对不存在的文件返回 None。
        """
        index.build_index(temp_codebase)

        nonexistent = temp_codebase / "nonexistent.py"
        info = index.get_file_info(nonexistent)

        assert info is None

    def test_list_files(self, index, temp_codebase):
        """测试列出所有文件。

        验证能够列出索引中的所有文件。
        """
        index.build_index(temp_codebase)

        files = index.list_files()

        assert isinstance(files, list)
        assert len(files) > 0
        assert all("path" in f for f in files)
        assert all("file_type" in f for f in files)

    def test_list_files_by_type(self, index, temp_codebase):
        """测试按类型列出文件。

        验证能够按文件类型过滤文件列表。
        """
        index.build_index(temp_codebase)

        py_files = index.list_files(file_type="python")
        assert all(f["file_type"] == "python" for f in py_files)

        js_files = index.list_files(file_type="javascript")
        assert all(f["file_type"] == "javascript" for f in js_files)

    def test_supported_extensions(self):
        """测试支持的文件扩展名。

        验证索引支持的文件类型。
        """
        assert ".py" in CodebaseIndex.SUPPORTED_EXTENSIONS
        assert ".ts" in CodebaseIndex.SUPPORTED_EXTENSIONS
        assert ".js" in CodebaseIndex.SUPPORTED_EXTENSIONS
        assert ".java" in CodebaseIndex.SUPPORTED_EXTENSIONS

    def test_ignore_dirs(self):
        """测试忽略的目录。

        验证索引忽略的目录列表。
        """
        assert "__pycache__" in CodebaseIndex.IGNORE_DIRS
        assert ".git" in CodebaseIndex.IGNORE_DIRS
        assert "node_modules" in CodebaseIndex.IGNORE_DIRS

    def test_code_match_to_dict(self, index, temp_codebase):
        """测试 CodeMatch 的字典转换。

        验证 CodeMatch 能够正确转换为字典格式。
        """
        index.build_index(temp_codebase)
        results = index.search("function", limit=1)

        if results:
            match = results[0]
            match_dict = match.to_dict()

            assert isinstance(match_dict, dict)
            assert "file_path" in match_dict
            assert "line_number" in match_dict
            assert "content" in match_dict
            assert "relevance_score" in match_dict
            assert "context_lines" in match_dict

    def test_file_node_to_dict(self, index, temp_codebase):
        """测试 FileNode 的字典转换。

        验证 FileNode 能够正确转换为字典格式。
        """
        index.build_index(temp_codebase)

        py_file = temp_codebase / "module1.py"
        info = index.get_file_info(py_file)

        assert info is not None
        assert isinstance(info, dict)

    def test_dependency_edge_to_dict(self):
        """测试 DependencyEdge 的字典转换。

        验证 DependencyEdge 能够正确转换为字典格式。
        """
        edge = DependencyEdge(
            from_file=Path("module1.py"),
            to_file=Path("module2.py"),
            import_statement="from module2 import func",
            edge_type="import",
        )

        edge_dict = edge.to_dict()

        assert isinstance(edge_dict, dict)
        assert "from_file" in edge_dict
        assert "to_file" in edge_dict
        assert "import_statement" in edge_dict
        assert "edge_type" in edge_dict

    def test_dependency_graph_to_dict(self):
        """测试 DependencyGraph 的字典转换。

        验证 DependencyGraph 能够正确转换为字典格式。
        """
        graph = DependencyGraph()
        graph.nodes[Path("module1.py")] = FileNode(
            path=Path("module1.py"),
            file_type="python",
        )

        graph_dict = graph.to_dict()

        assert isinstance(graph_dict, dict)
        assert "nodes" in graph_dict
        assert "edges" in graph_dict

    def test_index_stats_to_dict(self):
        """测试 IndexStats 的字典转换。

        验证 IndexStats 能够正确转换为字典格式。
        """
        stats = IndexStats(
            total_files=10,
            indexed_files=8,
            total_symbols=100,
            index_time_seconds=1.5,
        )

        stats_dict = stats.to_dict()

        assert isinstance(stats_dict, dict)
        assert "total_files" in stats_dict
        assert "indexed_files" in stats_dict
        assert "total_symbols" in stats_dict
        assert "index_time_seconds" in stats_dict
        assert "last_updated" in stats_dict

    def test_search_empty_query(self, index, temp_codebase):
        """测试空查询搜索。

        验证空查询返回空结果。
        """
        index.build_index(temp_codebase)
        results = index.search("")

        assert results == []

    def test_extract_symbols_python(self, index):
        """测试 Python 符号提取。

        验证能够正确提取 Python 文件中的符号。
        """
        content = """
def my_function():
    pass

async def async_function():
    pass

class MyClass:
    pass
"""
        symbols = index._extract_symbols(content, "python")

        assert "my_function" in symbols
        assert "async_function" in symbols
        assert "MyClass" in symbols

    def test_extract_symbols_javascript(self, index):
        """测试 JavaScript 符号提取。

        验证能够正确提取 JavaScript 文件中的符号。
        """
        content = """
function myFunction() {}
export async function asyncFunction() {}
export class MyClass {}
const myVar = 42;
"""
        symbols = index._extract_symbols(content, "javascript")

        assert "myFunction" in symbols
        assert "asyncFunction" in symbols
        assert "MyClass" in symbols
        assert "myVar" in symbols

    def test_extract_imports_python(self, index):
        """测试 Python 导入提取。

        验证能够正确提取 Python 文件中的导入。
        """
        content = """
import os
import sys
from pathlib import Path
from module1 import function1
"""
        imports = index._extract_imports(content, "python")

        assert "os" in imports
        assert "sys" in imports
        assert "pathlib" in imports
        assert "module1" in imports

    def test_extract_imports_javascript(self, index):
        """测试 JavaScript 导入提取。

        验证能够正确提取 JavaScript 文件中的导入。
        """
        content = """
import { something } from './module1.js';
import * as utils from './utils.js';
const fs = require('fs');
"""
        imports = index._extract_imports(content, "javascript")

        assert len(imports) > 0

    def test_global_index_singleton(self):
        """测试全局索引单例。

        验证全局索引单例的获取和设置。
        """
        # 获取全局索引
        index1 = get_codebase_index()
        index2 = get_codebase_index()

        # 应该是同一个实例
        assert index1 is index2

        # 设置新的全局索引
        new_index = CodebaseIndex()
        set_codebase_index(new_index)

        index3 = get_codebase_index()
        assert index3 is new_index

    def test_search_relevance_scoring(self, index, temp_codebase):
        """测试搜索相关性评分。

        验证搜索结果按相关性分数排序。
        """
        index.build_index(temp_codebase)
        results = index.search("function", limit=10)

        if len(results) > 1:
            # 验证结果按相关性分数排序
            for i in range(len(results) - 1):
                assert results[i].relevance_score >= results[i + 1].relevance_score

    def test_index_with_patterns(self, index, temp_codebase):
        """测试使用模式构建索引。

        验证能够使用文件模式过滤要索引的文件。
        """
        stats = index.build_index(temp_codebase, patterns=["*.py"])

        # 应该只索引 Python 文件
        files = index.list_files()
        assert all(f["file_type"] == "python" for f in files)

    def test_update_index_delete_file(self, index, temp_codebase):
        """测试删除文件的索引更新。

        验证能够处理已删除的文件。
        """
        index.build_index(temp_codebase)
        initial_files = index._stats.indexed_files

        # 删除一个文件
        py_file = temp_codebase / "module1.py"
        py_file.unlink()

        # 更新索引
        stats = index.update_index([py_file])

        # 文件数应该减少
        assert index._stats.indexed_files < initial_files
