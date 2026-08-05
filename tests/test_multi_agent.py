"""
Tests for multi-agent functionality (agent_spawner 存活面).

历史注记（P1-09 批次 A，2026-08-04）：本文件原同时覆盖三个零生产引用的
幽灵模块（core/agent_coordinator、core/parallel_executor、core/agent_recovery），
该部分用例已随模块归档至 archive/dead_code_2026-08/tests/test_multi_agent_ghost_modules.py。
"""

import asyncio

import pytest

from backend.app.core.agent_spawner import agent_spawner


@pytest.mark.asyncio
async def test_spawn_agent():
    """Test spawning a single agent."""
    agent_id = await agent_spawner.spawn_agent(
        agent_type="test",
        task="test task",
        context={"key": "value"},
    )

    assert agent_id.startswith("agent_")
    assert agent_id in agent_spawner.agents

    status = await agent_spawner.get_agent_status(agent_id)
    assert status is not None
    assert status["agent_id"] == agent_id
    assert status["status"] in ["initializing", "ready", "running"]


@pytest.mark.asyncio
async def test_spawn_multiple_agents():
    """Test spawning multiple agents."""
    agent_ids = []

    for i in range(3):
        agent_id = await agent_spawner.spawn_agent(
            agent_type="test",
            task=f"task {i}",
            context={"index": i},
        )
        agent_ids.append(agent_id)

    assert len(agent_ids) == 3
    assert len(set(agent_ids)) == 3  # All unique

    agents = await agent_spawner.list_agents()
    assert len(agents) >= 3


@pytest.mark.asyncio
async def test_terminate_agent():
    """Test terminating an agent."""
    agent_id = await agent_spawner.spawn_agent(
        agent_type="test",
        task="test task",
        context={},
    )

    success = await agent_spawner.terminate_agent(agent_id)
    assert success

    status = await agent_spawner.get_agent_status(agent_id)
    assert status["status"] == "terminated"


@pytest.mark.asyncio
async def test_agent_max_concurrent_limit():
    """Test max concurrent agents limit."""
    spawner = agent_spawner.__class__(max_concurrent_agents=2)

    # Spawn 2 agents
    await spawner.spawn_agent(
        agent_type="test",
        task="task 1",
        context={},
    )
    await spawner.spawn_agent(
        agent_type="test",
        task="task 2",
        context={},
    )

    # Third should fail
    with pytest.raises(RuntimeError):
        await spawner.spawn_agent(
            agent_type="test",
            task="task 3",
            context={},
        )


@pytest.mark.asyncio
async def test_agent_spawner_stats():
    """Test agent spawner statistics."""
    stats = agent_spawner.get_stats()

    assert "total_agents" in stats
    assert "active_agents" in stats
    assert "status_breakdown" in stats
    assert "max_concurrent" in stats


@pytest.mark.asyncio
async def test_agent_cleanup():
    """Test cleanup of completed agents."""
    await agent_spawner.spawn_agent(
        agent_type="test",
        task="test task",
        context={},
    )

    # Wait for completion
    await asyncio.sleep(0.2)

    # Cleanup
    cleaned = await agent_spawner.cleanup_completed_agents(max_age_seconds=0)

    assert cleaned >= 0
