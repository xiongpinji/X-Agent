"""Deep coverage tests for tools.py — all branches and code paths."""
import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.core.tools import (
    ToolDefinition,
    ToolExecutionRecord,
    ToolExecutionStore,
    ToolRegistry,
    set_tool_root_override,
    reset_tool_root_override,
    _active_tool_base,
    _is_path_forbidden,
    _resolve_tool_path,
    _resolve_tool_root,
    echo,
    list_files,
    inspect_tree,
    coordinate_files,
    analyze_entrypoints,
    analyze_dependencies,
    assess_change_impact,
    read_file,
    write_file,
    preview_text_patch,
    apply_text_patch,
    apply_batch_patch,
    preview_batch_patches,
    search_text,
    summarize_text,
    normalize_text,
    extract_keywords,
    build_default_tool_registry,
)
from backend.app.core.contracts import RunContext, RiskLevel, ToolCallRecord, ToolPolicyVerdict
from backend.app.core.policy import ToolPolicyEngine


# ═══════════════════════════════════════════════════════════════════════════════
# PATH SECURITY TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestPathSecurity:
    def test_is_path_forbidden(self):
        # On Windows, Path("/etc") becomes \etc so we test with PurePosixPath
        from pathlib import PurePosixPath
        assert _is_path_forbidden(PurePosixPath("/etc/passwd")) is True
        assert _is_path_forbidden(PurePosixPath("/sys/kernel")) is True
        assert _is_path_forbidden(PurePosixPath("/proc/1")) is True
        assert _is_path_forbidden(PurePosixPath("/dev/null")) is True
        assert _is_path_forbidden(PurePosixPath("/boot/vmlinuz")) is True
        assert _is_path_forbidden(PurePosixPath("/root/.bashrc")) is True
        assert _is_path_forbidden(PurePosixPath("/var/log/syslog")) is True
        assert _is_path_forbidden(PurePosixPath("/tmp/file")) is True

    def test_is_path_not_forbidden(self):
        from pathlib import PurePosixPath
        assert _is_path_forbidden(PurePosixPath("/home/user/project")) is False

    def test_resolve_tool_path_forbidden(self):
        with patch("backend.app.core.tools._is_path_forbidden", return_value=True):
            with patch("backend.app.core.tools._active_tool_base", return_value=Path("/")):
                with pytest.raises(PermissionError, match="forbidden"):
                    _resolve_tool_path("/etc/passwd")

    def test_resolve_tool_path_outside_root(self, tmp_path):
        with patch("backend.app.core.tools._active_tool_base", return_value=tmp_path):
            with pytest.raises(PermissionError, match="within project"):
                _resolve_tool_path(str(tmp_path.parent.parent.parent / "outside.txt"))

    def test_resolve_tool_root_forbidden(self):
        with patch("backend.app.core.tools._is_path_forbidden", return_value=True):
            with patch("backend.app.core.tools._active_tool_base", return_value=Path("/")):
                with pytest.raises(PermissionError, match="forbidden"):
                    _resolve_tool_root("/etc")

    def test_resolve_tool_root_outside(self, tmp_path):
        with patch("backend.app.core.tools._active_tool_base", return_value=tmp_path):
            with pytest.raises(PermissionError, match="within project"):
                _resolve_tool_root(str(tmp_path.parent.parent.parent / "outside"))

    def test_tool_root_override(self, tmp_path):
        token = set_tool_root_override(str(tmp_path))
        base = _active_tool_base()
        assert str(tmp_path) in str(base)
        reset_tool_root_override(token)


