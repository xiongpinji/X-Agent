"""Characterization tests for ``backend/app/core/tools.py``.

These tests LOCK IN the current observable behavior of the tool layer's pure
logic — path sandboxing, JSON-schema generation/validation, the local text
tools, and the ``ToolRegistry`` surface (register / get / manifest /
definitions_for_llm / capability_index / related_tools / execute). They are
deliberately written against behavior as it exists today, not against an
idealized spec, so that future refactors of this module are caught if they
change anything observable.

Notes for future maintainers:
- ``_is_path_forbidden`` does a lowercased string-prefix match against
  POSIX-style forbidden roots (``/etc`` etc.). On Windows that prefix never
  matches a real absolute path, so the forbidden check is effectively inert
  there. The platform-guarded assertions below document that as-is.
- ``RunContext()`` defaults grant ``tools:read``, so LOW-risk tools are
  allowed by the Phase-0 policy without extra scopes; HIGH-risk tools are
  blocked unless ``ToolPolicyEngine(enable_high_risk_tools=True)``.
"""

from __future__ import annotations

import os
import inspect
from pathlib import Path

import pytest

from backend.app.core.contracts import RiskLevel, RunContext
from backend.app.core.policy import ToolPolicyEngine
from backend.app.core.tools import (
    ToolRegistry,
    _is_path_forbidden,
    _resolve_tool_path,
    _resolve_tool_root,
    build_default_tool_registry,
    echo,
    extract_keywords,
    normalize_text,
    summarize_text,
)
from backend.app.settings import PROJECT_ROOT


# --------------------------------------------------------------------------- #
# Path sandboxing: _is_path_forbidden / _resolve_tool_path / _resolve_tool_root
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(os.name == "nt", reason="POSIX-style forbidden prefixes")
def test_is_path_forbidden_matches_system_roots_on_posix():
    # Each forbidden root and a child under it must be reported forbidden.
    assert _is_path_forbidden(Path("/etc")) is True
    assert _is_path_forbidden(Path("/etc/passwd")) is True
    assert _is_path_forbidden(Path("/proc/cpuinfo")) is True
    assert _is_path_forbidden(Path("/var/log/syslog")) is True
    assert _is_path_forbidden(Path("/tmp/whatever")) is True


def test_is_path_forbidden_allows_non_system_paths():
    # A path that does not start with any forbidden POSIX root is allowed.
    assert _is_path_forbidden(Path(str(PROJECT_ROOT))) is False
    # /var/lib is NOT in the forbidden set (only /var/log, /var/spool, /var/tmp).
    assert _is_path_forbidden(Path("/var/lib/data")) is False


@pytest.mark.skipif(os.name == "nt", reason="prefix match is case-insensitive on POSIX-style strings")
def test_is_path_forbidden_is_case_insensitive():
    assert _is_path_forbidden(Path("/ETC/passwd")) is True


def test_resolve_tool_path_accepts_path_inside_project():
    # A real path inside PROJECT_ROOT resolves and stays inside the base.
    inside = str(PROJECT_ROOT / "backend")
    resolved = _resolve_tool_path(inside)
    base = Path(PROJECT_ROOT).resolve()
    # Must be relative_to base (i.e. inside the sandbox).
    assert resolved.resolve().relative_to(base)


def test_resolve_tool_path_rejects_path_outside_project():
    # The parent of PROJECT_ROOT is outside the sandbox → PermissionError.
    outside = str(Path(PROJECT_ROOT).resolve().parent)
    with pytest.raises(PermissionError):
        _resolve_tool_path(outside)


def test_resolve_tool_root_accepts_inside_and_rejects_outside():
    inside = str(PROJECT_ROOT / "backend")
    base = Path(PROJECT_ROOT).resolve()
    assert _resolve_tool_root(inside).resolve().relative_to(base)

    outside = str(Path(PROJECT_ROOT).resolve().parent)
    with pytest.raises(PermissionError):
        _resolve_tool_root(outside)


# --------------------------------------------------------------------------- #
# JSON schema type mapping: _json_schema_type
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "annotation, expected",
    [
        (int, "integer"),
        ("int", "integer"),
        (float, "number"),
        ("float", "number"),
        (bool, "boolean"),
        ("bool", "boolean"),
        (dict, "object"),
        ("dict", "object"),
        (list, "array"),
        ("list", "array"),
        (str, "string"),
        ("str", "string"),
        (inspect.Parameter.empty, "string"),  # unknown → string
        (object, "string"),  # any other type → string
    ],
)
def test_json_schema_type_mapping(annotation, expected):
    assert ToolRegistry._json_schema_type(annotation) == expected


