from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, TypeVar
from uuid import uuid4

from pydantic import BaseModel, ValidationError

ModelT = TypeVar("ModelT", bound=BaseModel)


def load_json_array(path: Path, model: type[ModelT]) -> list[ModelT]:
    if not path.exists():
        return []
    try:
        raw_payload = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    if not raw_payload.strip():
        return []
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    records: list[ModelT] = []
    for item in payload:
        try:
            records.append(model.model_validate(item))
        except (TypeError, ValidationError):
            continue
    return records


def atomic_write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".tmp-{os.getpid()}-{uuid4().hex[:12]}.json")
    try:
        tmp_path.write_text(
            dumps_json(payload, indent=2),
            encoding="utf-8",
        )
        for attempt in range(6):
            try:
                os.replace(tmp_path, path)
                break
            except PermissionError:
                if attempt == 5:
                    raise
                time.sleep(0.025 * (attempt + 1))
    finally:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass
        except PermissionError:
            pass


def load_jsonl(path: Path, model: type[ModelT]) -> list[ModelT]:
    if not path.exists():
        return []
    records: list[ModelT] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                    records.append(model.model_validate(payload))
                except (json.JSONDecodeError, TypeError, ValidationError):
                    continue
    except (OSError, UnicodeDecodeError):
        return []
    return records


def append_jsonl(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(dumps_json(payload) + "\n")


def dumps_json(
    payload: object,
    *,
    indent: int | None = None,
    separators: tuple[str, str] | None = None,
    sort_keys: bool = False,
) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=indent,
        separators=separators,
        sort_keys=sort_keys,
        default=_json_default,
    )


def to_jsonable(payload: object) -> Any:
    return json.loads(dumps_json(payload))


def normalize_datetime_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def parse_datetime_utc(value: Any, *, fallback: datetime | None = None) -> datetime:
    parsed = try_parse_datetime_utc(value)
    if parsed is not None:
        return parsed
    return fallback or datetime.now(UTC)


def parse_datetime_utc_strict(value: Any) -> datetime:
    parsed = try_parse_datetime_utc(value)
    if parsed is None:
        raise TypeError("Expected datetime or ISO 8601 datetime string.")
    return parsed


def try_parse_datetime_utc(value: Any) -> datetime | None:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return None
    if isinstance(value, datetime):
        return normalize_datetime_utc(value)
    return None


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, os.PathLike):
        return str(value)
    return str(value)
