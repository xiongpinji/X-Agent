import json
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            ts TEXT NOT NULL,
            sender TEXT NOT NULL,
            recipient TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            read_at TEXT
        );
        """
    )



def persist_message(
    conn: sqlite3.Connection,
    *,
    sender: str,
    recipient: str,
    subject: str,
    body: str,
    task_id: str | None,
    status: str | None,
    summary: str | None,
) -> None:
    import uuid
    from datetime import datetime, timezone

    payload = {
        "body": body,
        "task_id": task_id,
        "status": status,
        "summary": summary,
    }
    conn.execute(
        "INSERT INTO messages(id, ts, sender, recipient, subject, body) VALUES(?,?,?,?,?,?)",
        (
            str(uuid.uuid4()),
            datetime.now(timezone.utc).isoformat(),
            sender,
            recipient,
            subject,
            json.dumps(payload, ensure_ascii=False),
        ),
    )



def make_paths(tmp_path: Path):
    import scripts.claude_controller_loop as loop

    comm = tmp_path / "audit_reports" / "_comm"
    packets = comm / "task_packets"
    packets.mkdir(parents=True)
    return loop.ControllerPaths(
        repo_root=tmp_path,
        db_path=comm / "blackboard.sqlite",
        task_board_path=comm / "CURRENT_TASK_BOARD.json",
        session_recovery_path=comm / "SESSION_RECOVERY.md",
        verification_ledger_path=comm / "VERIFICATION_LEDGER.md",
        decision_log_path=comm / "DECISION_LOG.md",
        task_packet_dir=packets,
    )


def write_runtime_files(paths, *, status: str = "in_progress", second_task_status: str | None = None) -> None:
    tasks = [
        {
            "task_id": "T-001",
            "title": "Test task",
            "owner": "codex",
            "status": status,
            "priority": "P0",
            "next_step": "waiting",
        }
    ]
    if second_task_status:
        tasks.append(
            {
                "task_id": "T-002",
                "title": "Next task",
                "owner": "codex",
                "status": second_task_status,
                "priority": "P1",
                "next_step": "ready",
            }
        )
    board = {
        "generated_at": "2026-06-29T00:00:00+00:00",
        "controller": "claude_code",
        "executor": "codex",
        "tasks": tasks,
        "next_recommended_tasks": [task["task_id"] for task in tasks],
    }
    paths.task_board_path.parent.mkdir(parents=True, exist_ok=True)
    paths.task_board_path.write_text(json.dumps(board), encoding="utf-8")
    paths.session_recovery_path.write_text(
        "# SESSION RECOVERY\n\n"
        "Last Updated: 2026-06-29 00:00\n\n"
        "## Active Tasks\n"
        "- T-001：Test task，状态：in_progress\n\n"
        "## Latest Verified Evidence\n\n"
        "## Critical Decisions\n",
        encoding="utf-8",
    )
    paths.verification_ledger_path.write_text(
        "# VERIFICATION LEDGER\n\n## VERIFIED\n\n## FAILED / OPEN\n",
        encoding="utf-8",
    )
    paths.decision_log_path.write_text("# DECISION LOG\n", encoding="utf-8")


def write_packet(paths, task_id: str, command: str) -> None:
    packet = {
        "task_id": task_id,
        "title": "Test task" if task_id == "T-001" else "Next task",
        "assigned_to": "codex",
        "allowed_files": ["docs/**", "tests/**"],
        "forbidden_files": ["backend/**"],
        "verification_commands": [command],
    }
    (paths.task_packet_dir / f"{task_id}.json").write_text(
        json.dumps(packet),
        encoding="utf-8",
    )


def write_inbox_receipt(
    paths,
    filename: str,
    *,
    task_id: str,
    status: str,
    subject: str,
    line_ending: str = "\n",
) -> None:
    inbox = paths.task_board_path.parent / "inbox_zcode"
    inbox.mkdir(parents=True, exist_ok=True)
    content = line_ending.join(
        [
            "---",
            "from: codex",
            "to: zcode",
            "ts: 2026-06-29T22:26:17+00:00",
            f"task_id: {task_id}",
            f"status: {status}",
            "---",
            "",
            f"# {subject}",
            "",
            "done",
            "",
        ]
    )
    (inbox / filename).write_text(content, encoding="utf-8")


def seed_message(paths, subject: str, *, task_id: str, status: str) -> None:
    conn = sqlite3.connect(paths.db_path)
    try:
        ensure_schema(conn)
        persist_message(
            conn,
            sender="codex",
            recipient="zcode",
            subject=subject,
            body="body",
            task_id=task_id,
            status=status,
            summary=subject,
        )
        conn.commit()
    finally:
        conn.close()


@dataclass(frozen=True)
class FakeWorkerResult:
    status: str
    returncode: int
    message: str
    task_id: str | None = None
    packet_path: str | None = None


def test_controller_loop_verifies_done_waiting_review_message(tmp_path):
    import scripts.claude_controller_loop as loop

    paths = make_paths(tmp_path)
    write_runtime_files(paths)
    write_packet(paths, "T-001", f'"{sys.executable}" -c "print(123)"')
    seed_message(
        paths,
        "T-001 done_waiting_review",
        task_id="T-001",
        status="done_waiting_review",
    )

    result = loop.run_once(paths, auto_dispatch=False, max_passes=1)

    board = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    task = board["tasks"][0]
    assert task["status"] == "verified"
    assert "verified T-001" in result["events"]
    assert "V-AUTO-T-001" in paths.verification_ledger_path.read_text(encoding="utf-8")
    assert "状态：verified" in paths.session_recovery_path.read_text(encoding="utf-8")
    assert loop.load_unread_codex_messages(paths) == []


def test_controller_loop_creates_repair_packet_on_verification_failure(tmp_path):
    import scripts.claude_controller_loop as loop

    paths = make_paths(tmp_path)
    write_runtime_files(paths, status="done_waiting_review")
    write_packet(paths, "T-001", f'"{sys.executable}" -c "import sys; sys.exit(7)"')

    result = loop.run_once(paths, auto_dispatch=False, max_passes=1)

    board = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    source_task = board["tasks"][0]
    repair_tasks = [task for task in board["tasks"] if task["task_id"].startswith("T-001-REPAIR-")]
    repair_packets = list(paths.task_packet_dir.glob("T-001-REPAIR-*.json"))
    assert source_task["status"] == "repair_requested"
    assert repair_tasks and repair_tasks[0]["status"] == "ready_for_dispatch"
    assert repair_packets
    assert any(event.startswith("repair_requested T-001") for event in result["events"])


def test_controller_loop_verifies_then_auto_dispatches_next_task(monkeypatch, tmp_path):
    import scripts.claude_controller_loop as loop

    paths = make_paths(tmp_path)
    write_runtime_files(paths, second_task_status="ready_for_dispatch")
    write_packet(paths, "T-001", f'"{sys.executable}" -c "print(123)"')
    write_packet(paths, "T-002", f'"{sys.executable}" -c "print(456)"')
    seed_message(paths, "T-001 done_waiting_review", task_id="T-001", status="done_waiting_review")

    monkeypatch.setattr(
        loop,
        "run_worker_once_result",
        lambda **kwargs: FakeWorkerResult(
            status="dispatched",
            returncode=0,
            message="Dispatch completed for T-002",
            task_id="T-002",
            packet_path=str(paths.task_packet_dir / "T-002.json"),
        ),
    )

    result = loop.run_once(paths, auto_dispatch=True, max_passes=1)

    board = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    t1 = next(task for task in board["tasks"] if task["task_id"] == "T-001")
    assert t1["status"] == "verified"
    assert "verified T-001" in result["events"]
    assert any(event.startswith("worker_dispatched T-002") for event in result["events"])


def test_controller_loop_unblocks_and_dispatches_task(monkeypatch, tmp_path):
    import scripts.claude_controller_loop as loop

    paths = make_paths(tmp_path)
    write_runtime_files(paths, status="blocked")
    write_packet(paths, "T-001", f'"{sys.executable}" -c "print(123)"')

    monkeypatch.setattr(
        loop,
        "run_worker_once_result",
        lambda **kwargs: FakeWorkerResult(
            status="dispatched",
            returncode=0,
            message="Dispatch completed for T-001",
            task_id="T-001",
            packet_path=str(paths.task_packet_dir / "T-001.json"),
        ),
    )

    result = loop.run_once(paths, auto_dispatch=True, max_passes=1)

    assert any(event == "unblocked T-001" for event in result["events"])
    assert any(event.startswith("worker_dispatched T-001") for event in result["events"])


def test_controller_loop_prioritizes_repair_task(monkeypatch, tmp_path):
    import scripts.claude_controller_loop as loop

    paths = make_paths(tmp_path)
    write_runtime_files(paths, status="done_waiting_review")
    write_packet(paths, "T-001", f'"{sys.executable}" -c "import sys; sys.exit(7)"')

    monkeypatch.setattr(
        loop,
        "run_worker_once_result",
        lambda **kwargs: FakeWorkerResult(
            status="dispatched",
            returncode=0,
            message="Dispatch completed for repair",
            task_id="T-001-REPAIR-123",
            packet_path=str(paths.task_packet_dir / "T-001-REPAIR-123.json"),
        ),
    )

    result = loop.run_once(paths, auto_dispatch=True, max_passes=1)

    board = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    assert board["next_recommended_tasks"][0].startswith("T-001-REPAIR-")
    assert any(event.startswith("repair_requested T-001") for event in result["events"])


def test_controller_loop_defaults_to_verifier_mode_without_worker_dispatch(monkeypatch, tmp_path):
    import scripts.claude_controller_loop as loop

    paths = make_paths(tmp_path)
    write_runtime_files(paths, status="done_waiting_review", second_task_status="ready_for_dispatch")
    write_packet(paths, "T-001", f'"{sys.executable}" -c "print(123)"')
    write_packet(paths, "T-002", f'"{sys.executable}" -c "print(456)"')

    called = {"value": False}

    def fake_worker(**kwargs):
        called["value"] = True
        raise AssertionError("worker should not be called in verifier mode")

    monkeypatch.setattr(loop, "run_worker_once_result", fake_worker)

    result = loop.run_once(paths, auto_dispatch=False, max_passes=1)

    board = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    t1 = next(task for task in board["tasks"] if task["task_id"] == "T-001")
    t2 = next(task for task in board["tasks"] if task["task_id"] == "T-002")
    assert t1["status"] == "verified"
    assert t2["status"] == "ready_for_dispatch"
    assert called["value"] is False
    assert "verified T-001" in result["events"]


def test_controller_loop_promotes_next_queued_task_after_verification(tmp_path):
    import scripts.claude_controller_loop as loop

    paths = make_paths(tmp_path)
    write_runtime_files(paths)
    board = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    board["tasks"] = [
        {
            "task_id": "P1-CODEX-PRODUCTIZATION-003",
            "title": "done task",
            "owner": "codex",
            "status": "done_waiting_review",
            "priority": "P1",
            "next_step": "waiting verify",
        },
        {
            "task_id": "P1-CODEX-PRODUCTIZATION-004",
            "title": "queued next task",
            "owner": "codex",
            "status": "queued",
            "priority": "P1",
            "next_step": "wait prior verify",
        },
    ]
    board["next_recommended_tasks"] = [
        "P1-CODEX-PRODUCTIZATION-003",
        "P1-CODEX-PRODUCTIZATION-004",
    ]
    paths.task_board_path.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")
    write_packet(paths, "P1-CODEX-PRODUCTIZATION-003", f'"{sys.executable}" -c "print(123)"')
    write_packet(paths, "P1-CODEX-PRODUCTIZATION-004", f'"{sys.executable}" -c "print(456)"')

    result = loop.run_once(paths, auto_dispatch=False, max_passes=1)

    updated = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    done_task = next(task for task in updated["tasks"] if task["task_id"] == "P1-CODEX-PRODUCTIZATION-003")
    next_task = next(task for task in updated["tasks"] if task["task_id"] == "P1-CODEX-PRODUCTIZATION-004")
    assert done_task["status"] == "verified"
    assert next_task["status"] == "ready_for_dispatch"
    assert any(event == "promoted P1-CODEX-PRODUCTIZATION-004" for event in result["events"])


def test_controller_loop_reconciles_missing_packets_after_no_task_report(tmp_path):
    import scripts.claude_controller_loop as loop

    paths = make_paths(tmp_path)
    write_runtime_files(paths, status="verified")
    board = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    board["tasks"] = []
    board["next_recommended_tasks"] = []
    paths.task_board_path.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")

    packet = {
        "task_id": "P1-CODEX-PRODUCTIZATION-099",
        "title": "reconciled task",
        "assigned_to": "codex",
        "priority": "P1",
        "verification_commands": [],
    }
    (paths.task_packet_dir / "P1-CODEX-PRODUCTIZATION-099.json").write_text(
        json.dumps(packet, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    conn = sqlite3.connect(paths.db_path)
    try:
        ensure_schema(conn)
        persist_message(
            conn,
            sender="codex",
            recipient="zcode",
            subject="codex_worker no_task_request_more_task_packets",
            body="Codex worker status: no_task",
            task_id=None,
            status=None,
            summary="no_task",
        )
        conn.commit()
    finally:
        conn.close()

    result = loop.run_once(paths, auto_dispatch=False, max_passes=1)

    updated = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    task = next(task for task in updated["tasks"] if task["task_id"] == "P1-CODEX-PRODUCTIZATION-099")
    assert task["status"] == "ready_for_dispatch"
    assert any(event == "reconciled_missing_task P1-CODEX-PRODUCTIZATION-099" for event in result["events"])
    assert loop.load_unread_codex_messages(paths) == []


def test_controller_loop_reconciles_ready_tasks_after_no_task_report(tmp_path):
    import scripts.claude_controller_loop as loop

    paths = make_paths(tmp_path)
    write_runtime_files(paths, status="verified")
    board = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    board["tasks"] = [
        {
            "task_id": "P1-CODEX-PRODUCTIZATION-001",
            "title": "stale task",
            "owner": "codex",
            "status": "verified",
            "priority": "P1",
            "next_step": "already done",
        }
    ]
    board["next_recommended_tasks"] = ["P1-CODEX-PRODUCTIZATION-099"]
    paths.task_board_path.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")

    packet = {
        "task_id": "P1-CODEX-PRODUCTIZATION-099",
        "title": "reconciled task",
        "assigned_to": "codex",
        "priority": "P1",
        "verification_commands": [],
    }
    (paths.task_packet_dir / "P1-CODEX-PRODUCTIZATION-099.json").write_text(
        json.dumps(packet, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    conn = sqlite3.connect(paths.db_path)
    try:
        ensure_schema(conn)
        persist_message(
            conn,
            sender="codex",
            recipient="zcode",
            subject="codex_worker no_task_request_more_task_packets",
            body="Codex worker status: no_task",
            task_id=None,
            status=None,
            summary="no_task",
        )
        conn.commit()
    finally:
        conn.close()

    result = loop.run_once(paths, auto_dispatch=False, max_passes=1)

    updated = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    task = next(task for task in updated["tasks"] if task["task_id"] == "P1-CODEX-PRODUCTIZATION-099")
    assert task["status"] == "ready_for_dispatch"
    assert any(event == "reconciled_missing_task P1-CODEX-PRODUCTIZATION-099" for event in result["events"])
    assert loop.load_unread_codex_messages(paths) == []


def test_controller_loop_reconciles_verified_board_regression_from_ledger(tmp_path):
    import scripts.claude_controller_loop as loop

    paths = make_paths(tmp_path)
    write_runtime_files(paths, status="verified")
    board = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    board["tasks"] = [
        {
            "task_id": "P1-CODEX-PRODUCTIZATION-099",
            "title": "regressed task",
            "owner": "codex",
            "status": "ready_for_dispatch",
            "priority": "P1",
            "next_step": "stale queue",
        }
    ]
    board["next_recommended_tasks"] = ["P1-CODEX-PRODUCTIZATION-099"]
    paths.task_board_path.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")
    paths.verification_ledger_path.write_text(
        "# VERIFICATION LEDGER\n\n## VERIFIED\n\n### 2026-06-29 V-AUTO-P1-CODEX-PRODUCTIZATION-099\n"
        "**Claim:** regressed task\n"
        "**Evidence:** `pytest tests/test_dummy.py -q` -> exit 0\n"
        "**Status:** passed\n\n## FAILED / OPEN\n",
        encoding="utf-8",
    )

    conn = sqlite3.connect(paths.db_path)
    try:
        ensure_schema(conn)
        persist_message(
            conn,
            sender="codex",
            recipient="zcode",
            subject="codex_worker blocked_board_regression_verified_tasks_requeued",
            body="board_state_mismatch",
            task_id=None,
            status="blocked",
            summary="board regression",
        )
        conn.commit()
    finally:
        conn.close()

    result = loop.run_once(paths, auto_dispatch=False, max_passes=1)

    updated = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    task = updated["tasks"][0]
    assert task["status"] == "verified"
    assert any(event == "reconciled_verified P1-CODEX-PRODUCTIZATION-099" for event in result["events"])


def test_controller_loop_reconciles_no_task_current_state_message(tmp_path):
    import scripts.claude_controller_loop as loop

    paths = make_paths(tmp_path)
    write_runtime_files(paths, status="verified")
    board = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    board["tasks"] = []
    board["next_recommended_tasks"] = []
    paths.task_board_path.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")

    packet = {
        "task_id": "P1-CODEX-RUNTIME-099",
        "title": "runtime reconciled task",
        "assigned_to": "codex",
        "priority": "P1",
        "verification_commands": [],
    }
    (paths.task_packet_dir / "P1-CODEX-RUNTIME-099.json").write_text(
        json.dumps(packet, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    conn = sqlite3.connect(paths.db_path)
    try:
        ensure_schema(conn)
        persist_message(
            conn,
            sender="codex",
            recipient="zcode",
            subject="codex_worker no_task_current_state_request_next_or_stop",
            body="no_task current-state audit",
            task_id=None,
            status="no_task",
            summary="no_task current-state audit",
        )
        conn.commit()
    finally:
        conn.close()

    result = loop.run_once(paths, auto_dispatch=False, max_passes=1)

    updated = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    task = next(task for task in updated["tasks"] if task["task_id"] == "P1-CODEX-RUNTIME-099")
    assert task["status"] == "ready_for_dispatch"
    assert any(event == "reconciled_missing_task P1-CODEX-RUNTIME-099" for event in result["events"])
    assert loop.load_unread_codex_messages(paths) == []


def test_controller_loop_does_not_requeue_auto_verify_smoke_packet(tmp_path):
    import scripts.claude_controller_loop as loop

    paths = make_paths(tmp_path)
    write_runtime_files(paths, status="verified")
    board = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    board["tasks"] = []
    board["next_recommended_tasks"] = []
    paths.task_board_path.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")

    packet = {
        "task_id": "P1-AUTO-VERIFY-SMOKE-001",
        "title": "自动验收链路烟雾测试",
        "assigned_to": "codex",
        "priority": "P1",
        "verification_commands": [],
    }
    (paths.task_packet_dir / "P1-AUTO-VERIFY-SMOKE-001.json").write_text(
        json.dumps(packet, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    conn = sqlite3.connect(paths.db_path)
    try:
        ensure_schema(conn)
        persist_message(
            conn,
            sender="codex",
            recipient="zcode",
            subject="codex_worker no_task_request_more_task_packets",
            body="Codex worker status: no_task",
            task_id=None,
            status=None,
            summary="no_task",
        )
        conn.commit()
    finally:
        conn.close()

    result = loop.run_once(paths, auto_dispatch=False, max_passes=1)

    updated = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    assert updated["tasks"] == []
    assert not any("P1-AUTO-VERIFY-SMOKE-001" in event for event in result["events"])
    assert result["completion_state"] == "stop_ready"


def test_controller_loop_marks_missing_packet_verified_when_ledger_already_has_entry(tmp_path):
    import scripts.claude_controller_loop as loop

    paths = make_paths(tmp_path)
    write_runtime_files(paths, status="verified")
    board = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    board["tasks"] = []
    board["next_recommended_tasks"] = []
    paths.task_board_path.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")
    paths.verification_ledger_path.write_text(
        "# VERIFICATION LEDGER\n\n## VERIFIED\n\n### 2026-06-29 V-AUTO-P1-CODEX-PRODUCTIZATION-099\n"
        "**Claim:** reconciled task\n"
        "**Evidence:** `pytest tests/test_dummy.py -q` -> exit 0\n"
        "**Status:** passed\n\n## FAILED / OPEN\n",
        encoding="utf-8",
    )

    packet = {
        "task_id": "P1-CODEX-PRODUCTIZATION-099",
        "title": "reconciled task",
        "assigned_to": "codex",
        "priority": "P1",
        "verification_commands": [],
    }
    (paths.task_packet_dir / "P1-CODEX-PRODUCTIZATION-099.json").write_text(
        json.dumps(packet, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    conn = sqlite3.connect(paths.db_path)
    try:
        ensure_schema(conn)
        persist_message(
            conn,
            sender="codex",
            recipient="zcode",
            subject="codex_worker no_task_request_more_task_packets",
            body="Codex worker status: no_task",
            task_id=None,
            status=None,
            summary="no_task",
        )
        conn.commit()
    finally:
        conn.close()

    result = loop.run_once(paths, auto_dispatch=False, max_passes=1)

    updated = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    task = next(task for task in updated["tasks"] if task["task_id"] == "P1-CODEX-PRODUCTIZATION-099")
    assert task["status"] == "verified"
    assert any(event == "reconciled_verified_missing_task P1-CODEX-PRODUCTIZATION-099" for event in result["events"])
    assert loop.load_unread_codex_messages(paths) == []


def test_controller_loop_replays_inbox_done_waiting_review_receipt_when_board_is_missing_task(tmp_path):
    import scripts.claude_controller_loop as loop

    paths = make_paths(tmp_path)
    write_runtime_files(paths, status="verified")
    board = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    board["tasks"] = []
    board["next_recommended_tasks"] = []
    paths.task_board_path.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")
    write_packet(paths, "P1-CODEX-RUNTIME-053", f'"{sys.executable}" -c "print(123)"')
    write_inbox_receipt(
        paths,
        "2026-06-29T22-26-17_P1-CODEX-RUNTIME-053-done_waiting_review.md",
        task_id="P1-CODEX-RUNTIME-053",
        status="done_waiting_review",
        subject="P1-CODEX-RUNTIME-053 done_waiting_review",
        line_ending="\r\n",
    )

    result = loop.run_once(paths, auto_dispatch=False, max_passes=1)

    updated = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    task = next(task for task in updated["tasks"] if task["task_id"] == "P1-CODEX-RUNTIME-053")
    assert task["status"] == "verified"
    assert any(event == "replayed_inbox_receipt P1-CODEX-RUNTIME-053" for event in result["events"])
    assert any(event == "verified P1-CODEX-RUNTIME-053" for event in result["events"])
    assert "V-AUTO-P1-CODEX-RUNTIME-053" in paths.verification_ledger_path.read_text(encoding="utf-8")



def test_controller_loop_does_not_trust_verified_inbox_receipt_without_ledger_entry(tmp_path):
    import scripts.claude_controller_loop as loop

    paths = make_paths(tmp_path)
    write_runtime_files(paths, status="verified")
    board = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    board["tasks"] = []
    board["next_recommended_tasks"] = []
    paths.task_board_path.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")
    write_packet(paths, "P1-CODEX-RUNTIME-053", f'"{sys.executable}" -c "print(123)"')
    write_inbox_receipt(
        paths,
        "2026-06-29T22-26-17_P1-CODEX-RUNTIME-053-verified.md",
        task_id="P1-CODEX-RUNTIME-053",
        status="verified",
        subject="P1-CODEX-RUNTIME-053 verified",
    )

    result = loop.run_once(paths, auto_dispatch=False, max_passes=1)

    updated = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    assert updated["tasks"] == []
    assert not any(event == "replayed_inbox_receipt P1-CODEX-RUNTIME-053" for event in result["events"])
    assert result["completion_state"] is None



def test_controller_loop_pending_done_receipt_without_packet_blocks_closeout(tmp_path):
    import scripts.claude_controller_loop as loop

    paths = make_paths(tmp_path)
    write_runtime_files(paths, status="verified")
    board = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    board["tasks"] = []
    board["next_recommended_tasks"] = []
    paths.task_board_path.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")
    write_inbox_receipt(
        paths,
        "2026-06-29T22-26-17_P1-CODEX-RUNTIME-406-done.md",
        task_id="P1-CODEX-RUNTIME-406",
        status="done",
        subject="P1-CODEX-RUNTIME-406 done",
    )

    result = loop.run_once(paths, auto_dispatch=False, max_passes=1)

    assert result["completion_state"] is None
    assert "completion_closeout_detected" not in result["events"]



def test_controller_loop_ignores_historical_numbered_done_receipt_for_closeout(tmp_path):
    import scripts.claude_controller_loop as loop

    paths = make_paths(tmp_path)
    write_runtime_files(paths, status="verified")
    board = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    board["tasks"] = []
    board["next_recommended_tasks"] = []
    paths.task_board_path.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")
    write_inbox_receipt(
        paths,
        "2026-06-17T21-33-16_P0-task-board-reverify-evidence.md",
        task_id="P0-01",
        status="done",
        subject="P0-01 done",
    )

    result = loop.run_once(paths, auto_dispatch=False, max_passes=1)

    updated = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    assert updated["tasks"] == []
    assert result["completion_state"] == "stop_ready"
    assert "completion_closeout_detected" in result["events"]



def test_controller_loop_replays_legacy_done_receipt_as_done_waiting_review(tmp_path):
    import scripts.claude_controller_loop as loop

    paths = make_paths(tmp_path)
    write_runtime_files(paths, status="verified")
    board = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    board["tasks"] = []
    board["next_recommended_tasks"] = []
    paths.task_board_path.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")
    write_packet(paths, "P1-CODEX-RUNTIME-407", f'"{sys.executable}" -c "print(123)"')
    write_inbox_receipt(
        paths,
        "2026-06-29T22-27-17_P1-CODEX-RUNTIME-407-done.md",
        task_id="P1-CODEX-RUNTIME-407",
        status="done",
        subject="P1-CODEX-RUNTIME-407 done",
    )

    result = loop.run_once(paths, auto_dispatch=False, max_passes=1)

    updated = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    task = next(task for task in updated["tasks"] if task["task_id"] == "P1-CODEX-RUNTIME-407")
    assert task["status"] == "verified"
    assert any(event == "replayed_inbox_receipt P1-CODEX-RUNTIME-407" for event in result["events"])
    assert any(event == "verified P1-CODEX-RUNTIME-407" for event in result["events"])



def test_controller_loop_ignores_control_signal_receipt_for_closeout(tmp_path):
    import scripts.claude_controller_loop as loop

    paths = make_paths(tmp_path)
    write_runtime_files(paths, status="verified")
    board = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    board["tasks"] = []
    board["next_recommended_tasks"] = []
    paths.task_board_path.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")
    write_inbox_receipt(
        paths,
        "2026-06-29T22-27-17_CODEX-WORKER-LOOP-blocked.md",
        task_id="CODEX-WORKER-LOOP",
        status="blocked",
        subject="CODEX-WORKER-LOOP blocked",
    )

    result = loop.run_once(paths, auto_dispatch=False, max_passes=1)

    assert result["completion_state"] == "stop_ready"
    assert "completion_closeout_detected" in result["events"]



def test_controller_loop_pending_blocked_receipt_without_packet_blocks_closeout(tmp_path):
    import scripts.claude_controller_loop as loop

    paths = make_paths(tmp_path)
    write_runtime_files(paths, status="verified")
    board = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    board["tasks"] = []
    board["next_recommended_tasks"] = []
    paths.task_board_path.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")
    write_inbox_receipt(
        paths,
        "2026-06-29T22-26-17_P1-CODEX-RUNTIME-405-blocked.md",
        task_id="P1-CODEX-RUNTIME-405",
        status="blocked",
        subject="P1-CODEX-RUNTIME-405 blocked",
    )

    result = loop.run_once(paths, auto_dispatch=False, max_passes=1)

    assert result["completion_state"] is None
    assert "completion_closeout_detected" not in result["events"]



def test_controller_loop_replays_latest_inbox_receipt_for_task(tmp_path):
    import scripts.claude_controller_loop as loop

    paths = make_paths(tmp_path)
    write_runtime_files(paths, status="verified")
    board = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    board["tasks"] = []
    board["next_recommended_tasks"] = []
    paths.task_board_path.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")
    write_packet(paths, "P1-CODEX-RUNTIME-053", f'"{sys.executable}" -c "print(123)"')
    write_inbox_receipt(
        paths,
        "2026-06-29T22-26-17_P1-CODEX-RUNTIME-053-blocked.md",
        task_id="P1-CODEX-RUNTIME-053",
        status="blocked",
        subject="P1-CODEX-RUNTIME-053 blocked",
    )
    write_inbox_receipt(
        paths,
        "2026-06-29T22-27-17_P1-CODEX-RUNTIME-053-done_waiting_review.md",
        task_id="P1-CODEX-RUNTIME-053",
        status="done_waiting_review",
        subject="P1-CODEX-RUNTIME-053 done_waiting_review",
    )

    result = loop.run_once(paths, auto_dispatch=False, max_passes=1)

    updated = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    task = next(task for task in updated["tasks"] if task["task_id"] == "P1-CODEX-RUNTIME-053")
    assert task["status"] == "verified"
    assert any(event == "replayed_inbox_receipt P1-CODEX-RUNTIME-053" for event in result["events"])
    assert any(event == "verified P1-CODEX-RUNTIME-053" for event in result["events"])



def test_controller_loop_reconciles_stale_board_task_from_newer_inbox_receipt(tmp_path):
    import scripts.claude_controller_loop as loop

    paths = make_paths(tmp_path)
    write_runtime_files(paths, status="verified")
    board = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    board["tasks"] = [
        {
            "task_id": "P1-CODEX-RUNTIME-053",
            "title": "stale task",
            "owner": "codex",
            "status": "ready_for_dispatch",
            "priority": "P1",
            "next_step": "stale queue",
        }
    ]
    board["next_recommended_tasks"] = ["P1-CODEX-RUNTIME-053"]
    paths.task_board_path.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")
    write_packet(paths, "P1-CODEX-RUNTIME-053", f'"{sys.executable}" -c "print(123)"')
    write_inbox_receipt(
        paths,
        "2026-06-29T22-27-17_P1-CODEX-RUNTIME-053-done_waiting_review.md",
        task_id="P1-CODEX-RUNTIME-053",
        status="done_waiting_review",
        subject="P1-CODEX-RUNTIME-053 done_waiting_review",
    )

    result = loop.run_once(paths, auto_dispatch=False, max_passes=1)

    updated = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    task = next(task for task in updated["tasks"] if task["task_id"] == "P1-CODEX-RUNTIME-053")
    assert task["status"] == "verified"
    assert any(event == "replayed_inbox_receipt P1-CODEX-RUNTIME-053" for event in result["events"])
    assert any(event == "verified P1-CODEX-RUNTIME-053" for event in result["events"])



def test_controller_loop_reconciles_stale_board_task_from_verified_receipt_with_ledger_entry(tmp_path):
    import scripts.claude_controller_loop as loop

    paths = make_paths(tmp_path)
    write_runtime_files(paths, status="verified")
    board = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    board["tasks"] = [
        {
            "task_id": "P1-CODEX-RUNTIME-053",
            "title": "stale task",
            "owner": "codex",
            "status": "ready_for_dispatch",
            "priority": "P1",
            "next_step": "stale queue",
        }
    ]
    board["next_recommended_tasks"] = ["P1-CODEX-RUNTIME-053"]
    paths.task_board_path.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")
    paths.verification_ledger_path.write_text(
        "# VERIFICATION LEDGER\n\n## VERIFIED\n\n### 2026-06-29 V-AUTO-P1-CODEX-RUNTIME-053\n"
        "**Claim:** task already auto-verified\n"
        "**Evidence:** `pytest tests/test_dummy.py -q` -> exit 0\n"
        "**Status:** passed\n\n## FAILED / OPEN\n",
        encoding="utf-8",
    )
    write_inbox_receipt(
        paths,
        "2026-06-30T22-27-17_P1-CODEX-RUNTIME-053-verified.md",
        task_id="P1-CODEX-RUNTIME-053",
        status="verified",
        subject="P1-CODEX-RUNTIME-053 verified",
    )

    result = loop.run_once(paths, auto_dispatch=False, max_passes=1)

    updated = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    task = next(task for task in updated["tasks"] if task["task_id"] == "P1-CODEX-RUNTIME-053")
    assert task["status"] == "verified"
    assert task["next_step"] == "Replayed inbox receipt after ledger reconciliation"
    assert any(event == "replayed_inbox_receipt P1-CODEX-RUNTIME-053" for event in result["events"])
    assert not any(event == "verified P1-CODEX-RUNTIME-053" for event in result["events"])



def test_controller_loop_prefers_newer_inbox_receipt_over_stale_verified_ledger(tmp_path):
    import scripts.claude_controller_loop as loop

    paths = make_paths(tmp_path)
    write_runtime_files(paths, status="verified")
    board = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    board["tasks"] = []
    board["next_recommended_tasks"] = []
    paths.task_board_path.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")
    paths.verification_ledger_path.write_text(
        "# VERIFICATION LEDGER\n\n## VERIFIED\n\n### 2026-06-29 V-AUTO-P1-CODEX-RUNTIME-053\n"
        "**Claim:** stale verified task\n"
        "**Evidence:** `pytest tests/test_dummy.py -q` -> exit 0\n"
        "**Status:** passed\n\n## FAILED / OPEN\n",
        encoding="utf-8",
    )
    write_packet(paths, "P1-CODEX-RUNTIME-053", f'"{sys.executable}" -c "print(123)"')
    write_inbox_receipt(
        paths,
        "2026-06-30T22-27-17_P1-CODEX-RUNTIME-053-blocked.md",
        task_id="P1-CODEX-RUNTIME-053",
        status="blocked",
        subject="P1-CODEX-RUNTIME-053 blocked",
    )

    result = loop.run_once(paths, auto_dispatch=False, max_passes=1)

    updated = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    task = next(task for task in updated["tasks"] if task["task_id"] == "P1-CODEX-RUNTIME-053")
    assert task["status"] == "blocked"
    assert task["next_step"] == "Replayed inbox receipt; Claude controller will inspect blocker"
    assert any(event == "replayed_inbox_receipt P1-CODEX-RUNTIME-053" for event in result["events"])
    assert not any(event == "verified P1-CODEX-RUNTIME-053" for event in result["events"])



def test_controller_loop_reconciles_existing_blocked_task_from_newer_done_receipt(tmp_path):
    import scripts.claude_controller_loop as loop

    paths = make_paths(tmp_path)
    write_runtime_files(paths, status="verified")
    board = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    board["tasks"] = [
        {
            "task_id": "P1-CODEX-RUNTIME-053",
            "title": "blocked task",
            "owner": "codex",
            "status": "blocked",
            "priority": "P1",
            "next_step": "old blocker",
        }
    ]
    board["next_recommended_tasks"] = ["P1-CODEX-RUNTIME-053"]
    paths.task_board_path.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")
    write_packet(paths, "P1-CODEX-RUNTIME-053", f'"{sys.executable}" -c "print(123)"')
    write_inbox_receipt(
        paths,
        "2026-06-30T22-27-17_P1-CODEX-RUNTIME-053-done_waiting_review.md",
        task_id="P1-CODEX-RUNTIME-053",
        status="done_waiting_review",
        subject="P1-CODEX-RUNTIME-053 done_waiting_review",
    )

    result = loop.run_once(paths, auto_dispatch=False, max_passes=1)

    updated = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    task = next(task for task in updated["tasks"] if task["task_id"] == "P1-CODEX-RUNTIME-053")
    assert task["status"] == "verified"
    assert any(event == "replayed_inbox_receipt P1-CODEX-RUNTIME-053" for event in result["events"])
    assert any(event == "verified P1-CODEX-RUNTIME-053" for event in result["events"])



def test_controller_loop_reconciles_existing_done_task_from_newer_blocked_receipt(tmp_path):
    import scripts.claude_controller_loop as loop

    paths = make_paths(tmp_path)
    write_runtime_files(paths, status="verified")
    board = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    board["tasks"] = [
        {
            "task_id": "P1-CODEX-RUNTIME-053",
            "title": "done task",
            "owner": "codex",
            "status": "done_waiting_review",
            "priority": "P1",
            "next_step": "stale done state",
        }
    ]
    board["next_recommended_tasks"] = ["P1-CODEX-RUNTIME-053"]
    paths.task_board_path.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")
    write_packet(paths, "P1-CODEX-RUNTIME-053", f'"{sys.executable}" -c "print(123)"')
    write_inbox_receipt(
        paths,
        "2026-06-30T22-27-17_P1-CODEX-RUNTIME-053-blocked.md",
        task_id="P1-CODEX-RUNTIME-053",
        status="blocked",
        subject="P1-CODEX-RUNTIME-053 blocked",
    )

    result = loop.run_once(paths, auto_dispatch=False, max_passes=1)

    updated = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    task = next(task for task in updated["tasks"] if task["task_id"] == "P1-CODEX-RUNTIME-053")
    assert task["status"] == "blocked"
    assert task["next_step"] == "Replayed inbox receipt; Claude controller will inspect blocker"
    assert any(event == "replayed_inbox_receipt P1-CODEX-RUNTIME-053" for event in result["events"])
    assert not any(event == "verified P1-CODEX-RUNTIME-053" for event in result["events"])



def test_controller_loop_backfills_missing_done_waiting_review_task_from_packet(tmp_path):
    import scripts.claude_controller_loop as loop

    paths = make_paths(tmp_path)
    write_runtime_files(paths, status="verified")
    board = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    board["tasks"] = []
    board["next_recommended_tasks"] = []
    paths.task_board_path.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")
    write_packet(paths, "P1-CODEX-RUNTIME-058", f'"{sys.executable}" -c "print(123)"')
    seed_message(
        paths,
        "P1-CODEX-RUNTIME-058 done_waiting_review",
        task_id="P1-CODEX-RUNTIME-058",
        status="done_waiting_review",
    )

    result = loop.run_once(paths, auto_dispatch=False, max_passes=1)

    updated = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    task = next(task for task in updated["tasks"] if task["task_id"] == "P1-CODEX-RUNTIME-058")
    assert task["status"] == "verified"
    assert any(event == "reconciled_message_task P1-CODEX-RUNTIME-058" for event in result["events"])
    assert any(event == "verified P1-CODEX-RUNTIME-058" for event in result["events"])
    assert "V-AUTO-P1-CODEX-RUNTIME-058" in paths.verification_ledger_path.read_text(encoding="utf-8")
    assert loop.load_unread_codex_messages(paths) == []


def test_controller_loop_backfills_missing_blocked_task_from_packet(tmp_path):
    import scripts.claude_controller_loop as loop

    paths = make_paths(tmp_path)
    write_runtime_files(paths, status="verified")
    board = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    board["tasks"] = []
    board["next_recommended_tasks"] = []
    paths.task_board_path.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")
    write_packet(paths, "P1-CODEX-RUNTIME-059", f'"{sys.executable}" -c "print(123)"')
    seed_message(
        paths,
        "P1-CODEX-RUNTIME-059 blocked",
        task_id="P1-CODEX-RUNTIME-059",
        status="blocked",
    )

    result = loop.run_once(paths, auto_dispatch=False, max_passes=1)

    updated = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    task = next(task for task in updated["tasks"] if task["task_id"] == "P1-CODEX-RUNTIME-059")
    assert task["status"] == "ready_for_dispatch"
    assert task["next_step"] == "Controller found task packet context; re-dispatch through Codex worker"
    assert any(event == "reconciled_message_task P1-CODEX-RUNTIME-059" for event in result["events"])
    assert any(event == "unblocked P1-CODEX-RUNTIME-059" for event in result["events"])
    assert loop.load_unread_codex_messages(paths) == []


def test_controller_loop_reconciles_runtime_board_regression_variant(tmp_path):
    import scripts.claude_controller_loop as loop

    paths = make_paths(tmp_path)
    write_runtime_files(paths, status="verified")
    board = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    board["tasks"] = [
        {
            "task_id": "P1-CODEX-PRODUCTIZATION-100",
            "title": "runtime regressed task",
            "owner": "codex",
            "status": "ready_for_dispatch",
            "priority": "P1",
            "next_step": "stale queue",
        }
    ]
    board["next_recommended_tasks"] = ["P1-CODEX-PRODUCTIZATION-100"]
    paths.task_board_path.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")
    paths.verification_ledger_path.write_text(
        "# VERIFICATION LEDGER\n\n## VERIFIED\n\n### 2026-06-29 V-AUTO-P1-CODEX-PRODUCTIZATION-100\n"
        "**Claim:** runtime regressed task\n"
        "**Evidence:** `pytest tests/test_dummy.py -q` -> exit 0\n"
        "**Status:** passed\n\n## FAILED / OPEN\n",
        encoding="utf-8",
    )

    conn = sqlite3.connect(paths.db_path)
    try:
        ensure_schema(conn)
        persist_message(
            conn,
            sender="codex",
            recipient="zcode",
            subject="codex_worker blocked_board_regression_after_runtime_018_020",
            body="CURRENT_TASK_BOARD.json regressed after runtime wave",
            task_id=None,
            status="blocked",
            summary="runtime board regression",
        )
        conn.commit()
    finally:
        conn.close()

    result = loop.run_once(paths, auto_dispatch=False, max_passes=1)

    updated = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    task = updated["tasks"][0]
    assert task["status"] == "verified"
    assert any(event == "reconciled_verified P1-CODEX-PRODUCTIZATION-100" for event in result["events"])


def test_controller_loop_marks_no_task_messages_read_even_without_reconciliation(tmp_path):
    import scripts.claude_controller_loop as loop

    paths = make_paths(tmp_path)
    write_runtime_files(paths, status="verified")
    board = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    board["tasks"] = [
        {
            "task_id": "P1-CODEX-PRODUCTIZATION-001",
            "title": "existing ready task",
            "owner": "codex",
            "status": "ready_for_dispatch",
            "priority": "P1",
            "next_step": "ready",
        }
    ]
    board["next_recommended_tasks"] = ["P1-CODEX-PRODUCTIZATION-001"]
    paths.task_board_path.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")

    conn = sqlite3.connect(paths.db_path)
    try:
        ensure_schema(conn)
        persist_message(
            conn,
            sender="codex",
            recipient="zcode",
            subject="codex_worker no_task_request_more_task_packets",
            body="Codex worker status: no_task",
            task_id=None,
            status=None,
            summary="no_task",
        )
        conn.commit()
    finally:
        conn.close()

    result = loop.run_once(paths, auto_dispatch=False, max_passes=1)

    assert result["unread_messages"] == 1
    assert loop.load_unread_codex_messages(paths) == []


def test_controller_loop_skips_auto_dispatch_when_idle(monkeypatch, tmp_path):
    import scripts.claude_controller_loop as loop

    paths = make_paths(tmp_path)
    write_runtime_files(paths, status="verified")

    called = {"value": False}

    def fake_worker(**kwargs):
        called["value"] = True
        raise AssertionError("worker should not be called when idle")

    monkeypatch.setattr(loop, "run_worker_once_result", fake_worker)

    result = loop.run_once(paths, auto_dispatch=True, max_passes=1)

    assert "normalized_next_recommended_tasks" in result["events"]
    assert "completion_closeout_detected" in result["events"]
    assert result["completion_state"] == "stop_ready"
    assert called["value"] is False


def test_controller_loop_writes_closeout_decision_once_for_idle_board(tmp_path):
    import scripts.claude_controller_loop as loop

    paths = make_paths(tmp_path)
    write_runtime_files(paths, status="verified")

    first = loop.run_once(paths, auto_dispatch=False, max_passes=1)
    second = loop.run_once(paths, auto_dispatch=False, max_passes=1)

    decision_log = paths.decision_log_path.read_text(encoding="utf-8")
    assert first["completion_state"] == "stop_ready"
    assert second["completion_state"] == "stop_ready"
    assert decision_log.count("D-AUTO-CLOSEOUT-") == 1



def test_controller_loop_uses_generated_at_to_distinguish_closeout_markers_without_goal(tmp_path):
    import scripts.claude_controller_loop as loop

    paths = make_paths(tmp_path)
    write_runtime_files(paths, status="verified")

    board = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    board.pop("current_goal", None)
    board["generated_at"] = "2026-06-29T00:00:00+00:00"
    paths.task_board_path.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")
    first = loop.run_once(paths, auto_dispatch=False, max_passes=1)

    board = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    board.pop("current_goal", None)
    board["generated_at"] = "2026-06-30T00:00:00+00:00"
    paths.task_board_path.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")
    second = loop.run_once(paths, auto_dispatch=False, max_passes=1)

    decision_log = paths.decision_log_path.read_text(encoding="utf-8")
    assert first["completion_state"] == "stop_ready"
    assert second["completion_state"] == "stop_ready"
    assert decision_log.count("D-AUTO-CLOSEOUT-") == 2



def test_controller_loop_does_not_closeout_when_blocked_task_still_requires_controller(tmp_path):
    import scripts.claude_controller_loop as loop

    paths = make_paths(tmp_path)
    write_runtime_files(paths, status="verified")
    board = json.loads(paths.task_board_path.read_text(encoding="utf-8"))
    board["tasks"] = [
        {
            "task_id": "T-001",
            "title": "blocked task",
            "owner": "codex",
            "status": "blocked",
            "priority": "P0",
            "next_step": "Replayed inbox receipt; Claude controller will inspect blocker",
        }
    ]
    board["next_recommended_tasks"] = ["T-001"]
    paths.task_board_path.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")

    result = loop.run_once(paths, auto_dispatch=False, max_passes=1)

    assert "completion_closeout_detected" not in result["events"]
    assert result["completion_state"] is None