# --------------------------------------------------------------------------- #
# Schema from signature: _schema_from_signature
# --------------------------------------------------------------------------- #


def test_schema_from_signature_marks_only_defaultless_params_required():
    async def handler(text: str, count: int = 3, flag: bool = False):
        return None

    schema = ToolRegistry._schema_from_signature(handler)

    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    # Only ``text`` has no default → required.
    assert schema["required"] == ["text"]
    assert schema["properties"]["text"]["type"] == "string"
    assert schema["properties"]["count"]["type"] == "integer"
    assert schema["properties"]["flag"]["type"] == "boolean"
    # Description shape is fixed.
    assert schema["properties"]["text"]["description"] == "Argument text"


def test_schema_from_signature_no_params():
    async def handler():
        return None

    schema = ToolRegistry._schema_from_signature(handler)
    assert schema["properties"] == {}
    assert schema["required"] == []


# --------------------------------------------------------------------------- #
# Argument validation: _validate_arguments
# --------------------------------------------------------------------------- #


def _schema(properties, required, additional=False):
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": additional,
    }


def test_validate_arguments_missing_required():
    schema = _schema({"text": {"type": "string"}}, ["text"])
    err = ToolRegistry._validate_arguments({}, schema)
    assert err == "Missing required argument: text"


def test_validate_arguments_unknown_when_additional_false():
    schema = _schema({"text": {"type": "string"}}, [])
    err = ToolRegistry._validate_arguments({"text": "x", "bogus": 1}, schema)
    assert err == "Unknown arguments: bogus"


def test_validate_arguments_unknown_allowed_when_additional_true():
    schema = _schema({"text": {"type": "string"}}, [], additional=True)
    err = ToolRegistry._validate_arguments({"text": "x", "extra": 1}, schema)
    assert err is None


def test_validate_arguments_type_mismatch():
    schema = _schema({"count": {"type": "integer"}}, [])
    err = ToolRegistry._validate_arguments({"count": "not-int"}, schema)
    assert err == "Argument count must be integer."


def test_validate_arguments_all_good():
    schema = _schema(
        {"text": {"type": "string"}, "count": {"type": "integer"}},
        ["text"],
    )
    assert ToolRegistry._validate_arguments({"text": "hi", "count": 2}, schema) is None


# --------------------------------------------------------------------------- #
# Type matching: _matches_json_type
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "value, expected_type, ok",
    [
        ("s", "string", True),
        (1, "string", False),
        (1, "integer", True),
        (True, "integer", False),  # bool explicitly excluded from integer
        (1.5, "number", True),
        (2, "number", True),  # int counts as number
        (True, "number", False),  # bool explicitly excluded from number
        (True, "boolean", True),
        (1, "boolean", False),
        ({}, "object", True),
        ([], "array", True),
        ("x", "array", False),
        ("anything", "unknown-type", True),  # unknown type → always True
    ],
)
def test_matches_json_type(value, expected_type, ok):
    assert ToolRegistry._matches_json_type(value, expected_type) is ok


# --------------------------------------------------------------------------- #
# Local text tools: echo / summarize_text / normalize_text / extract_keywords
# --------------------------------------------------------------------------- #


async def test_echo_returns_input_verbatim():
    assert await echo("hello world") == "hello world"
    assert await echo("") == ""


async def test_summarize_text_collapses_whitespace_short():
    assert await summarize_text("  a   b\tc\n d ") == "a b c d"


async def test_summarize_text_truncates_long_with_ellipsis():
    long = "x" * 300
    out = await summarize_text(long)
    assert len(out) == 160
    assert out.endswith("...")
    assert out[:157] == "x" * 157


async def test_summarize_text_boundary_160_not_truncated():
    text = "y" * 160
    out = await summarize_text(text)
    assert out == text  # exactly 160 → returned as-is


async def test_normalize_text_collapses_all_whitespace():
    assert await normalize_text("a\n\n  b\t c  ") == "a b c"


