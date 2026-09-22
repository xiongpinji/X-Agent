from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import tempfile

from scripts.claude_controller_loop import (
    is_control_signal_task_id,
    is_historical_closeout_task_id,
    parse_inbox_receipt,
)


@dataclass(frozen=True)
class ArchiveResult:
    archived_count: int


LEGACY_CLOSEOUT_PREFIXES = ("B2-", "F-")
DECISION_MARKER = "D-AUTO-ARCHIVE-CONTROL-SIGNAL"


def is_historical_legacy_closeout_task_id(task_id: str) -> bool:
    return task_id.startswith(LEGACY_CLOSEOUT_PREFIXES)


def should_archive_receipt(task_id: str) -> bool:
    return is_control_signal_task_id(task_id) or is_historical_closeout_task_id(task_id)


def append_decision_log(decision_log_path: Path, archived_names: list[str]) -> None:
    if not archived_names:
        return

    text = (
        decision_log_path.read_text(encoding="utf-8")
        if decision_log_path.exists()
        else "# DECISION LOG\n"
    )

    today = datetime.now().strftime("%Y-%m-%d")
    entry = (
        f"\n## {today} {DECISION_MARKER}\n"
        "**Decision:** 归档历史 control/legacy receipts  \n"
        "**Reason:** 从当前 closeout 语义面移除非任务回执。  \n"
        f"**Archived receipts:** {', '.join(archived_names)}\n"
    )
    new_text = text.rstrip() + entry + "\n"
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=decision_log_path.parent,
        delete=False,
    ) as temp_file:
        temp_file.write(new_text)
        temp_path = Path(temp_file.name)
    try:
        temp_path.replace(decision_log_path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise



def archive_closeout_receipts(inbox_dir: Path, decision_log_path: Path) -> ArchiveResult:
    archive_dir = inbox_dir / "_archived_closeout"
    archive_dir.mkdir(parents=True, exist_ok=True)

    archived_names: list[str] = []
    moved_receipts: list[tuple[Path, Path]] = []
    duplicate_receipts_to_delete: list[Path] = []
    try:
        for receipt_path in sorted(inbox_dir.glob("*.md")):
            receipt = parse_inbox_receipt(receipt_path)
            if not receipt:
                continue
            task_id = receipt["task_id"]
            if not should_archive_receipt(task_id):
                continue

            target_path = archive_dir / receipt_path.name
            if target_path.exists():
                duplicate_receipts_to_delete.append(receipt_path)
                continue

            receipt_path.replace(target_path)
            moved_receipts.append((receipt_path, target_path))
            archived_names.append(receipt_path.name)

        append_decision_log(decision_log_path, archived_names)
    except Exception:
        for source_path, archived_path in reversed(moved_receipts):
            if archived_path.exists() and not source_path.exists():
                archived_path.replace(source_path)
        raise

    for receipt_path in duplicate_receipts_to_delete:
        if receipt_path.exists():
            receipt_path.unlink()
    return ArchiveResult(archived_count=len(archived_names))
