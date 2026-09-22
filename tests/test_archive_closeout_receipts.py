from __future__ import annotations


from pathlib import Path

import pytest


def _write_receipt(inbox: Path, filename: str, task_id: str, status: str) -> Path:
    receipt = inbox / filename
    receipt.write_text(
        "---\n"
        "from: codex\n"
        "to: zcode\n"
        "ts: 2026-07-01T00:00:00+00:00\n"
        f"task_id: {task_id}\n"
        f"status: {status}\n"
        "---\n",
        encoding="utf-8",
    )
    return receipt


def test_archive_closeout_receipts_moves_control_and_legacy_receipts(tmp_path):
    from scripts.archive_closeout_receipts import archive_closeout_receipts

    inbox = tmp_path / "inbox_zcode"
    inbox.mkdir(parents=True)
    control_receipt = _write_receipt(
        inbox,
        "2026-07-01T00-00-00_CODEX-WORKER-LOOP-blocked.md",
        "CODEX-WORKER-LOOP",
        "blocked",
    )
    legacy_b2_receipt = _write_receipt(
        inbox,
        "2026-07-01T00-05-00_B2-123-done.md",
        "B2-123",
        "done",
    )
    legacy_f_receipt = _write_receipt(
        inbox,
        "2026-07-01T00-06-00_F-456-blocked.md",
        "F-456",
        "blocked",
    )
    decision_log = tmp_path / "DECISION_LOG.md"
    decision_log.write_text("# DECISION LOG\n", encoding="utf-8")

    result = archive_closeout_receipts(inbox, decision_log)

    archived_dir = inbox / "_archived_closeout"
    assert (archived_dir / control_receipt.name).exists()
    assert not control_receipt.exists()
    assert (archived_dir / legacy_b2_receipt.name).exists()
    assert not legacy_b2_receipt.exists()
    assert (archived_dir / legacy_f_receipt.name).exists()
    assert not legacy_f_receipt.exists()
    assert result.archived_count == 3

    decision_log_text = decision_log.read_text(encoding="utf-8")
    assert "ARCHIVE-CONTROL-SIGNAL" in decision_log_text
    assert control_receipt.name in decision_log_text
    assert legacy_b2_receipt.name in decision_log_text
    assert legacy_f_receipt.name in decision_log_text


def test_archive_closeout_receipts_appends_decision_log_for_later_archive_runs(tmp_path):
    from scripts.archive_closeout_receipts import archive_closeout_receipts

    inbox = tmp_path / "inbox_zcode"
    inbox.mkdir(parents=True)
    first_receipt = _write_receipt(
        inbox,
        "2026-07-01T00-00-00_CODEX-WORKER-LOOP-blocked.md",
        "CODEX-WORKER-LOOP",
        "blocked",
    )
    decision_log = tmp_path / "DECISION_LOG.md"
    decision_log.write_text("# DECISION LOG\n", encoding="utf-8")

    first_result = archive_closeout_receipts(inbox, decision_log)

    second_receipt = _write_receipt(
        inbox,
        "2026-07-01T00-05-00_F-456-blocked.md",
        "F-456",
        "blocked",
    )
    second_result = archive_closeout_receipts(inbox, decision_log)

    archived_dir = inbox / "_archived_closeout"
    decision_log_text = decision_log.read_text(encoding="utf-8")

    assert first_result.archived_count == 1
    assert second_result.archived_count == 1
    assert (archived_dir / first_receipt.name).exists()
    assert (archived_dir / second_receipt.name).exists()
    assert decision_log_text.count("D-AUTO-ARCHIVE-CONTROL-SIGNAL") == 2
    assert first_receipt.name in decision_log_text
    assert second_receipt.name in decision_log_text



def test_archive_closeout_receipts_is_idempotent_for_receipt_already_in_archive(tmp_path):
    from scripts.archive_closeout_receipts import archive_closeout_receipts

    inbox = tmp_path / "inbox_zcode"
    inbox.mkdir(parents=True)
    receipt_name = "2026-07-01T00-05-00_F-456-blocked.md"
    first_receipt = _write_receipt(
        inbox,
        receipt_name,
        "F-456",
        "blocked",
    )
    decision_log = tmp_path / "DECISION_LOG.md"
    decision_log.write_text("# DECISION LOG\n", encoding="utf-8")

    first_result = archive_closeout_receipts(inbox, decision_log)

    duplicate_receipt = _write_receipt(
        inbox,
        receipt_name,
        "F-456",
        "blocked",
    )
    second_result = archive_closeout_receipts(inbox, decision_log)

    archived_dir = inbox / "_archived_closeout"
    decision_log_text = decision_log.read_text(encoding="utf-8")

    assert first_result.archived_count == 1
    assert second_result.archived_count == 0
    assert (archived_dir / first_receipt.name).exists()
    assert not duplicate_receipt.exists()
    assert decision_log_text.count("D-AUTO-ARCHIVE-CONTROL-SIGNAL") == 1
    assert decision_log_text.count(first_receipt.name) == 1



