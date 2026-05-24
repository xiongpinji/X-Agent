from backend.app.core.contracts import RunContext
from backend.app.core.memory import MemorySystem
from backend.app.core.tracing import TraceStore


async def test_memory_persists_to_jsonl(tmp_path) -> None:
    path = tmp_path / "memory.jsonl"
    memory = MemorySystem(storage_path=path)
    context = RunContext(tenant_id="tenant-a")

    item_id = await memory.store(context, content="persistent note", layer=3)

    assert item_id
    assert path.exists()

    reloaded = MemorySystem(storage_path=path)
    hits = await reloaded.search(context, "persistent", layers=[3], top_k=5)

    assert len(hits) == 1
    assert hits[0].content == "persistent note"


def test_trace_persists_to_jsonl(tmp_path) -> None:
    path = tmp_path / "trace.jsonl"
    tracer = TraceStore(storage_path=path)
    context = RunContext(trace_id="trace-1")

    tracer.record(context, "agent.started", task="hello")
    tracer.record(context, "agent.completed", status="ok")

    assert path.exists()

    reloaded = TraceStore(storage_path=path)
    events = reloaded.list_events("trace-1")

    assert [event.event for event in events] == ["agent.started", "agent.completed"]