async def test_extract_keywords_filters_short_strips_punct_dedups():
    # < 3 chars dropped ("a", "an"); note "the" is len 3 so it is KEPT.
    text = "Hello, hello WORLD! a an code-base. code-base?"
    out = await extract_keywords(text)
    # punctuation stripped; lowercased; de-duped; inner hyphen preserved.
    assert out == ["hello", "world", "code-base"]


async def test_extract_keywords_keeps_three_char_tokens():
    # Boundary: length-3 tokens survive the ``len(cleaned) < 3`` filter.
    out = await extract_keywords("the cat dog")
    assert out == ["the", "cat", "dog"]


async def test_extract_keywords_respects_limit():
    text = "alpha bravo charlie delta echo foxtrot"
    out = await extract_keywords(text, limit=2)
    assert out == ["alpha", "bravo"]


async def test_extract_keywords_limit_floor_is_one():
    # max(1, limit) → a non-positive limit still yields at least one token.
    out = await extract_keywords("alpha bravo charlie", limit=0)
    assert out == ["alpha"]


# --------------------------------------------------------------------------- #
# ToolRegistry: register / get / definitions_for_llm / manifest
# --------------------------------------------------------------------------- #


def _registry() -> ToolRegistry:
    return ToolRegistry(ToolPolicyEngine())


async def _handler(text: str, count: int = 1):
    return {"text": text, "count": count}


def test_register_derives_schema_and_default_scope():
    reg = _registry()
    reg.register("do_thing", "Does a thing.", _handler)
    tool = reg.get("do_thing")
    assert tool is not None
    assert tool.name == "do_thing"
    assert tool.description == "Does a thing."
    assert tool.risk_level == RiskLevel.LOW
    # Default scope is tool:<name> when none provided.
    assert tool.required_scope == "tool:do_thing"
    # Schema derived from the handler signature.
    assert tool.parameters_schema["required"] == ["text"]
    assert tool.parameters_schema["properties"]["count"]["type"] == "integer"


def test_register_respects_explicit_scope_and_schema():
    reg = _registry()
    custom_schema = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}
    reg.register(
        "danger",
        "High risk.",
        _handler,
        risk_level=RiskLevel.HIGH,
        required_scope="tool:custom",
        parameters_schema=custom_schema,
    )
    tool = reg.get("danger")
    assert tool.risk_level == RiskLevel.HIGH
    assert tool.required_scope == "tool:custom"
    assert tool.parameters_schema is custom_schema


def test_get_unknown_returns_none():
    assert _registry().get("nope") is None


def test_definitions_for_llm_shape():
    reg = _registry()
    reg.register("do_thing", "Does a thing.", _handler)
    defs = reg.definitions_for_llm()
    assert len(defs) == 1
    entry = defs[0]
    assert entry["type"] == "function"
    fn = entry["function"]
    assert fn["name"] == "do_thing"
    assert fn["description"] == "Does a thing."
    assert fn["x-risk-level"] == "low"
    assert fn["x-required-scope"] == "tool:do_thing"
    assert "parameters" in fn


def test_manifest_shape():
    reg = _registry()
    reg.register("do_thing", "Does a thing.", _handler, risk_level=RiskLevel.MEDIUM)
    manifest = reg.manifest()
    assert manifest == [
        {
            "name": "do_thing",
            "description": "Does a thing.",
            "risk_level": "medium",
            "required_scope": "tool:do_thing",
            "parameters": reg.get("do_thing").parameters_schema,
        }
    ]


# --------------------------------------------------------------------------- #
# ToolRegistry: capability_index / related_tools
# --------------------------------------------------------------------------- #


def test_capability_index_buckets():
    reg = _registry()
    reg.register("reader", "r", _handler)            # 'read' → read
    reg.register("search_docs", "s", _handler)       # 'search' → search
    reg.register("writer", "w", _handler)            # 'write' → write
    reg.register("helper", "h", _handler)            # none → utility
    reg.register("code_tool", "c", _handler)         # 'code' → code

    index = reg.capability_index()
    names = {bucket: [t["name"] for t in items] for bucket, items in index.items()}

    assert "reader" in names["read"]
    assert "search_docs" in names["search"]
    assert "writer" in names["write"]
    assert "helper" in names["utility"]
    assert "code_tool" in names["code"]