def test_archive_closeout_receipts_keeps_duplicate_receipt_when_later_log_append_fails(tmp_path, monkeypatch):
    import scripts.archive_closeout_receipts as archive_module

    inbox = tmp_path / "inbox_zcode"
    inbox.mkdir(parents=True)
    receipt_name = "2026-07-01T00-05-00_F-456-blocked.md"
    archived_receipt = _write_receipt(
        inbox,
        receipt_name,
        "F-456",
        "blocked",
    )
    decision_log = tmp_path / "DECISION_LOG.md"
    decision_log.write_text("# DECISION LOG\n", encoding="utf-8")
    archive_module.archive_closeout_receipts(inbox, decision_log)

    duplicate_receipt = _write_receipt(
        inbox,
        receipt_name,
        "F-456",
        "blocked",
    )
    newly_archivable_receipt = _write_receipt(
        inbox,
        "2026-07-01T00-06-00_B2-123-done.md",
        "B2-123",
        "done",
    )

    def fail_append(_decision_log_path: Path, archived_names: list[str]) -> None:
        assert archived_names == [newly_archivable_receipt.name]
        raise OSError("disk full")

    monkeypatch.setattr(archive_module, "append_decision_log", fail_append)

    with pytest.raises(OSError, match="disk full"):
        archive_module.archive_closeout_receipts(inbox, decision_log)

    archived_dir = inbox / "_archived_closeout"
    assert duplicate_receipt.exists()
    assert (archived_dir / archived_receipt.name).exists()
    assert newly_archivable_receipt.exists()
    assert not (archived_dir / newly_archivable_receipt.name).exists()
    assert decision_log.read_text(encoding="utf-8").count("D-AUTO-ARCHIVE-CONTROL-SIGNAL") == 1



def test_archive_closeout_receipts_preserves_new_archives_when_duplicate_cleanup_fails_after_log_append(tmp_path, monkeypatch):
    import scripts.archive_closeout_receipts as archive_module

    inbox = tmp_path / "inbox_zcode"
    inbox.mkdir(parents=True)
    receipt_name = "2026-07-01T00-05-00_F-456-blocked.md"
    archived_receipt = _write_receipt(
        inbox,
        receipt_name,
        "F-456",
        "blocked",
    )
    decision_log = tmp_path / "DECISION_LOG.md"
    decision_log.write_text("# DECISION LOG\n", encoding="utf-8")
    archive_module.archive_closeout_receipts(inbox, decision_log)

    duplicate_receipt = _write_receipt(
        inbox,
        receipt_name,
        "F-456",
        "blocked",
    )
    newly_archivable_receipt = _write_receipt(
        inbox,
        "2026-07-01T00-06-00_B2-123-done.md",
        "B2-123",
        "done",
    )

    original_unlink = Path.unlink

    def fail_duplicate_cleanup(self: Path, *args, **kwargs) -> None:
        if self == duplicate_receipt:
            raise OSError("cleanup failed")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_duplicate_cleanup)

    with pytest.raises(OSError, match="cleanup failed"):
        archive_module.archive_closeout_receipts(inbox, decision_log)

    archived_dir = inbox / "_archived_closeout"
    decision_log_text = decision_log.read_text(encoding="utf-8")

    assert duplicate_receipt.exists()
    assert (archived_dir / archived_receipt.name).exists()
    assert (archived_dir / newly_archivable_receipt.name).exists()
    assert not newly_archivable_receipt.exists()
    assert decision_log_text.count("D-AUTO-ARCHIVE-CONTROL-SIGNAL") == 2
    assert newly_archivable_receipt.name in decision_log_text



def test_archive_closeout_receipts_archives_historical_legacy_done_but_keeps_current_done_receipt(tmp_path):
    from scripts.archive_closeout_receipts import archive_closeout_receipts

    inbox = tmp_path / "inbox_zcode"
    inbox.mkdir(parents=True)
    historical_legacy_done = _write_receipt(
        inbox,
        "2026-07-01T00-05-00_B2-123-done.md",
        "B2-123",
        "done",
    )
    active_current_done = _write_receipt(
        inbox,
        "2026-07-01T00-10-00_P1-CODEX-RUNTIME-053-done.md",
        "P1-CODEX-RUNTIME-053",
        "done",
    )
    decision_log = tmp_path / "DECISION_LOG.md"
    decision_log.write_text("# DECISION LOG\n", encoding="utf-8")

    result = archive_closeout_receipts(inbox, decision_log)

    archived_dir = inbox / "_archived_closeout"
    decision_log_text = decision_log.read_text(encoding="utf-8")

    assert (archived_dir / historical_legacy_done.name).exists()
    assert not historical_legacy_done.exists()
    assert active_current_done.exists()
    assert not (archived_dir / active_current_done.name).exists()
    assert result.archived_count == 1
    assert historical_legacy_done.name in decision_log_text
    assert active_current_done.name not in decision_log_text



