from __future__ import annotations

import argparse
import math
import subprocess
import sys
import time
from collections import OrderedDict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


def _ensure_source_root() -> Path:
    source_root = Path(__file__).resolve().parents[1]
    source_root_text = str(source_root)
    if source_root_text not in sys.path:
        sys.path.insert(0, source_root_text)
    return source_root


SOURCE_ROOT = _ensure_source_root()

from backend.app.core.storage import atomic_write_json  # noqa: E402

DEFAULT_OUTPUT = Path(".xagent_runtime/reports/pytest-evidence.json")
DEFAULT_SHARDS = 12
DEFAULT_TIMEOUT_SECONDS = 600.0
DEFAULT_COLLECT_TIMEOUT_SECONDS = 120.0
DEFAULT_MAX_NODEIDS_PER_SHARD = 80


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False


Runner = Callable[[list[str], Path, float], CommandResult]


def run_pytest_evidence(
    *,
    source_root: Path,
    output: Path = DEFAULT_OUTPUT,
    shard_count: int = DEFAULT_SHARDS,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    collect_timeout_seconds: float = DEFAULT_COLLECT_TIMEOUT_SECONDS,
    max_nodeids_per_shard: int = DEFAULT_MAX_NODEIDS_PER_SHARD,
    runner: Runner | None = None,
) -> dict:
    source_root = source_root.resolve()
    output = output if output.is_absolute() else source_root / output
    runner = runner or _run_command

    started = time.perf_counter()
    collect_command = [sys.executable, "-m", "pytest", "--collect-only", "-q"]
    collect = runner(collect_command, source_root, collect_timeout_seconds)
    if collect.returncode != 0:
        payload = _payload(
            source_root=source_root,
            status="collect_failed" if not collect.timed_out else "collect_timed_out",
            started=started,
            collect=collect,
            shards=[],
            collected_items=[],
            shard_count=shard_count,
            max_nodeids_per_shard=max_nodeids_per_shard,
        )
        atomic_write_json(output, payload)
        return payload

    items = _parse_collect_output(collect.stdout)
    shards = _build_file_shards(items, shard_count, max_nodeids_per_shard=max_nodeids_per_shard)
    shard_results = []
    for index, shard in enumerate(shards, start=1):
        files = [item["file"] for item in shard["files"]]
        targets = list(shard["targets"])
        print(
            f"pytest shard {index}/{len(shards)}: "
            f"{shard['nodeid_count']} tests across {len(files)} files via {shard['target_type']}",
            flush=True,
        )
        command = [sys.executable, "-m", "pytest", "-q", *targets]
        result = runner(command, source_root, timeout_seconds)
        shard_results.append(
            {
                "index": index,
                "status": _result_status(result),
                "command": result.command,
                "returncode": result.returncode,
                "timed_out": result.timed_out,
                "duration_seconds": round(result.duration_seconds, 3),
                "file_count": len(files),
                "nodeid_count": shard["nodeid_count"],
                "target_type": shard["target_type"],
                "target_count": len(targets),
                "split": shard["split"],
                "split_file": shard.get("split_file"),
                "targets": targets,
                "files": files,
                "stdout_tail": _tail_text(result.stdout),
                "stderr_tail": _tail_text(result.stderr),
            }
        )
        if result.stdout:
            print(_tail_text(result.stdout, limit=2000), end="" if result.stdout.endswith("\n") else "\n", flush=True)
        if result.stderr:
            print(
                _tail_text(result.stderr, limit=2000),
                end="" if result.stderr.endswith("\n") else "\n",
                file=sys.stderr,
                flush=True,
            )
        if result.returncode != 0:
            break

    status = "passed"
    if any(item["timed_out"] for item in shard_results):
        status = "timed_out"
    elif any(item["returncode"] != 0 for item in shard_results):
        status = "failed"
    elif len(shard_results) != len(shards):
        status = "incomplete"

    payload = _payload(
        source_root=source_root,
        status=status,
        started=started,
        collect=collect,
        shards=shard_results,
        collected_items=items,
        shard_count=shard_count,
        max_nodeids_per_shard=max_nodeids_per_shard,
    )
    atomic_write_json(output, payload)
    return payload


