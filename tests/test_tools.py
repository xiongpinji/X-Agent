from backend.app.core.contracts import RunContext
from backend.app.core.policy import ToolPolicyEngine
from backend.app.core.tools import build_default_tool_registry


async def test_tool_manifest_exposes_json_schema() -> None:
    registry = build_default_tool_registry(ToolPolicyEngine())

    echo_definition = next(
        item
        for item in registry.definitions_for_llm()
        if item["function"]["name"] == "echo"
    )

    schema = echo_definition["function"]["parameters"]
    assert schema["type"] == "object"
    assert schema["required"] == ["text"]
    assert schema["properties"]["text"]["type"] == "string"


async def test_tool_execution_validates_required_arguments() -> None:
    registry = build_default_tool_registry(ToolPolicyEngine())

    context = RunContext()
    result = await registry.execute(context, "echo", {})

    assert result.success is False
    assert result.error == "Missing required argument: text"
    assert result.trace_id == context.trace_id
    assert result.request_id == context.request_id


async def test_tool_execution_rejects_unknown_arguments() -> None:
    registry = build_default_tool_registry(ToolPolicyEngine())

    result = await registry.execute(RunContext(), "echo", {"text": "ok", "extra": "bad"})

    assert result.success is False
    assert result.error == "Unknown arguments: extra"
    assert result.trace_id is not None
    assert result.request_id is not None