# ═══════════════════════════════════════════════════════════════════════════════
# ToolExecutionStore TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestToolExecutionStore:
    def _make_context(self):
        return RunContext(trace_id="trace-1", tenant_id="t1", user_id="u1")

    def _make_tool_call(self):
        return ToolCallRecord(
            tool_name="echo",
            success=True,
            policy=ToolPolicyVerdict(allowed=True, requires_approval=False,
                                     sandbox_profile="default", reason="ok"),
            risk_level=RiskLevel.LOW,
            latency_ms=1.5,
            arguments_preview={"text": "hello"},
            trace_id="trace-1",
        )

    def test_record_and_get(self, tmp_path):
        store = ToolExecutionStore(storage_path=tmp_path / "exec.json")
        ctx = self._make_context()
        tc = self._make_tool_call()
        record = store.record(ctx, tc)
        assert record.execution_id is not None
        assert store.get(record.execution_id) is not None

    def test_by_trace(self, tmp_path):
        store = ToolExecutionStore(storage_path=tmp_path / "exec.json")
        ctx = self._make_context()
        store.record(ctx, self._make_tool_call())
        store.record(ctx, self._make_tool_call())
        records = store.by_trace("trace-1")
        assert len(records) == 2

    def test_persistence(self, tmp_path):
        path = tmp_path / "exec.json"
        store1 = ToolExecutionStore(storage_path=path)
        ctx = self._make_context()
        store1.record(ctx, self._make_tool_call())
        store2 = ToolExecutionStore(storage_path=path)
        assert len(store2.by_trace("trace-1")) == 1

    def test_no_storage_path(self):
        store = ToolExecutionStore()
        ctx = self._make_context()
        record = store.record(ctx, self._make_tool_call())
        assert store.get(record.execution_id) is not None


