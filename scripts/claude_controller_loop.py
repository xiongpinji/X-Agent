from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.codex_worker_loop import run_once_result as run_worker_once_result
except ModuleNotFoundError:
    def run_worker_once_result(**kwargs: Any) -> Any:
        raise ModuleNotFoundError("scripts.codex_worker_loop is required for auto dispatch")

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ControllerPaths:
    repo_root: Path
    db_path: Path
    task_board_path: Path
    session_recovery_path: Path
    verification_ledger_path: Path
    decision_log_path: Path
    task_packet_dir: Path


@dataclass(frozen=True)
class CommandResult:
    command: str
    returncode: int
    output: str


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    commands: list[CommandResult]
    reason: str


@dataclass(frozen=True)
class PassResult:
    events: list[str]
    unread_messages: int
    worker_status: str | None = None
    worker_task_id: str | None = None


ACTIONABLE_DISPATCH_STATUSES = {"queued", "ready_for_dispatch"}


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value) if value else default


def default_paths() -> ControllerPaths:
    comm_dir = REPO_ROOT / "audit_reports" / "_comm"
    return ControllerPaths(
        repo_root=REPO_ROOT,
        db_path=_env_path("XAGENT_BLACKBOARD_PATH", comm_dir / "blackboard.sqlite"),
        task_board_path=_env_path(
            "XAGENT_CURRENT_TASK_BOARD_PATH",
            comm_dir / "CURRENT_TASK_BOARD.json",
        ),
        session_recovery_path=_env_path(
            "XAGENT_SESSION_RECOVERY_PATH",
            comm_dir / "SESSION_RECOVERY.md",
        ),
        verification_ledger_path=_env_path(
            "XAGENT_VERIFICATION_LEDGER_PATH",
            comm_dir / "VERIFICATION_LEDGER.md",
        ),
        decision_log_path=_env_path("XAGENT_DECISION_LOG_PATH", comm_dir / "DECISION_LOG.md"),
        task_packet_dir=_env_path("XAGENT_TASK_PACKET_DIR", comm_dir / "task_packets"),
    )