def _payload(
    *,
    source_root: Path,
    status: str,
    started: float,
    collect: CommandResult,
    shards: list[dict],
    collected_items: list[dict[str, str]],
    shard_count: int,
    max_nodeids_per_shard: int,
) -> dict:
    total_duration = time.perf_counter() - started
    failed = [item for item in shards if item.get("returncode") != 0]
    timed_out = [item for item in shards if item.get("timed_out") is True]
    return {
        "kind": "pytest_evidence",
        "version": 1,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "source_root": str(source_root),
        "ok": status == "passed",
        "status": status,
        "summary": {
            "collected": len(collected_items),
            "requested_shards": shard_count,
            "planned_shards": _planned_shard_count(
                collected_items,
                shard_count,
                max_nodeids_per_shard=max_nodeids_per_shard,
            ),
            "max_nodeids_per_shard": max(0, int(max_nodeids_per_shard)),
            "completed_shards": len(shards),
            "passed_shards": sum(1 for item in shards if item.get("status") == "passed"),
            "failed_shards": len(failed),
            "timed_out_shards": len(timed_out),
            "file_target_shards": sum(1 for item in shards if item.get("target_type") == "files"),
            "nodeid_target_shards": sum(1 for item in shards if item.get("target_type") == "nodeids"),
            "split_nodeid_shards": sum(1 for item in shards if item.get("split") is True),
            "largest_shard_nodeids": max((int(item.get("nodeid_count") or 0) for item in shards), default=0),
            "duration_seconds": round(total_duration, 3),
        },
        "collect": {
            "command": collect.command,
            "returncode": collect.returncode,
            "timed_out": collect.timed_out,
            "duration_seconds": round(collect.duration_seconds, 3),
            "stdout_tail": _tail_text(collect.stdout),
            "stderr_tail": _tail_text(collect.stderr),
        },
        "shards": shards,
        "shards_count": len(shards),
    }


def _run_command(command: list[str], cwd: Path, timeout_seconds: float) -> CommandResult:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            command=command,
            returncode=124,
            stdout=_timeout_text(exc.stdout),
            stderr=_timeout_text(exc.stderr) or f"command timed out after {timeout_seconds} seconds",
            duration_seconds=time.perf_counter() - started,
            timed_out=True,
        )
    return CommandResult(
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        duration_seconds=time.perf_counter() - started,
    )


def _parse_collect_output(output: str) -> list[dict[str, str]]:
    items = []
    seen = set()
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if "::" not in line:
            continue
        file_path = line.split("::", 1)[0].replace("\\", "/")
        if not file_path.startswith("tests/"):
            continue
        if line in seen:
            continue
        seen.add(line)
        items.append({"nodeid": line, "file": file_path})
    return items


def _build_file_shards(
    items: Sequence[dict[str, str]],
    shard_count: int,
    *,
    max_nodeids_per_shard: int = DEFAULT_MAX_NODEIDS_PER_SHARD,
) -> list[dict]:
    if not items:
        return []
    shard_count = max(1, int(shard_count))
    max_nodeids_per_shard = max(0, int(max_nodeids_per_shard))
    by_file: OrderedDict[str, list[str]] = OrderedDict()
    for item in items:
        by_file.setdefault(item["file"], []).append(item["nodeid"])
    files = [{"file": file, "nodeids": nodeids} for file, nodeids in by_file.items()]
    target = max(1, math.ceil(len(items) / min(shard_count, len(files))))
    split_limit = target
    if max_nodeids_per_shard:
        split_limit = min(target, max_nodeids_per_shard)

    full_file_units = []
    shards = []
    for item in files:
        nodeids = list(item["nodeids"])
        if max_nodeids_per_shard and len(nodeids) > split_limit:
            if full_file_units:
                shards.extend(_pack_file_units(full_file_units, shard_count, target))
                full_file_units = []
            for chunk in _chunked(nodeids, split_limit):
                file_item = {"file": item["file"], "nodeids": chunk}
                shards.append(
                    {
                        "nodeid_count": len(chunk),
                        "files": [file_item],
                        "targets": chunk,
                        "target_type": "nodeids",
                        "split": True,
                        "split_file": item["file"],
                    }
                )
            continue
        full_file_units.append(item)

    if full_file_units:
        shards.extend(_pack_file_units(full_file_units, shard_count, target))
    return shards