# ═══════════════════════════════════════════════════════════════════════════════
# ToolRegistry TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestToolRegistry:
    def _make_registry(self):
        return ToolRegistry(policy_engine=ToolPolicyEngine())

    def _make_context(self):
        return RunContext(
            trace_id="trace-1", tenant_id="t1", user_id="u1",
            permission_scope=["tools:read", "tool:echo"],
        )

    def test_register_by_name(self):
        reg = self._make_registry()
        reg.register("echo", "Echo text", echo)
        assert reg.get("echo") is not None
        assert reg.get("echo").name == "echo"

    def test_register_by_definition(self):
        reg = self._make_registry()
        defn = ToolDefinition(name="custom", description="Custom tool", handler=echo)
        reg.register(defn)
        assert reg.get("custom") is not None

    def test_unregister(self):
        reg = self._make_registry()
        reg.register("echo", "Echo", echo)
        assert reg.unregister("echo") is True
        assert reg.unregister("echo") is False

    def test_tool_names(self):
        reg = self._make_registry()
        reg.register("beta", "B", echo)
        reg.register("alpha", "A", echo)
        assert reg.tool_names() == ["alpha", "beta"]

    def test_definitions_for_llm(self):
        reg = self._make_registry()
        reg.register("echo", "Echo text", echo)
        defs = reg.definitions_for_llm()
        assert len(defs) == 1
        assert defs[0]["type"] == "function"
        assert defs[0]["function"]["name"] == "echo"

    def test_manifest(self):
        reg = self._make_registry()
        reg.register("echo", "Echo text", echo)
        manifest = reg.manifest()
        assert len(manifest) == 1
        assert manifest[0]["name"] == "echo"

    def test_capability_index(self):
        reg = self._make_registry()
        reg.register("read_data", "Read data", echo)
        reg.register("write_data", "Write data", echo)
        reg.register("search_items", "Search items", echo)
        reg.register("code_runner", "Run code", echo)
        reg.register("my_utility", "A utility", echo)
        index = reg.capability_index()
        # read_data -> "read" bucket (no code/write keywords)
        assert any(t["name"] == "read_data" for t in index["read"])
        # write_data -> "write" bucket
        assert any(t["name"] == "write_data" for t in index["write"])
        # search_items -> "search" bucket
        assert any(t["name"] == "search_items" for t in index["search"])
        # code_runner -> "code" bucket
        assert any(t["name"] == "code_runner" for t in index["code"])
        # my_utility -> "utility" bucket
        assert any(t["name"] == "my_utility" for t in index["utility"])

    def test_related_tools(self):
        reg = self._make_registry()
        reg.register("read_file", "Read a file from disk", echo)
        reg.register("write_file", "Write a file to disk", echo)
        results = reg.related_tools("read file")
        assert len(results) >= 1

    async def test_execute_unknown_tool(self):
        reg = self._make_registry()
        ctx = self._make_context()
        record = await reg.execute(ctx, "nonexistent", {})
        assert record.success is False
        assert "Unknown tool" in record.error

    async def test_execute_no_name_raises(self):
        reg = self._make_registry()
        ctx = self._make_context()
        with pytest.raises(TypeError, match="requires a tool name"):
            await reg.execute(ctx, None, {})

    async def test_execute_success(self):
        reg = self._make_registry()
        reg.register("echo", "Echo text", echo)
        ctx = self._make_context()
        record = await reg.execute(ctx, "echo", {"text": "hello"})
        assert record.success is True
        assert record.output == "hello"

    async def test_execute_tool_name_kwarg(self):
        reg = self._make_registry()
        reg.register("echo", "Echo text", echo)
        ctx = self._make_context()
        record = await reg.execute(ctx, tool_name="echo", arguments={"text": "hi"})
        assert record.success is True

    async def test_execute_handler_exception(self):
        reg = self._make_registry()
        async def failing_tool(text: str = "") -> str:
            raise ValueError("tool error")
        reg.register("fail", "Failing tool", failing_tool)
        ctx = self._make_context()
        record = await reg.execute(ctx, "fail", {"text": "x"})
        assert record.success is False
        assert "tool error" in record.error

    async def test_execute_policy_denied(self):
        policy = MagicMock()
        policy.evaluate.return_value = ToolPolicyVerdict(
            allowed=False, requires_approval=False,
            sandbox_profile="locked", reason="denied by policy",
        )
        reg = ToolRegistry(policy_engine=policy)
        reg.register("secret", "Secret tool", echo)
        ctx = self._make_context()
        record = await reg.execute(ctx, "secret", {"text": "x"})
        assert record.success is False
        assert "denied by policy" in record.error

    async def test_execute_policy_requires_approval(self):
        from backend.app.core.approvals import ApprovalStore
        approval_store = ApprovalStore()
        policy = MagicMock()
        policy.evaluate.return_value = ToolPolicyVerdict(
            allowed=False, requires_approval=True,
            sandbox_profile="locked", reason="needs approval",
        )
        reg = ToolRegistry(policy_engine=policy, approval_store=approval_store)
        reg.register("dangerous", "Dangerous tool", echo, risk_level=RiskLevel.HIGH)
        ctx = self._make_context()
        record = await reg.execute(ctx, "dangerous", {"text": "x"})
        assert record.success is False
        assert "Approval request" in record.error

    async def test_execute_validation_error_missing_arg(self):
        reg = self._make_registry()
        reg.register("echo", "Echo", echo, parameters_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        })
        ctx = self._make_context()
        record = await reg.execute(ctx, "echo", {})
        assert record.success is False
        assert "Missing required" in record.error

    async def test_execute_validation_error_unknown_arg(self):
        reg = self._make_registry()
        reg.register("echo", "Echo", echo, parameters_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        })
        ctx = self._make_context()
        record = await reg.execute(ctx, "echo", {"text": "hi", "extra": "bad"})
        assert record.success is False
        assert "Unknown arguments" in record.error

    async def test_execute_validation_error_wrong_type(self):
        reg = self._make_registry()
        reg.register("echo", "Echo", echo, parameters_schema={
            "type": "object",
            "properties": {"text": {"type": "integer"}},
            "required": ["text"],
        })
        ctx = self._make_context()
        record = await reg.execute(ctx, "echo", {"text": "not_int"})
        assert record.success is False
        assert "must be integer" in record.error

    async def test_execute_high_risk_creates_approval(self):
        from backend.app.core.approvals import ApprovalStore
        approval_store = ApprovalStore()
        ctx = self._make_context()
        ctx.permission_scope.append("tool:dangerous")
        # Use a permissive policy that allows HIGH risk
        policy = MagicMock()
        policy.evaluate.return_value = ToolPolicyVerdict(
            allowed=True, requires_approval=False,
            sandbox_profile="default", reason="ok",
        )
        reg = ToolRegistry(policy_engine=policy, approval_store=approval_store)
        reg.register("dangerous", "Dangerous", echo, risk_level=RiskLevel.HIGH)
        record = await reg.execute(ctx, "dangerous", {"text": "x"})
        assert record.success is True

    async def test_execute_approved_no_store(self):
        reg = self._make_registry()
        ctx = self._make_context()
        record = await reg.execute_approved(ctx, "appr-1")
        assert record.success is False
        assert "not configured" in record.error

    async def test_execute_approved_not_found(self):
        from backend.app.core.approvals import ApprovalStore
        reg = ToolRegistry(policy_engine=ToolPolicyEngine(), approval_store=ApprovalStore())
        ctx = self._make_context()
        record = await reg.execute_approved(ctx, "nonexistent")
        assert record.success is False
        assert "not found" in record.error

    async def test_execute_batch(self):
        reg = self._make_registry()
        reg.register("echo", "Echo", echo)
        ctx = self._make_context()
        with patch("backend.app.core.parallel_tool_executor.ParallelToolExecutor") as MockExecutor:
            mock_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.tool_name = "echo"
            mock_result.success = True
            mock_result.output = "hi"
            mock_result.error = None
            mock_result.latency_ms = 1.0
            mock_instance.execute_batch = AsyncMock(return_value=[mock_result])
            MockExecutor.return_value = mock_instance
            records = await reg.execute_batch(ctx, [{"name": "echo", "arguments": {"text": "hi"}}])
            assert len(records) == 1

    def test_schema_from_signature(self):
        async def sample(x: int, y: str = "default") -> str:
            return y
        schema = ToolRegistry._schema_from_signature(sample)
        assert "x" in schema["properties"]
        assert schema["properties"]["x"]["type"] == "integer"
        assert "x" in schema["required"]
        assert "y" not in schema["required"]

    def test_json_schema_type(self):
        assert ToolRegistry._json_schema_type(int) == "integer"
        assert ToolRegistry._json_schema_type(float) == "number"
        assert ToolRegistry._json_schema_type(bool) == "boolean"
        assert ToolRegistry._json_schema_type(dict) == "object"
        assert ToolRegistry._json_schema_type(list) == "array"
        assert ToolRegistry._json_schema_type(str) == "string"
        assert ToolRegistry._json_schema_type(None) == "string"

    def test_validate_arguments_valid(self):
        schema = {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]}
        assert ToolRegistry._validate_arguments({"x": "hello"}, schema) is None

    def test_validate_arguments_missing_required(self):
        schema = {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]}
        assert "Missing required" in ToolRegistry._validate_arguments({}, schema)

    def test_validate_arguments_unknown(self):
        schema = {"type": "object", "properties": {"x": {"type": "string"}},
                  "required": [], "additionalProperties": False}
        assert "Unknown" in ToolRegistry._validate_arguments({"y": "bad"}, schema)

    def test_validate_arguments_type_mismatch(self):
        schema = {"type": "object", "properties": {"x": {"type": "integer"}}, "required": []}
        assert "must be integer" in ToolRegistry._validate_arguments({"x": "str"}, schema)

    def test_matches_json_type_bool_not_integer(self):
        assert ToolRegistry._matches_json_type(True, "integer") is False
        assert ToolRegistry._matches_json_type(True, "number") is False
        assert ToolRegistry._matches_json_type(42, "integer") is True
        assert ToolRegistry._matches_json_type(3.14, "number") is True
        assert ToolRegistry._matches_json_type("x", "unknown_type") is True

    def test_preview_arguments_truncation(self):
        long_val = "x" * 200
        preview = ToolRegistry._preview_arguments({"key": long_val})
        assert len(preview["key"]) <= 120
        assert preview["key"].endswith("...")

    def test_build_rollback_artifact(self):
        artifact = ToolRegistry._build_rollback_artifact(
            "write_file", {"path": "/tmp/f"}, {"path": "/tmp/f", "previous_size": 10, "current_size": 20, "verified": True, "applied": True}
        )
        assert artifact["tool_name"] == "write_file"
        assert artifact["path"] == "/tmp/f"
        assert artifact["previous_size"] == 10

    def test_build_rollback_artifact_non_dict_output(self):
        artifact = ToolRegistry._build_rollback_artifact("echo", {}, "text output")
        assert artifact["tool_name"] == "echo"
        assert "path" not in artifact

    def test_get_execution_store(self):
        store = ToolExecutionStore()
        reg = ToolRegistry(execution_store=store)
        assert reg.get_execution_store() is store