def load_unread_codex_messages(paths: ControllerPaths | None = None) -> list[dict[str, Any]]:
    paths = paths or default_paths()
    if not paths.db_path.exists():
        return []

    conn = sqlite3.connect(paths.db_path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        rows = conn.execute(
            "SELECT * FROM messages "
            "WHERE sender='codex' AND recipient='zcode' AND read_at IS NULL "
            "ORDER BY ts ASC"
        ).fetchall()
    finally:
        conn.close()

    messages: list[dict[str, Any]] = []
    for row in rows:
        message = dict(row)
        body = message.get("body", "")
        try:
            payload = json.loads(body)
        except Exception:
            payload = {"body": body}
        if isinstance(payload, dict):
            message.update(payload)
        else:
            message["body"] = body
        messages.append(message)
    return messages


def mark_messages_read(message_ids: list[str], paths: ControllerPaths | None = None) -> None:
    if not message_ids:
        return
    paths = paths or default_paths()
    if not paths.db_path.exists():
        return

    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(paths.db_path, timeout=10.0)
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        for message_id in message_ids:
            conn.execute("UPDATE messages SET read_at=? WHERE id=?", (now, message_id))
        conn.commit()
    finally:
        conn.close()


def load_task_board(paths: ControllerPaths | None = None) -> dict[str, Any]:
    paths = paths or default_paths()
    return json.loads(paths.task_board_path.read_text(encoding="utf-8"))


def save_task_board(board: dict[str, Any], paths: ControllerPaths | None = None) -> None:
    paths = paths or default_paths()
    board["generated_at"] = datetime.now(timezone.utc).isoformat()
    paths.task_board_path.write_text(
        json.dumps(board, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def find_task(board: dict[str, Any], task_id: str) -> dict[str, Any] | None:
    for task in board.get("tasks", []):
        if task.get("task_id") == task_id:
            return task
    return None


def task_packet_path(task_id: str, paths: ControllerPaths | None = None) -> Path:
    paths = paths or default_paths()
    return paths.task_packet_dir / f"{task_id}.json"


def inbox_dir(paths: ControllerPaths | None = None) -> Path:
    paths = paths or default_paths()
    return paths.task_board_path.parent / "inbox_zcode"


def load_task_packet(task_id: str, paths: ControllerPaths | None = None) -> dict[str, Any]:
    path = task_packet_path(task_id, paths)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def command_timeout(packet: dict[str, Any]) -> int:
    value = packet.get("verification_timeout_seconds")
    if isinstance(value, int) and value > 0:
        return value
    return 900


def run_verification(task_id: str, paths: ControllerPaths | None = None) -> VerificationResult:
    paths = paths or default_paths()
    packet = load_task_packet(task_id, paths)
    commands = packet.get("verification_commands") or []
    if not commands:
        return VerificationResult(
            passed=False,
            commands=[],
            reason=f"task packet {task_id} has no verification_commands",
        )

    results: list[CommandResult] = []
    timeout = command_timeout(packet)
    for command in commands:
        completed = subprocess.run(
            command,
            cwd=paths.repo_root,
            shell=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
        output = (completed.stdout or "").strip()
        results.append(CommandResult(command=command, returncode=completed.returncode, output=output))
        if completed.returncode != 0:
            return VerificationResult(
                passed=False,
                commands=results,
                reason=f"verification command failed with exit code {completed.returncode}",
            )

    return VerificationResult(passed=True, commands=results, reason="all verification commands passed")


def ledger_entry(task: dict[str, Any], result: VerificationResult) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    task_id = task["task_id"]
    evidence = "; ".join(
        f"`{item.command}` -> exit {item.returncode}" for item in result.commands
    )
    return (
        f"\n### {today} V-AUTO-{task_id}\n"
        f"**Claim:** {task.get('title', task_id)}\n"
        f"**Evidence:** {evidence}\n"
        f"**Status:** passed\n"
    )


def append_verification_ledger(task: dict[str, Any], result: VerificationResult, paths: ControllerPaths) -> None:
    text = paths.verification_ledger_path.read_text(encoding="utf-8")
    marker = f"V-AUTO-{task['task_id']}"
    if marker in text:
        return
    failed_marker = "\n## FAILED / OPEN"
    entry = ledger_entry(task, result)
    if failed_marker in text:
        text = text.replace(failed_marker, entry + failed_marker, 1)
    else:
        text = text.rstrip() + entry + "\n"
    paths.verification_ledger_path.write_text(text, encoding="utf-8")


def update_session_recovery(task: dict[str, Any], result: VerificationResult, paths: ControllerPaths) -> None:
    text = paths.session_recovery_path.read_text(encoding="utf-8")
    now_line = datetime.now().strftime("Last Updated: %Y-%m-%d %H:%M")
    lines = text.splitlines()
    updated_lines: list[str] = []
    task_seen = False
    for line in lines:
        if line.startswith("Last Updated: "):
            updated_lines.append(now_line)
            continue
        if line.startswith(f"- {task['task_id']}：") or line.startswith(f"- {task['task_id']}:"):
            updated_lines.append(f"- {task['task_id']}：{task.get('title', task['task_id'])}，状态：verified")
            task_seen = True
            continue
        updated_lines.append(line)

    text = "\n".join(updated_lines) + "\n"
    if not task_seen and "## Active Tasks" in text:
        active_marker = "## Active Tasks\n"
        text = text.replace(
            active_marker,
            active_marker + f"- {task['task_id']}：{task.get('title', task['task_id'])}，状态：verified\n",
            1,
        )

    evidence_lines = [
        f"- `{item.command}` -> exit {item.returncode}" for item in result.commands
    ]
    for evidence_line in evidence_lines:
        if evidence_line not in text and "## Latest Verified Evidence" in text:
            text = text.replace("## Critical Decisions", evidence_line + "\n## Critical Decisions", 1)

    paths.session_recovery_path.write_text(text, encoding="utf-8")


def repair_packet_id(task_id: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{task_id}-REPAIR-{stamp}"


def create_repair_packet(
    task: dict[str, Any],
    result: VerificationResult,
    paths: ControllerPaths,
) -> dict[str, Any]:
    original = load_task_packet(task["task_id"], paths)
    new_task_id = repair_packet_id(task["task_id"])
    packet = {
        "task_id": new_task_id,
        "title": f"Repair verification failure for {task['task_id']}",
        "priority": task.get("priority", "P0"),
        "assigned_to": "codex",
        "source_task_id": task["task_id"],
        "allowed_files": original.get("allowed_files", []),
        "forbidden_files": original.get("forbidden_files", []),
        "failure_reason": result.reason,
        "failed_commands": [
            {
                "command": item.command,
                "returncode": item.returncode,
                "output_tail": item.output[-4000:],
            }
            for item in result.commands
        ],
        "acceptance": [
            "Fix only the failed verification for the source task.",
            "Keep scope inside the original task packet allowed_files.",
            "Run the verification_commands and return changed files, command outputs, and residual risks.",
        ],
        "verification_commands": original.get("verification_commands", []),
    }
    paths.task_packet_dir.mkdir(parents=True, exist_ok=True)
    (paths.task_packet_dir / f"{new_task_id}.json").write_text(
        json.dumps(packet, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return packet


def enqueue_repair_task(board: dict[str, Any], source_task: dict[str, Any], repair_packet: dict[str, Any]) -> None:
    if find_task(board, repair_packet["task_id"]):
        return
    board.setdefault("tasks", []).append(
        {
            "task_id": repair_packet["task_id"],
            "title": repair_packet["title"],
            "owner": "codex",
            "status": "ready_for_dispatch",
            "priority": repair_packet.get("priority", source_task.get("priority", "P0")),
            "next_step": f"Repair failed verification for {source_task['task_id']}",
        }
    )


def message_task_status(message: dict[str, Any]) -> tuple[str | None, str | None]:
    task_id = message.get("task_id")
    status = message.get("status")
    subject = str(message.get("subject", ""))
    if not status and "done_waiting_review" in subject:
        status = "done_waiting_review"
    if not status and "blocked" in subject.lower():
        status = "blocked"
    return task_id, status


def canonical_receipt_status(status: str | None) -> str | None:
    if status == "done":
        return "done_waiting_review"
    return status


LEGACY_CLOSEOUT_PREFIXES = ("B2-", "F-")


def is_historical_numbered_closeout_task_id(task_id: str) -> bool:
    phase, separator, sequence = task_id.partition("-")
    return (
        separator == "-"
        and len(phase) == 2
        and phase.startswith("P")
        and phase[1].isdigit()
        and len(sequence) == 2
        and sequence.isdigit()
    )



def is_historical_closeout_task_id(task_id: str) -> bool:
    return task_id.startswith(LEGACY_CLOSEOUT_PREFIXES) or is_historical_numbered_closeout_task_id(task_id)



def is_control_signal_task_id(task_id: str) -> bool:
    return (
        task_id == "CODEX-WORKER-LOOP"
        or task_id == "no_task"
        or task_id.startswith("NO_TASK-")
    )


def parse_inbox_receipt(path: Path) -> dict[str, str] | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.startswith("---"):
        return None

    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return None
    frontmatter_text, separator, _remainder = normalized[4:].partition("\n---\n")
    if not separator:
        return None

    frontmatter: dict[str, str] = {}
    for line in frontmatter_text.splitlines():
        key, sep, value = line.partition(":")
        if not sep:
            continue
        frontmatter[key.strip()] = value.strip()

    task_id = frontmatter.get("task_id")
    status = canonical_receipt_status(frontmatter.get("status"))
    if not task_id or not status:
        return None
    return {
        "task_id": task_id,
        "status": status,
        "ts": frontmatter.get("ts", ""),
        "path": str(path),
        "filename": path.name,
    }


def has_pending_inbox_receipt_without_task(board: dict[str, Any], paths: ControllerPaths) -> bool:
    inbox = inbox_dir(paths)
    if not inbox.exists():
        return False

    known_task_ids = {
        str(task.get("task_id", ""))
        for task in board.get("tasks", [])
        if str(task.get("task_id", ""))
    }
    ledger_text = paths.verification_ledger_path.read_text(encoding="utf-8")

    latest_receipts: dict[str, dict[str, str]] = {}
    for receipt_path in sorted(inbox.glob("*.md")):
        receipt = parse_inbox_receipt(receipt_path)
        if not receipt:
            continue
        previous = latest_receipts.get(receipt["task_id"])
        if previous is None or receipt.get("ts", "") >= previous.get("ts", ""):
            latest_receipts[receipt["task_id"]] = receipt

    for task_id, receipt in latest_receipts.items():
        if is_control_signal_task_id(task_id):
            continue
        if is_historical_closeout_task_id(task_id):
            continue
        if task_id in known_task_ids:
            continue
        status = receipt.get("status")
        if status == "verified" and f"V-AUTO-{task_id}" in ledger_text:
            continue
        if status in {"done_waiting_review", "blocked", "verified"}:
            return True
    return False


STALE_ACTIONABLE_STATUSES = {"queued", "ready_for_dispatch", "in_progress"}


def is_stale_actionable_task(task: dict[str, Any]) -> bool:
    status = str(task.get("status") or "")
    if status not in STALE_ACTIONABLE_STATUSES:
        return False
    next_step = str(task.get("next_step") or "")
    if next_step.startswith("Controller found task packet context"):
        return False
    if next_step.startswith("Replayed inbox receipt"):
        return False
    if next_step.startswith("Claude controller received Codex completion"):
        return False
    return True


def should_apply_inbox_receipt(existing_task: dict[str, Any] | None, receipt_status: str) -> bool:
    if existing_task is None:
        return True

    current_status = str(existing_task.get("status") or "")
    if is_stale_actionable_task(existing_task) and receipt_status in {"done_waiting_review", "blocked", "verified"}:
        return True
    if current_status == "blocked" and receipt_status == "done_waiting_review":
        return True
    if current_status == "done_waiting_review" and receipt_status == "blocked":
        return True
    return False


def should_prefer_ledger_status(receipt: dict[str, str], ledger_text: str) -> bool:
    task_id = receipt["task_id"]
    if f"V-AUTO-{task_id}" not in ledger_text:
        return False
    return receipt["status"] == "verified"


def reconcile_inbox_receipts(board: dict[str, Any], paths: ControllerPaths) -> list[str]:
    events: list[str] = []
    inbox = inbox_dir(paths)
    if not inbox.exists():
        return events

    latest_receipts: dict[str, dict[str, str]] = {}
    for receipt_path in sorted(inbox.glob("*.md")):
        receipt = parse_inbox_receipt(receipt_path)
        if receipt:
            previous = latest_receipts.get(receipt["task_id"])
            if previous is None or receipt.get("ts", "") >= previous.get("ts", ""):
                latest_receipts[receipt["task_id"]] = receipt

    ledger_text = paths.verification_ledger_path.read_text(encoding="utf-8")
    for task_id, receipt in latest_receipts.items():
        if is_control_signal_task_id(task_id):
            continue
        receipt_status = receipt["status"]
        existing_task = find_task(board, task_id)
        if should_prefer_ledger_status(receipt, ledger_text):
            status = "verified"
        else:
            status = receipt_status
            if status not in {"done_waiting_review", "blocked"}:
                continue

        if not should_apply_inbox_receipt(existing_task, status):
            continue

        task = existing_task or backfill_task_from_packet(board, task_id, status, paths)
        if not task:
            continue

        task["title"] = task.get("title") or load_task_packet(task_id, paths).get("title", task_id)
        task["owner"] = task.get("owner") or "codex"
        task["priority"] = task.get("priority") or "P1"

        if status == "verified":
            task["status"] = "verified"
            task["next_step"] = "Replayed inbox receipt after ledger reconciliation"
        elif status == "done_waiting_review":
            task["status"] = "done_waiting_review"
            task["next_step"] = "Replayed inbox receipt; Claude controller will verify"
        elif status == "blocked":
            task["status"] = "blocked"
            task["next_step"] = "Replayed inbox receipt; Claude controller will inspect blocker"
        events.append(f"replayed_inbox_receipt {task_id}")
    return events


def backfill_task_from_packet(
    board: dict[str, Any],
    task_id: str,
    status: str,
    paths: ControllerPaths,
) -> dict[str, Any] | None:
    packet = load_task_packet(task_id, paths)
    if not packet:
        return None

    task = {
        "task_id": task_id,
        "title": packet.get("title", task_id),
        "owner": packet.get("assigned_to") or packet.get("owner") or "codex",
        "status": status,
        "priority": packet.get("priority", "P1"),
        "next_step": (
            "Backfilled from Codex completion message; Claude controller will verify"
            if status == "done_waiting_review"
            else "Backfilled from Codex blocker message; Claude controller will inspect blocker"
        ),
    }
    board.setdefault("tasks", []).append(task)
    return task



def sync_messages_into_board(
    board: dict[str, Any],
    messages: list[dict[str, Any]],
    paths: ControllerPaths,
) -> tuple[list[str], list[dict[str, Any]], list[str]]:
    message_ids_to_mark: list[str] = []
    unhandled_messages: list[dict[str, Any]] = []
    events: list[str] = []
    for message in messages:
        message_id = message.get("id")
        task_id, status = message_task_status(message)
        if not task_id or not status:
            unhandled_messages.append(message)
            continue
        status = canonical_receipt_status(status)
        if is_control_signal_task_id(task_id):
            if message_id:
                message_ids_to_mark.append(message_id)
            continue

        task = find_task(board, task_id)
        if not task and status in {"done", "done_waiting_review", "blocked"}:
            backfill_status = "done_waiting_review" if status in {"done", "done_waiting_review"} else "blocked"
            task = backfill_task_from_packet(board, task_id, backfill_status, paths)
            if task:
                events.append(f"reconciled_message_task {task_id}")
        if not task:
            if message_id:
                message_ids_to_mark.append(message_id)
            continue

        current_status = task.get("status")
        if current_status in {"verified", "repair_requested"}:
            if message_id:
                message_ids_to_mark.append(message_id)
            continue

        if status in {"done", "done_waiting_review"}:
            task["status"] = "done_waiting_review"
            task["next_step"] = "Claude controller received Codex completion and will verify"
            if message_id:
                message_ids_to_mark.append(message_id)
        elif status == "blocked" and current_status != "verified":
            task["status"] = "blocked"
            task["next_step"] = "Claude controller will inspect blocker and decide repair or owner escalation"
            if message_id:
                message_ids_to_mark.append(message_id)
    return message_ids_to_mark, unhandled_messages, events


def reconcile_missing_codex_tasks(board: dict[str, Any], paths: ControllerPaths, messages: list[dict[str, Any]]) -> list[str]:
    events: list[str] = []
    no_task_messages = [
        message for message in messages
        if "codex_worker no_task" in str(message.get("subject", ""))
        or "Codex worker status: no_task" in str(message.get("body", ""))
    ]
    if not no_task_messages:
        return events

    known_tasks = {str(task.get("task_id", "")) for task in board.get("tasks", [])}
    ledger_text = paths.verification_ledger_path.read_text(encoding="utf-8")
    for packet_path in sorted(paths.task_packet_dir.glob("*.json")):
        try:
            packet = json.loads(packet_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not _packet_eligible_for_board_reconcile(packet):
            continue
        task_id = str(packet.get("task_id", ""))
        if not task_id or task_id in known_tasks:
            continue
        is_verified = f"V-AUTO-{task_id}" in ledger_text
        board.setdefault("tasks", []).append(
            {
                "task_id": task_id,
                "title": packet.get("title", task_id),
                "owner": "codex",
                "status": "verified" if is_verified else "ready_for_dispatch",
                "priority": packet.get("priority", "P1"),
                "next_step": (
                    "Reconciled from verification ledger after missing board state"
                    if is_verified
                    else "Reconciled from task packet after Codex no_task report"
                ),
            }
        )
        known_tasks.add(task_id)
        events.append(
            f"reconciled_verified_missing_task {task_id}"
            if is_verified
            else f"reconciled_missing_task {task_id}"
        )

    message_ids = [message.get("id") for message in no_task_messages if message.get("id")]
    if message_ids:
        mark_messages_read(message_ids, paths)
    return events


def reconcile_verified_tasks_from_ledger(board: dict[str, Any], paths: ControllerPaths, messages: list[dict[str, Any]]) -> list[str]:
    events: list[str] = []
    mismatch_messages = [
        message for message in messages
        if "board_regression_verified_tasks_requeued" in str(message.get("subject", ""))
        or "blocked_board_regression_after_runtime_018_020" in str(message.get("subject", ""))
        or "board_state_mismatch" in str(message.get("body", ""))
        or "regressed after runtime wave" in str(message.get("body", ""))
    ]
    if not mismatch_messages:
        return events

    ledger_text = paths.verification_ledger_path.read_text(encoding="utf-8")
    for task in board.get("tasks", []):
        task_id = str(task.get("task_id", ""))
        if not task_id:
            continue
        if f"V-AUTO-{task_id}" not in ledger_text:
            continue
        if task.get("status") != "verified":
            task["status"] = "verified"
            task["next_step"] = "Reconciled from verification ledger after Codex board regression signal"
            events.append(f"reconciled_verified {task_id}")

    message_ids = [message.get("id") for message in mismatch_messages if message.get("id")]
    if message_ids:
        mark_messages_read(message_ids, paths)
    return events


def handle_done_waiting_review(board: dict[str, Any], paths: ControllerPaths) -> list[str]:
    events: list[str] = []
    for task in board.get("tasks", []):
        if task.get("status") != "done_waiting_review":
            continue
        task_id = task["task_id"]
        result = run_verification(task_id, paths)
        if result.passed:
            task["status"] = "verified"
            task["next_step"] = "Verified by Claude controller loop; keep as evidence"
            append_verification_ledger(task, result, paths)
            update_session_recovery(task, result, paths)
            events.append(f"verified {task_id}")
        else:
            task["status"] = "repair_requested"
            task["next_step"] = result.reason
            repair_packet = create_repair_packet(task, result, paths)
            enqueue_repair_task(board, task, repair_packet)
            events.append(f"repair_requested {task_id} -> {repair_packet['task_id']}")
    return events


def handle_blocked_tasks(board: dict[str, Any], paths: ControllerPaths) -> list[str]:
    events: list[str] = []
    for task in board.get("tasks", []):
        if task.get("status") != "blocked":
            continue
        if str(task.get("next_step", "")).startswith("Replayed inbox receipt; Claude controller will inspect blocker"):
            continue
        task_id = task["task_id"]
        packet = load_task_packet(task_id, paths)
        if packet:
            task["status"] = "ready_for_dispatch"
            task["next_step"] = "Controller found task packet context; re-dispatch through Codex worker"
            events.append(f"unblocked {task_id}")
        else:
            task["next_step"] = "Owner escalation required: task packet missing"
            events.append(f"owner_escalation_needed {task_id}")
    return events


def is_actionable_status(status: str | None) -> bool:
    return status not in {"completed", "verified", None}


def matches_recommendation(recommendation: str, task_id: str) -> bool:
    return task_id == recommendation or task_id.startswith(f"{recommendation}-")


def prioritize_repair_tasks(normalized: list[str], tasks: list[dict[str, Any]]) -> list[str]:
    repair_ids = {
        str(task.get("task_id"))
        for task in tasks
        if str(task.get("status")) in ACTIONABLE_DISPATCH_STATUSES
        and str(task.get("task_id", "")).find("-REPAIR-") != -1
    }
    if not repair_ids:
        return normalized
    repairs = [task_id for task_id in normalized if task_id in repair_ids]
    others = [task_id for task_id in normalized if task_id not in repair_ids]
    return repairs + others


def normalize_next_recommended_tasks(board: dict[str, Any]) -> list[str]:
    tasks = board.get("tasks", [])
    recommendations = [str(item) for item in board.get("next_recommended_tasks", [])]
    normalized: list[str] = []

    for recommendation in recommendations:
        matches = [
            task
            for task in tasks
            if matches_recommendation(recommendation, str(task.get("task_id", "")))
        ]
        actionable_matches = [
            task for task in matches if is_actionable_status(task.get("status"))
        ]
        if actionable_matches:
            for task in actionable_matches:
                task_id = str(task["task_id"])
                if task_id not in normalized:
                    normalized.append(task_id)
        elif not matches and recommendation not in normalized:
            normalized.append(recommendation)

    for task in tasks:
        task_id = str(task.get("task_id", ""))
        if task_id and is_actionable_status(task.get("status")) and task_id not in normalized:
            normalized.append(task_id)

    normalized = prioritize_repair_tasks(normalized, tasks)

    if normalized != board.get("next_recommended_tasks", []):
        board["next_recommended_tasks"] = normalized
        return ["normalized_next_recommended_tasks"]
    return []


def has_dispatchable_codex_task(board: dict[str, Any]) -> bool:
    for task in board.get("tasks", []):
        if task.get("owner") == "codex" and task.get("status") in ACTIONABLE_DISPATCH_STATUSES:
            return True
    return False


CLOSEOUT_BLOCKING_STATUSES = {
    "queued",
    "ready_for_dispatch",
    "in_progress",
    "done_waiting_review",
    "blocked",
    "repair_requested",
}


def _packet_owned_by_codex(packet: dict[str, Any]) -> bool:
    owner = str(packet.get("assigned_to") or packet.get("owner") or "")
    return owner == "codex"


def _packet_eligible_for_board_reconcile(packet: dict[str, Any]) -> bool:
    if not _packet_owned_by_codex(packet):
        return False
    task_id = str(packet.get("task_id", ""))
    if not task_id:
        return False
    if task_id.startswith("P1-AUTO-VERIFY-SMOKE-"):
        return False
    return True


def has_unreconciled_codex_packet(board: dict[str, Any], paths: ControllerPaths) -> bool:
    known_task_ids = {
        str(task.get("task_id", ""))
        for task in board.get("tasks", [])
        if str(task.get("task_id", ""))
    }
    ledger_text = paths.verification_ledger_path.read_text(encoding="utf-8")

    for packet_path in sorted(paths.task_packet_dir.glob("*.json")):
        try:
            packet = json.loads(packet_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not _packet_eligible_for_board_reconcile(packet):
            continue
        task_id = str(packet.get("task_id", ""))
        if not task_id or task_id in known_task_ids:
            continue
        if f"V-AUTO-{task_id}" in ledger_text:
            continue
        return True
    return False


def detect_completion_closeout(board: dict[str, Any], paths: ControllerPaths) -> bool:
    for task in board.get("tasks", []):
        if task.get("owner") == "codex" and task.get("status") in CLOSEOUT_BLOCKING_STATUSES:
            return False
    if board.get("next_recommended_tasks"):
        return False
    if load_unread_codex_messages(paths):
        return False
    if has_pending_inbox_receipt_without_task(board, paths):
        return False
    if has_unreconciled_codex_packet(board, paths):
        return False
    return True


def _closeout_marker(board: dict[str, Any]) -> str:
    goal = str(board.get("current_goal") or "controller-loop")
    goal_slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in goal).strip("-")
    while "--" in goal_slug:
        goal_slug = goal_slug.replace("--", "-")
    goal_slug = goal_slug[:48] or "controller-loop"

    generated_at = str(board.get("generated_at") or "unknown")
    generated_slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in generated_at).strip("-")
    while "--" in generated_slug:
        generated_slug = generated_slug.replace("--", "-")
    generated_slug = generated_slug[:24] or "unknown"

    return f"D-AUTO-CLOSEOUT-{goal_slug}-{generated_slug}"


def append_closeout_decision_once(board: dict[str, Any], paths: ControllerPaths) -> bool:
    marker = _closeout_marker(board)
    if paths.decision_log_path.exists():
        text = paths.decision_log_path.read_text(encoding="utf-8")
    else:
        text = "# DECISION LOG\n"
    if marker in text:
        return False

    today = datetime.now().strftime("%Y-%m-%d")
    goal = str(board.get("current_goal") or "当前自治目标")
    entry = (
        f"\n## {today} {marker}\n"
        "**Decision:** Claude controller 检测到本轮自治 closeout 已收口，可视为 stop-ready 完成态  \n"
        f"**Reason:** `{goal}` 当前无 actionable Codex 任务、`next_recommended_tasks` 为空、未读 Codex 消息为空，且不存在未收敛的 Codex task packet。\n"
    )
    paths.decision_log_path.write_text(text.rstrip() + entry + "\n", encoding="utf-8")
    return True


def run_controller_pass(board: dict[str, Any], paths: ControllerPaths, *, auto_dispatch: bool) -> PassResult:
    events: list[str] = []

    messages = load_unread_codex_messages(paths)
    read_ids, unhandled_messages, message_events = sync_messages_into_board(board, messages, paths)
    events.extend(message_events)
    if read_ids:
        mark_messages_read(read_ids, paths)
        events.append(f"marked_read {len(read_ids)}")

    inbox_replay_events = reconcile_inbox_receipts(board, paths)
    events.extend(inbox_replay_events)

    blocked_events = handle_blocked_tasks(board, paths)
    events.extend(blocked_events)

    reconcile_events = reconcile_missing_codex_tasks(board, paths, unhandled_messages)
    events.extend(reconcile_events)

    verified_reconcile_events = reconcile_verified_tasks_from_ledger(board, paths, unhandled_messages)
    events.extend(verified_reconcile_events)

    done_events = handle_done_waiting_review(board, paths)
    events.extend(done_events)
    events.extend(normalize_next_recommended_tasks(board))

    worker_status: str | None = None
    worker_task_id: str | None = None
    should_save_before_worker = bool(events) or has_dispatchable_codex_task(board)
    if should_save_before_worker:
        save_task_board(board, paths)

    if auto_dispatch and has_dispatchable_codex_task(board):
        worker_result = run_worker_once_result(
            dry_run=False,
            resume=os.getenv("XAGENT_CODEX_RESUME", "019ecfe8-0db5-7b12-b1c0-e5acfc1985f3"),
            timeout=int(os.getenv("XAGENT_CODEX_DISPATCH_TIMEOUT", "1800")),
            task_board_path=paths.task_board_path,
            task_packet_dir=paths.task_packet_dir,
            repo_root=paths.repo_root,
        )
        worker_status = worker_result.status
        worker_task_id = worker_result.task_id
        if worker_result.status in {"dispatched", "blocked", "dry_run", "missing_packet"}:
            label = worker_result.task_id or worker_result.status
            events.append(f"worker_{worker_result.status} {label}")
        elif worker_result.status == "no_task":
            events.append("no_dispatchable_tasks")

    return PassResult(
        events=events,
        unread_messages=len(messages),
        worker_status=worker_status,
        worker_task_id=worker_task_id,
    )


def run_once(paths: ControllerPaths | None = None, *, auto_dispatch: bool = True, max_passes: int = 5) -> dict[str, Any]:
    paths = paths or default_paths()
    events: list[str] = []
    unread_messages = 0

    for _ in range(max_passes):
        board = load_task_board(paths)
        pass_result = run_controller_pass(board, paths, auto_dispatch=auto_dispatch)
        unread_messages = pass_result.unread_messages
        if pass_result.events:
            events.extend(pass_result.events)
            continue
        break

    final_board = load_task_board(paths)
    promote_events: list[str] = []
    promoted = False
    tasks = final_board.get("tasks", [])
    active_protocol_tasks = [
        task for task in tasks
        if str(task.get("task_id", "")).startswith("P1-CODEX-PRODUCTIZATION")
        and task.get("status") in {"ready_for_dispatch", "in_progress", "done_waiting_review", "repair_requested", "blocked"}
    ]
    if not active_protocol_tasks:
        for task_id in final_board.get("next_recommended_tasks", []):
            task = find_task(final_board, str(task_id))
            if task and task.get("owner") == "codex" and task.get("status") == "queued":
                task["status"] = "ready_for_dispatch"
                task["next_step"] = "Prior task verified; ready for Codex execution"
                promoted = True
                promote_events.append(f"promoted {task['task_id']}")
                break
    if promoted:
        promote_events.extend(normalize_next_recommended_tasks(final_board))
        save_task_board(final_board, paths)
        events.extend(promote_events)

    completion_state: str | None = None
    if detect_completion_closeout(final_board, paths):
        completion_state = "stop_ready"
        if append_closeout_decision_once(final_board, paths):
            events.append("completion_closeout_logged")
        events.append("completion_closeout_detected")

    return {
        "events": events,
        "unread_messages": unread_messages,
        "task_board": str(paths.task_board_path),
        "completion_state": completion_state,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Claude controller loop for X-Agent task board")
    parser.add_argument("--once", action="store_true", help="run one controller pass")
    parser.add_argument("--watch", action="store_true", help="run continuously")
    parser.add_argument("--interval", type=int, default=10, help="watch interval seconds")
    parser.add_argument("--auto-dispatch", action="store_true", help="enable worker auto dispatch bridge")
    args = parser.parse_args()

    if args.watch:
        while True:
            result = run_once(auto_dispatch=args.auto_dispatch)
            print(json.dumps(result, ensure_ascii=False), flush=True)
            time.sleep(args.interval)

    result = run_once(auto_dispatch=args.auto_dispatch)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