def _pack_file_units(files: Sequence[dict[str, object]], shard_count: int, target: int) -> list[dict]:
    if not files:
        return []
    if shard_count == 1 or len(files) == 1:
        file_items = list(files)
        return [_file_target_shard(file_items, sum(len(item["nodeids"]) for item in file_items))]

    shards = []
    current: list[dict[str, object]] = []
    current_count = 0
    for index, item in enumerate(files):
        current.append(item)
        current_count += len(item["nodeids"])
        remaining_files = len(files) - index - 1
        remaining_slots = shard_count - len(shards) - 1
        if current_count >= target and remaining_slots > 0 and remaining_files >= remaining_slots:
            shards.append(_file_target_shard(current, current_count))
            current = []
            current_count = 0
    if current:
        shards.append(_file_target_shard(current, current_count))
    return shards


def _file_target_shard(files: Sequence[dict[str, object]], nodeid_count: int) -> dict:
    file_items = list(files)
    return {
        "nodeid_count": nodeid_count,
        "files": file_items,
        "targets": [str(item["file"]) for item in file_items],
        "target_type": "files",
        "split": False,
        "split_file": None,
    }


def _chunked(values: Sequence[str], size: int) -> list[list[str]]:
    size = max(1, int(size))
    return [list(values[index : index + size]) for index in range(0, len(values), size)]


def _planned_shard_count(
    items: Sequence[dict[str, str]],
    shard_count: int,
    *,
    max_nodeids_per_shard: int = DEFAULT_MAX_NODEIDS_PER_SHARD,
) -> int:
    return len(_build_file_shards(items, shard_count, max_nodeids_per_shard=max_nodeids_per_shard))


def _result_status(result: CommandResult) -> str:
    if result.timed_out:
        return "timed_out"
    return "passed" if result.returncode == 0 else "failed"


def _tail_text(value: str | bytes | None, *, limit: int = 6000) -> str:
    text = _timeout_text(value)
    if len(text) <= limit:
        return text
    return text[-limit:]


def _timeout_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Run pytest in deterministic shards and write audit evidence.")
    parser.add_argument("--source-root", type=Path, default=SOURCE_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--shards", type=int, default=DEFAULT_SHARDS)
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--collect-timeout-seconds", type=float, default=DEFAULT_COLLECT_TIMEOUT_SECONDS)
    parser.add_argument(
        "--max-nodeids-per-shard",
        type=int,
        default=DEFAULT_MAX_NODEIDS_PER_SHARD,
        help="Split oversized test files into nodeid shards at this size; use 0 to disable nodeid splitting.",
    )
    args = parser.parse_args()

    payload = run_pytest_evidence(
        source_root=args.source_root,
        output=args.output,
        shard_count=args.shards,
        timeout_seconds=args.timeout_seconds,
        collect_timeout_seconds=args.collect_timeout_seconds,
        max_nodeids_per_shard=args.max_nodeids_per_shard,
    )
    print(
        f"pytest evidence {payload['status']}: "
        f"{payload['summary']['collected']} collected, "
        f"{payload['summary']['passed_shards']}/{payload['summary']['planned_shards']} shards passed",
        flush=True,
    )
    return 0 if payload["ok"] else 124 if payload["status"] in {"timed_out", "collect_timed_out"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