# ═══════════════════════════════════════════════════════════════════════════════
# FILE TOOL TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestFileTools:
    async def test_echo(self):
        assert await echo("hello") == "hello"

    async def test_summarize_text_short(self):
        assert await summarize_text("short text") == "short text"

    async def test_summarize_text_long(self):
        long_text = "word " * 100
        result = await summarize_text(long_text)
        assert len(result) <= 160
        assert result.endswith("...")

    async def test_normalize_text(self):
        assert await normalize_text("  hello   world  ") == "hello world"

    async def test_extract_keywords(self):
        result = await extract_keywords("Python is a great programming language for building applications")
        assert "python" in result
        assert len(result) <= 8

    async def test_extract_keywords_short_words_excluded(self):
        result = await extract_keywords("I am ok no it is")
        assert all(len(k) >= 3 for k in result)

    async def test_list_files(self, tmp_path):
        (tmp_path / "a.py").write_text("print('hi')")
        (tmp_path / "b.txt").write_text("hello")
        with patch("backend.app.core.tools._resolve_tool_root", return_value=tmp_path):
            result = await list_files(root=".")
            assert len(result) == 2

    async def test_list_files_nonexistent(self, tmp_path):
        with patch("backend.app.core.tools._resolve_tool_root", return_value=tmp_path / "nope"):
            result = await list_files(root=".")
            assert result == []

    async def test_inspect_tree(self, tmp_path):
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "file.py").write_text("x")
        with patch("backend.app.core.tools._resolve_tool_root", return_value=tmp_path):
            result = await inspect_tree(root=".")
            assert "files" in result
            assert "directories" in result

    async def test_inspect_tree_nonexistent(self, tmp_path):
        with patch("backend.app.core.tools._resolve_tool_root", return_value=tmp_path / "nope"):
            result = await inspect_tree(root=".")
            assert result["files"] == []

    async def test_read_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        with patch("backend.app.core.tools._resolve_tool_path", return_value=f):
            result = await read_file(path="test.txt")
            assert result == "hello world"

    async def test_read_file_nonexistent(self, tmp_path):
        with patch("backend.app.core.tools._resolve_tool_path", return_value=tmp_path / "nope.txt"):
            result = await read_file(path="nope.txt")
            assert result == ""

    async def test_write_file(self, tmp_path):
        f = tmp_path / "out.txt"
        with patch("backend.app.core.tools._resolve_tool_path", return_value=f):
            result = await write_file(path="out.txt", content="new content")
            assert result["written"] is True
            assert f.read_text() == "new content"

    async def test_write_file_with_backup(self, tmp_path):
        f = tmp_path / "out.txt"
        f.write_text("original")
        with patch("backend.app.core.tools._resolve_tool_path", return_value=f):
            result = await write_file(path="out.txt", content="updated", backup=True)
            assert result["previous_size"] == 8
            bak = tmp_path / "out.txt.bak"
            assert bak.read_text() == "original"

    async def test_preview_text_patch_success(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("def hello():\n    pass")
        with patch("backend.app.core.tools._resolve_tool_path", return_value=f):
            result = await preview_text_patch(path="code.py", old_text="pass", new_text="return 1")
            assert result["previewed"] is True
            assert result["match_count"] == 1

    async def test_preview_text_patch_not_found(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("def hello():\n    pass")
        with patch("backend.app.core.tools._resolve_tool_path", return_value=f):
            result = await preview_text_patch(path="code.py", old_text="nonexistent", new_text="x")
            assert result["previewed"] is False
            assert result["error"] == "pattern_not_found"

    async def test_preview_text_patch_ambiguous(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("aaa bbb aaa")
        with patch("backend.app.core.tools._resolve_tool_path", return_value=f):
            result = await preview_text_patch(path="code.py", old_text="aaa", new_text="ccc")
            assert result["previewed"] is False
            assert result["error"] == "ambiguous_match"

    async def test_preview_text_patch_replace_all(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("aaa bbb aaa")
        with patch("backend.app.core.tools._resolve_tool_path", return_value=f):
            result = await preview_text_patch(path="code.py", old_text="aaa", new_text="ccc", replace_all=True)
            assert result["previewed"] is True
            assert result["match_count"] == 2

    async def test_preview_text_patch_file_not_found(self, tmp_path):
        with patch("backend.app.core.tools._resolve_tool_path", return_value=tmp_path / "nope.py"):
            result = await preview_text_patch(path="nope.py", old_text="x", new_text="y")
            assert result["error"] == "file_not_found"

    async def test_apply_text_patch_success(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("def hello():\n    pass")
        with patch("backend.app.core.tools._resolve_tool_path", return_value=f):
            result = await apply_text_patch(path="code.py", old_text="pass", new_text="return 1")
            assert result["applied"] is True
            assert result["verified"] is True
            assert "return 1" in f.read_text()

    async def test_apply_text_patch_not_found(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("hello")
        with patch("backend.app.core.tools._resolve_tool_path", return_value=f):
            result = await apply_text_patch(path="code.py", old_text="xyz", new_text="abc")
            assert result["applied"] is False

    async def test_apply_text_patch_file_not_found(self, tmp_path):
        with patch("backend.app.core.tools._resolve_tool_path", return_value=tmp_path / "nope.py"):
            result = await apply_text_patch(path="nope.py", old_text="x", new_text="y")
            assert result["error"] == "file_not_found"

    async def test_apply_batch_patch(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("aaa bbb ccc")
        with patch("backend.app.core.tools._resolve_tool_path", return_value=f):
            result = await apply_batch_patch([
                {"path": "code.py", "old_text": "aaa", "new_text": "xxx"},
            ])
            assert result["success_count"] == 1

    async def test_search_text(self, tmp_path):
        (tmp_path / "a.py").write_text("import numpy")
        (tmp_path / "b.py").write_text("import pandas")
        with patch("backend.app.core.tools._resolve_tool_root", return_value=tmp_path):
            result = await search_text(root=".", query="numpy")
            assert len(result) == 1
            assert result[0]["path"] == "a.py"

    async def test_search_text_nonexistent_root(self, tmp_path):
        with patch("backend.app.core.tools._resolve_tool_root", return_value=tmp_path / "nope"):
            result = await search_text(root=".", query="x")
            assert result == []

    async def test_analyze_entrypoints(self, tmp_path):
        (tmp_path / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()")
        with patch("backend.app.core.tools._resolve_tool_root", return_value=tmp_path):
            result = await analyze_entrypoints(root=".")
            assert result["count"] >= 1

    async def test_analyze_entrypoints_nonexistent(self, tmp_path):
        with patch("backend.app.core.tools._resolve_tool_root", return_value=tmp_path / "nope"):
            result = await analyze_entrypoints(root=".")
            assert result["entrypoints"] == []

    async def test_analyze_dependencies(self, tmp_path):
        (tmp_path / "app.py").write_text("import os\nimport sys\nfrom pathlib import Path")
        with patch("backend.app.core.tools._resolve_tool_root", return_value=tmp_path):
            result = await analyze_dependencies(root=".")
            assert result["count"] >= 1

    async def test_analyze_dependencies_nonexistent(self, tmp_path):
        with patch("backend.app.core.tools._resolve_tool_root", return_value=tmp_path / "nope"):
            result = await analyze_dependencies(root=".")
            assert result["dependencies"] == []

    async def test_coordinate_files(self, tmp_path):
        f = tmp_path / "target.py"
        f.write_text("content")
        with patch("backend.app.core.tools._resolve_tool_root", return_value=tmp_path):
            with patch("backend.app.core.tools._resolve_tool_path", return_value=f):
                result = await coordinate_files(root=".", targets=["target.py"])
                assert result["count"] == 1

    async def test_preview_batch_patches(self, tmp_path):
        f = tmp_path / "code.py"
        f.write_text("hello world")
        with patch("backend.app.core.tools._resolve_tool_root", return_value=tmp_path):
            with patch("backend.app.core.tools._resolve_tool_path", return_value=f):
                result = await preview_batch_patches(
                    patches=[{"path": "code.py", "old_text": "hello", "new_text": "hi"}],
                    root=".",
                )
                assert result["total_count"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# build_default_tool_registry TEST
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildDefaultRegistry:
    def test_build(self):
        policy = ToolPolicyEngine()
        with patch("backend.app.core.hooks.get_hook_manager", return_value=MagicMock()):
            with patch("backend.app.core.collaboration.delegation.delegate_subtask", new=echo):
                reg = build_default_tool_registry(policy)
                assert reg.get("echo") is not None
                assert reg.get("read_file") is not None
                assert reg.get("write_file") is not None
                assert reg.get("apply_text_patch") is not None
                assert reg.get("search_text") is not None