def test_capability_index_write_then_code_override():
    # 'write_file' matches both 'write' and 'file'; 'file' check runs last and
    # overwrites the bucket → ends up in 'code'. Locks the precedence as-is.
    reg = _registry()
    reg.register("write_file", "w", _handler)
    index = reg.capability_index()
    assert "write_file" in [t["name"] for t in index["code"]]
    assert "write_file" not in [t["name"] for t in index["write"]]


def test_related_tools_scores_and_orders():
    reg = _registry()
    reg.register("read_notes", "read the notes", _handler)
    reg.register("write_logs", "write the logs", _handler)
    reg.register("echo", "echo text back", _handler)

    related = reg.related_tools("notes")
    names = [t["name"] for t in related]
    # 'echo' has no token match and is neither read nor write → score 0 → excluded.
    assert "echo" not in names
    # read_notes: token 'notes' (+1) + read keyword (+1) = 2; write_logs: write keyword (+1) = 1.
    assert names[0] == "read_notes"
    assert "write_logs" in names


def test_related_tools_caps_at_eight():
    reg = _registry()
    for i in range(12):
        reg.register(f"read_tool_{i}", "reads stuff", _handler)
    related = reg.related_tools("reads")
    assert len(related) == 8


# --------------------------------------------------------------------------- #
# ToolRegistry.execute: policy + validation + dispatch
# --------------------------------------------------------------------------- #


async def test_execute_unknown_tool_fails():
    reg = _registry()
    rec = await reg.execute(RunContext(), "ghost", {})
    assert rec.success is False
    assert rec.error == "Unknown tool: ghost"


async def test_execute_low_risk_allowed_and_returns_output():
    reg = _registry()
    reg.register("echo", "Echo text.", echo)
    rec = await reg.execute(RunContext(), "echo", {"text": "hi"})
    assert rec.success is True
    assert rec.output == "hi"
    assert rec.error is None
    assert rec.tool_name == "echo"


async def test_execute_high_risk_blocked_without_approval():
    reg = _registry()  # enable_high_risk_tools=False by default
    reg.register("danger", "High risk.", echo, risk_level=RiskLevel.HIGH)
    rec = await reg.execute(RunContext(), "danger", {"text": "x"})
    assert rec.success is False
    assert rec.policy.allowed is False
    assert "high" in rec.error.lower()


async def test_execute_missing_permission_scope_blocked():
    reg = _registry()
    reg.register("echo", "Echo text.", echo)
    # Context with no tools:read / tools:* / tool:echo → blocked by policy.
    ctx = RunContext(permission_scope=[])
    rec = await reg.execute(ctx, "echo", {"text": "x"})
    assert rec.success is False
    assert "permission scope" in rec.error.lower()


async def test_execute_validation_error_for_missing_required_arg():
    reg = _registry()
    reg.register("echo", "Echo text.", echo)  # echo(text: str) → text required
    rec = await reg.execute(RunContext(), "echo", {})
    assert rec.success is False
    assert rec.error == "Missing required argument: text"


async def test_execute_handler_exception_is_captured():
    async def boom(text: str):
        raise ValueError("kaboom")

    reg = _registry()
    reg.register("boom", "Raises.", boom)
    rec = await reg.execute(RunContext(), "boom", {"text": "x"})
    assert rec.success is False
    assert rec.error == "kaboom"


# --------------------------------------------------------------------------- #
# build_default_tool_registry: wiring of the standard toolset
# --------------------------------------------------------------------------- #


def test_build_default_tool_registry_registers_expected_tools():
    reg = build_default_tool_registry(ToolPolicyEngine())
    names = {t["name"] for t in reg.manifest()}
    # A representative slice of the standard toolset must be present.
    expected = {
        "echo",
        "list_files",
        "read_file",
        "write_file",
        "apply_text_patch",
        "search_text",
        "summarize_text",
        "normalize_text",
        "extract_keywords",
    }
    assert expected.issubset(names)


def test_build_default_tool_registry_marks_write_tools_high_risk():
    reg = build_default_tool_registry(ToolPolicyEngine())
    by_name = {t["name"]: t for t in reg.manifest()}
    assert by_name["write_file"]["risk_level"] == "high"
    assert by_name["apply_text_patch"]["risk_level"] == "high"
    assert by_name["apply_batch_patch"]["risk_level"] == "high"
    # A read tool stays low.
    assert by_name["read_file"]["risk_level"] == "low"