def test_archive_closeout_receipts_keeps_active_task_receipt_in_inbox(tmp_path):
    from scripts.archive_closeout_receipts import archive_closeout_receipts

    inbox = tmp_path / "inbox_zcode"
    inbox.mkdir(parents=True)
    active_task_receipt = _write_receipt(
        inbox,
        "2026-07-01T00-10-00_P1-CODEX-RUNTIME-053-done_waiting_review.md",
        "P1-CODEX-RUNTIME-053",
        "done_waiting_review",
    )
    decision_log = tmp_path / "DECISION_LOG.md"
    decision_log.write_text("# DECISION LOG\n", encoding="utf-8")

    result = archive_closeout_receipts(inbox, decision_log)

    assert active_task_receipt.exists()
    assert not (inbox / "_archived_closeout" / active_task_receipt.name).exists()
    assert result.archived_count == 0
    assert "ARCHIVE-CONTROL-SIGNAL" not in decision_log.read_text(encoding="utf-8")



def test_archive_closeout_receipts_rolls_back_moves_when_decision_log_append_fails(tmp_path, monkeypatch):
    import scripts.archive_closeout_receipts as archive_module

    inbox = tmp_path / "inbox_zcode"
    inbox.mkdir(parents=True)
    control_receipt = _write_receipt(
        inbox,
        "2026-07-01T00-00-00_CODEX-WORKER-LOOP-blocked.md",
        "CODEX-WORKER-LOOP",
        "blocked",
    )
    legacy_receipt = _write_receipt(
        inbox,
        "2026-07-01T00-05-00_B2-123-done.md",
        "B2-123",
        "done",
    )
    decision_log = tmp_path / "DECISION_LOG.md"
    decision_log.write_text("# DECISION LOG\n", encoding="utf-8")

    def fail_append(_decision_log_path: Path, archived_names: list[str]) -> None:
        assert archived_names == [control_receipt.name, legacy_receipt.name]
        raise OSError("disk full")

    monkeypatch.setattr(archive_module, "append_decision_log", fail_append)

    with pytest.raises(OSError, match="disk full"):
        archive_module.archive_closeout_receipts(inbox, decision_log)

    archived_dir = inbox / "_archived_closeout"
    assert control_receipt.exists()
    assert legacy_receipt.exists()
    assert not (archived_dir / control_receipt.name).exists()
    assert not (archived_dir / legacy_receipt.name).exists()
    assert decision_log.read_text(encoding="utf-8") == "# DECISION LOG\n"



def test_archive_closeout_receipts_preserves_decision_log_when_atomic_append_swap_fails(tmp_path, monkeypatch):
    import scripts.archive_closeout_receipts as archive_module

    inbox = tmp_path / "inbox_zcode"
    inbox.mkdir(parents=True)
    control_receipt = _write_receipt(
        inbox,
        "2026-07-01T00-00-00_CODEX-WORKER-LOOP-blocked.md",
        "CODEX-WORKER-LOOP",
        "blocked",
    )
    decision_log = tmp_path / "DECISION_LOG.md"
    decision_log.write_text("# DECISION LOG\n", encoding="utf-8")

    original_replace = Path.replace

    def fail_atomic_swap(self: Path, target: Path) -> Path:
        if target == decision_log and self != decision_log:
            raise OSError("atomic swap failed")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", fail_atomic_swap)

    with pytest.raises(OSError, match="atomic swap failed"):
        archive_module.archive_closeout_receipts(inbox, decision_log)

    archived_dir = inbox / "_archived_closeout"
    assert control_receipt.exists()
    assert not (archived_dir / control_receipt.name).exists()
    assert decision_log.read_text(encoding="utf-8") == "# DECISION LOG\n"



def test_archive_closeout_receipts_keeps_current_done_receipt_for_controller_consumption(tmp_path):
    from scripts.archive_closeout_receipts import archive_closeout_receipts

    inbox = tmp_path / "inbox_zcode"
    inbox.mkdir(parents=True)
    active_current_done = _write_receipt(
        inbox,
        "2026-07-01T00-10-00_P1-CODEX-RUNTIME-053-done.md",
        "P1-CODEX-RUNTIME-053",
        "done",
    )
    decision_log = tmp_path / "DECISION_LOG.md"
    decision_log.write_text("# DECISION LOG\n", encoding="utf-8")

    result = archive_closeout_receipts(inbox, decision_log)

    assert active_current_done.exists()
    assert not (inbox / "_archived_closeout" / active_current_done.name).exists()
    assert result.archived_count == 0
    assert "ARCHIVE-CONTROL-SIGNAL" not in decision_log.read_text(encoding="utf-8")
