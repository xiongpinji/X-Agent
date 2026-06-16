from __future__ import annotations

import json
import sys
from pathlib import Path

from scripts import run_pytest_evidence


def test_parse_collect_output_keeps_only_test_nodeids() -> None:
    output = "\n".join(
        [
            "tests/test_a.py::test_one",
            "tests/test_a.py::test_one",
            "tests/test_b.py::TestDemo::test_two",
            "2 tests collected in 0.01s",
            "Installed 78 packages in 1.2s",
        ]
    )

    assert run_pytest_evidence._parse_collect_output(output) == [
        {"nodeid": "tests/test_a.py::test_one", "file": "tests/test_a.py"},
        {"nodeid": "tests/test_b.py::TestDemo::test_two", "file": "tests/test_b.py"},
    ]


def test_build_file_shards_preserves_file_order_and_covers_all_items() -> None:
    items = [
        {"nodeid": "tests/test_a.py::test_1", "file": "tests/test_a.py"},
        {"nodeid": "tests/test_a.py::test_2", "file": "tests/test_a.py"},
        {"nodeid": "tests/test_b.py::test_1", "file": "tests/test_b.py"},
        {"nodeid": "tests/test_c.py::test_1", "file": "tests/test_c.py"},
        {"nodeid": "tests/test_d.py::test_1", "file": "tests/test_d.py"},
    ]

    shards = run_pytest_evidence._build_file_shards(items, 2)

    assert [file["file"] for shard in shards for file in shard["files"]] == [
        "tests/test_a.py",
        "tests/test_b.py",
        "tests/test_c.py",
        "tests/test_d.py",
    ]
    assert sum(shard["nodeid_count"] for shard in shards) == 5
    assert len(shards) == 2


def test_build_file_shards_splits_oversized_file_into_nodeid_targets() -> None:
    items = [
        {"nodeid": f"tests/test_long_tasks.py::test_{index}", "file": "tests/test_long_tasks.py"}
        for index in range(7)
    ]
    items.append({"nodeid": "tests/test_small.py::test_one", "file": "tests/test_small.py"})

    shards = run_pytest_evidence._build_file_shards(items, 2, max_nodeids_per_shard=3)

    split_shards = [shard for shard in shards if shard["split"]]
    assert [shard["nodeid_count"] for shard in split_shards] == [3, 3, 1]
    assert all(shard["target_type"] == "nodeids" for shard in split_shards)
    assert all(target.startswith("tests/test_long_tasks.py::") for shard in split_shards for target in shard["targets"])
    assert shards[-1]["targets"] == ["tests/test_small.py"]
    assert sum(shard["nodeid_count"] for shard in shards) == 8


def test_run_pytest_evidence_writes_passed_shard_report(tmp_path: Path) -> None:
    calls = []

    def runner(command, cwd, timeout_seconds):  # noqa: ANN001
        calls.append((command, cwd, timeout_seconds))
        if "--collect-only" in command:
            return run_pytest_evidence.CommandResult(
                command=command,
                returncode=0,
                stdout="\n".join(
                    [
                        "tests/test_a.py::test_one",
                        "tests/test_b.py::test_two",
                        "tests/test_c.py::test_three",
                    ]
                ),
                stderr="",
                duration_seconds=0.1,
            )
        return run_pytest_evidence.CommandResult(
            command=command,
            returncode=0,
            stdout="passed\n",
            stderr="",
            duration_seconds=0.2,
        )

    output = tmp_path / "pytest-evidence.json"
    payload = run_pytest_evidence.run_pytest_evidence(
        source_root=tmp_path,
        output=output,
        shard_count=2,
        runner=runner,
    )

    assert payload["ok"] is True
    assert payload["status"] == "passed"
    assert payload["summary"]["collected"] == 3
    assert payload["summary"]["passed_shards"] == 2
    assert len(payload["shards"]) == 2
    assert json.loads(output.read_text(encoding="utf-8"))["kind"] == "pytest_evidence"
    assert calls[0][0] == [sys.executable, "-m", "pytest", "--collect-only", "-q"]


def test_run_pytest_evidence_runs_split_shards_by_nodeid(tmp_path: Path) -> None:
    calls = []
    collected = [
        *[f"tests/test_long_tasks.py::test_{index}" for index in range(5)],
        "tests/test_small.py::test_one",
    ]

    def runner(command, cwd, timeout_seconds):  # noqa: ANN001
        calls.append(command)
        if "--collect-only" in command:
            return run_pytest_evidence.CommandResult(
                command=command,
                returncode=0,
                stdout="\n".join(collected),
                stderr="",
                duration_seconds=0.1,
            )
        return run_pytest_evidence.CommandResult(
            command=command,
            returncode=0,
            stdout="passed\n",
            stderr="",
            duration_seconds=0.2,
        )

    payload = run_pytest_evidence.run_pytest_evidence(
        source_root=tmp_path,
        output=tmp_path / "pytest-evidence.json",
        shard_count=2,
        max_nodeids_per_shard=2,
        runner=runner,
    )

    pytest_targets = [call[4:] for call in calls[1:]]
    assert pytest_targets[0] == ["tests/test_long_tasks.py::test_0", "tests/test_long_tasks.py::test_1"]
    assert pytest_targets[1] == ["tests/test_long_tasks.py::test_2", "tests/test_long_tasks.py::test_3"]
    assert payload["summary"]["nodeid_target_shards"] == 3
    assert payload["summary"]["file_target_shards"] == 1
    assert payload["summary"]["largest_shard_nodeids"] == 2
    assert payload["shards"][0]["split_file"] == "tests/test_long_tasks.py"
    assert payload["shards"][-1]["targets"] == ["tests/test_small.py"]


def test_run_pytest_evidence_stops_at_failed_shard(tmp_path: Path) -> None:
    def runner(command, cwd, timeout_seconds):  # noqa: ANN001
        if "--collect-only" in command:
            return run_pytest_evidence.CommandResult(
                command=command,
                returncode=0,
                stdout="\n".join(
                    [
                        "tests/test_a.py::test_one",
                        "tests/test_b.py::test_two",
                        "tests/test_c.py::test_three",
                    ]
                ),
                stderr="",
                duration_seconds=0.1,
            )
        return run_pytest_evidence.CommandResult(
            command=command,
            returncode=2,
            stdout="failed\n",
            stderr="boom\n",
            duration_seconds=0.2,
        )

    payload = run_pytest_evidence.run_pytest_evidence(
        source_root=tmp_path,
        output=tmp_path / "pytest-evidence.json",
        shard_count=3,
        runner=runner,
    )

    assert payload["ok"] is False
    assert payload["status"] == "failed"
    assert payload["summary"]["completed_shards"] == 1
    assert payload["summary"]["failed_shards"] == 1
    assert payload["shards"][0]["stderr_tail"] == "boom\n"


def test_run_pytest_evidence_reports_collect_failure(tmp_path: Path) -> None:
    def runner(command, cwd, timeout_seconds):  # noqa: ANN001
        return run_pytest_evidence.CommandResult(
            command=command,
            returncode=4,
            stdout="",
            stderr="collect failed",
            duration_seconds=0.1,
        )

    payload = run_pytest_evidence.run_pytest_evidence(
        source_root=tmp_path,
        output=tmp_path / "pytest-evidence.json",
        runner=runner,
    )

    assert payload["ok"] is False
    assert payload["status"] == "collect_failed"
    assert payload["summary"]["collected"] == 0
    assert payload["collect"]["stderr_tail"] == "collect failed"
