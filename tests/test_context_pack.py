from backend.app.core.context_pack import build_context_pack
from backend.app.core.contracts import RunContext
from backend.app.core.memory import InMemoryMemorySystem


async def test_context_pack_indexes_workspace_and_memory(tmp_path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (tmp_path / "source").mkdir()
    (tmp_path / "source" / "app.py").write_text("def run():\n    return 'ok'\n", encoding="utf-8")
    (tmp_path / ".xagent_runtime").mkdir()
    (tmp_path / ".xagent_runtime" / "ignored.py").write_text("ignored = True\n", encoding="utf-8")
    memory = InMemoryMemorySystem()
    context = RunContext(tenant_id="tenant-a", user_id="user-a", agent_id="agent-a")
    await memory.store(context, "Fix app.py validation failure", layer=3, importance=0.9, tags=["bugfix"])

    pack = await build_context_pack(
        memory=memory,
        context=context,
        task="Fix app.py validation failure",
        workspace_root=tmp_path,
        top_k=5,
        max_files=10,
    )

    assert pack["kind"] == "xagent_context_pack"
    assert pack["tenant_id"] == "tenant-a"
    assert pack["memory"]["hit_count"] == 1
    assert pack["memory"]["hits"][0]["tags"] == ["bugfix"]
    assert pack["workspace"]["exists"] is True
    assert pack["workspace"]["file_count"] == 2
    assert "pyproject.toml" == pack["workspace"]["key_files"][0]["path"]
    assert pack["repo"]["available"] is True
    assert pack["repo"]["test_config"]["suggested_commands"] == ["pytest"]
    assert all(".xagent_runtime" not in item["path"] for item in pack["workspace"]["key_files"])
    assert "Fix app.py validation failure" in pack["compression"]["summary"]
    assert "Suggested validation commands" in pack["compression"]["summary"]
    assert "Continue the task" in pack["resume_prompt"]
