from __future__ import annotations

import pytest

from backend.app.core.agent_registry import (
    AgentCreateRequest,
    AgentParentUpdateRequest,
    AgentRegistryStore,
    AgentRole,
    SubAgentCreateRequest,
)


def test_agent_registry_creates_main_agent_with_org_and_subagents(tmp_path) -> None:
    store = AgentRegistryStore(tmp_path / "agents.json")

    tree = store.create_tree(
        AgentCreateRequest(
            name="Delivery Lead",
            organization_name="AgentCore",
            organization_units=[
                {"name": "Strategy", "title": "Planning", "agent_name": "Planner"},
                {"name": "Execution", "title": "Tools", "agent_name": "Executor"},
            ],
            subagents=[
                {"name": "Reviewer", "description": "Checks delivery quality."},
            ],
        )
    )

    assert tree.agent.role == AgentRole.MAIN
    assert len(tree.subagents) == 3
    assert len(tree.organization_units) == 2
    assert all(unit.agent_id for unit in tree.organization_units)
    assert tree.snapshot["subagents"] == 3
    assert tree.organization_tree

    reloaded = AgentRegistryStore(tmp_path / "agents.json")
    assert reloaded.summary().main == 1
    assert reloaded.summary().sub == 3


def test_agent_registry_supports_nested_hierarchy_and_move(tmp_path) -> None:
    store = AgentRegistryStore(tmp_path / "agents.json")
    tree = store.create_tree(AgentCreateRequest(name="Main"))
    first = store.create_subagent(tree.agent.id, SubAgentCreateRequest(name="Manager"))
    assert first is not None
    second = store.create_subagent(first.id, SubAgentCreateRequest(name="Specialist"))
    assert second is not None

    hierarchy = store.tree(tree.agent.id).hierarchy
    assert hierarchy["children"][0]["id"] == first.id
    assert hierarchy["children"][0]["children"][0]["id"] == second.id

    moved = store.move(second.id, AgentParentUpdateRequest(parent_agent_id=tree.agent.id))
    assert moved is not None
    updated = store.tree(tree.agent.id).hierarchy
    direct_child_ids = {child["id"] for child in updated["children"]}
    assert {first.id, second.id} <= direct_child_ids


def test_agent_registry_rejects_hierarchy_cycles(tmp_path) -> None:
    store = AgentRegistryStore(tmp_path / "agents.json")
    tree = store.create_tree(AgentCreateRequest(name="Main"))
    first = store.create_subagent(tree.agent.id, SubAgentCreateRequest(name="Manager"))
    assert first is not None

    with pytest.raises(ValueError, match="cycles"):
        store.move(tree.agent.id, AgentParentUpdateRequest(parent_agent_id=first.id))


def test_agent_registry_persists_per_agent_model_settings(tmp_path) -> None:
    store = AgentRegistryStore(tmp_path / "agents.json")

    tree = store.create_tree(
        AgentCreateRequest(
            name="Model Routed Team",
            model_provider="dashscope",
            model_name="qwen-plus",
            organization_units=[
                {
                    "name": "Reviewer",
                    "title": "Review",
                    "agent_name": "Review Agent",
                    "model_provider": "deepseek",
                    "model_name": "deepseek-chat",
                }
            ],
            subagents=[
                {
                    "name": "Local Worker",
                    "model_provider": "ollama",
                    "model_name": "llama3.1",
                },
            ],
        )
    )

    assert tree.agent.model_provider == "dashscope"
    assert tree.agent.model_name == "qwen-plus"
    assert {child.model_provider for child in tree.subagents} == {"deepseek", "ollama"}
    hierarchy = store.tree(tree.agent.id).hierarchy
    assert hierarchy["model_provider"] == "dashscope"
    assert {child["model_provider"] for child in hierarchy["children"]} == {"deepseek", "ollama"}


def test_agent_registry_ensures_dynamic_subagents_and_runtime_context(tmp_path) -> None:
    store = AgentRegistryStore(tmp_path / "agents.json")
    tree = store.create_tree(
        AgentCreateRequest(
            name="Autonomous Lead",
            model_provider="ollama",
            model_name="qwen2.5",
            max_dynamic_subagents=2,
        )
    )

    children = store.ensure_dynamic_subagents(
        tree.agent.id,
        task="implement feature",
        route="code",
    )
    refreshed = store.tree(tree.agent.id)
    context = store.runtime_context(refreshed.agent, refreshed.subagents)

    assert len(children) == 2
    assert store.summary().dynamic_subagents == 2
    assert {child.metadata["route"] for child in children} == {"code"}
    assert context["model_provider"] == "ollama"
    assert context["subagents"]
    assert context["hierarchy"]["children"]


def test_agent_registry_delete_cascades_descendants(tmp_path) -> None:
    store = AgentRegistryStore(tmp_path / "agents.json")
    tree = store.create_tree(AgentCreateRequest(name="Main"))
    first = store.create_subagent(tree.agent.id, SubAgentCreateRequest(name="Manager"))
    assert first is not None
    second = store.create_subagent(first.id, SubAgentCreateRequest(name="Specialist"))
    assert second is not None

    assert store.delete(first.id) is True

    assert store.get(first.id) is None
    assert store.get(second.id) is None
    assert store.summary().count == 1
