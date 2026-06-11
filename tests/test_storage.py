import json
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel

import backend.app.core.storage as storage_module
from backend.app.core.storage import (
    append_jsonl,
    atomic_write_json,
    dumps_json,
    load_json_array,
    load_jsonl,
    normalize_datetime_utc,
    parse_datetime_utc,
    parse_datetime_utc_strict,
    to_jsonable,
    try_parse_datetime_utc,
)


class StorageRecord(BaseModel):
    name: str


class StorageEnum(Enum):
    ACTIVE = "active"


def test_json_array_loader_tolerates_non_utf8_file(tmp_path) -> None:
    path = tmp_path / "records.json"
    path.write_bytes(b"\xff\xfe\x00\x00")

    assert load_json_array(path, StorageRecord) == []


def test_json_array_loader_skips_invalid_items(tmp_path) -> None:
    path = tmp_path / "records.json"
    path.write_text(
        json.dumps(
            [
                {"name": "kept-a"},
                {"missing": "name"},
                "not-an-object",
                {"name": "kept-b"},
            ]
        ),
        encoding="utf-8",
    )

    records = load_json_array(path, StorageRecord)

    assert [record.name for record in records] == ["kept-a", "kept-b"]


def test_jsonl_loader_tolerates_non_utf8_file(tmp_path) -> None:
    path = tmp_path / "records.jsonl"
    path.write_bytes(b"\xff\xfe\x00\x00")

    assert load_jsonl(path, StorageRecord) == []


def test_jsonl_loader_skips_invalid_lines_and_items(tmp_path) -> None:
    path = tmp_path / "records.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"name": "kept-a"}),
                "{not-json",
                json.dumps({"missing": "name"}),
                json.dumps("not-an-object"),
                json.dumps({"name": "kept-b"}),
            ]
        ),
        encoding="utf-8",
    )

    records = load_jsonl(path, StorageRecord)

    assert [record.name for record in records] == ["kept-a", "kept-b"]


def test_atomic_write_json_serializes_open_values(tmp_path) -> None:
    path = tmp_path / "payload.json"

    atomic_write_json(
        path,
        {
            "created_at": datetime(2026, 5, 11, 12, 0, tzinfo=UTC),
            "path": Path("runtime/state.json"),
        },
    )
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["created_at"] == "2026-05-11T12:00:00+00:00"
    assert payload["path"] in {"runtime/state.json", "runtime\\state.json"}


def test_atomic_write_json_retries_transient_replace_permission_error(monkeypatch, tmp_path) -> None:
    path = tmp_path / "payload.json"
    calls = []
    real_replace = storage_module.os.replace

    def flaky_replace(src, dst):
        calls.append((src, dst))
        if len(calls) < 3:
            raise PermissionError("file is temporarily locked")
        return real_replace(src, dst)

    monkeypatch.setattr(storage_module.os, "replace", flaky_replace)
    monkeypatch.setattr(storage_module.time, "sleep", lambda _: None)

    atomic_write_json(path, {"name": "kept"})

    assert json.loads(path.read_text(encoding="utf-8")) == {"name": "kept"}
    assert len(calls) == 3


def test_append_jsonl_serializes_open_values(tmp_path) -> None:
    path = tmp_path / "payload.jsonl"

    append_jsonl(
        path,
        {
            "created_at": datetime(2026, 5, 11, 12, 0, tzinfo=UTC),
            "path": Path("runtime/state.json"),
        },
    )
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["created_at"] == "2026-05-11T12:00:00+00:00"
    assert payload["path"] in {"runtime/state.json", "runtime\\state.json"}


def test_dumps_json_and_to_jsonable_serialize_open_values() -> None:
    raw = {
        "created_at": datetime(2026, 5, 11, 12, 0, tzinfo=UTC),
        "status": StorageEnum.ACTIVE,
        "path": Path("runtime/state.json"),
    }

    text = dumps_json(raw, separators=(",", ":"))
    payload = to_jsonable(raw)

    assert " " not in text
    assert payload["created_at"] == "2026-05-11T12:00:00+00:00"
    assert payload["status"] == "active"
    assert payload["path"] in {"runtime/state.json", "runtime\\state.json"}


def test_dumps_json_serializes_enum_values() -> None:
    payload = json.loads(dumps_json({"status": StorageEnum.ACTIVE}))

    assert payload["status"] == "active"


def test_datetime_helpers_normalize_to_utc() -> None:
    assert normalize_datetime_utc(datetime(2026, 5, 11, 12, 0)) == datetime(
        2026,
        5,
        11,
        12,
        0,
        tzinfo=UTC,
    )
    assert parse_datetime_utc("2026-05-11T20:30:00+08:00") == datetime(
        2026,
        5,
        11,
        12,
        30,
        tzinfo=UTC,
    )


def test_datetime_helper_uses_fallback_for_invalid_values() -> None:
    fallback = datetime(2026, 5, 11, 12, 0, tzinfo=UTC)

    assert parse_datetime_utc("not-a-date", fallback=fallback) is fallback


def test_try_parse_datetime_utc_returns_none_for_invalid_values() -> None:
    assert try_parse_datetime_utc("not-a-date") is None
    assert try_parse_datetime_utc("2026-05-11T20:30:00+08:00") == datetime(
        2026,
        5,
        11,
        12,
        30,
        tzinfo=UTC,
    )


def test_parse_datetime_utc_strict_rejects_invalid_values() -> None:
    try:
        parse_datetime_utc_strict("not-a-date")
    except TypeError as exc:
        assert "Expected datetime" in str(exc)
    else:
        raise AssertionError("Expected invalid datetime to fail.")
