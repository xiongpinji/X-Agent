from backend.app.core.contracts import AgentRunResponse, RunContext, RunStatus
from backend.app.core.runs import RunStore


def test_run_store_persists_records(tmp_path) -> None:
    path = tmp_path / "runs.jsonl"
    store = RunStore(storage_path=path)
    context = RunContext(tenant_id="tenant-a", user_id="user-a", trace_id="trace-run")
    response = AgentRunResponse(
        trace_id="trace-run",
        agent_id=context.agent_id,
        status=RunStatus.COMPLETED,
        answer="x" * 5_000,
        iterations=1,
        memory_hits=0,
    )

    store.save(context, "hello", response)

    reloaded = RunStore(storage_path=path)
    record = reloaded.get("trace-run")

    assert record is not None
    assert record.task == "hello"
    assert record.tenant_id == "tenant-a"
    assert record.answer == "x" * 4_000
