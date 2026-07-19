from __future__ import annotations

import hashlib
from pathlib import Path

from scripts.rc_staging_plan import build_staging_commands, build_staging_plan, validate_stage_paths


def _manifest(path: Path) -> Path:
    path.write_text(
        """
## Tracked Modified Candidate Files

```text
README.md
backend/app/main.py
```

## New Candidate Files

```text
scripts/rc_final_gate.py
```
""",
        encoding="utf-8",
    )
    return path


def test_validate_stage_paths_rejects_missing_and_excluded(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")

    valid, missing, excluded = validate_stage_paths(
        ["README.md", ".codex/config.toml", "missing.py"],
        root=tmp_path,
    )

    assert valid == ["README.md"]
    assert missing == ["missing.py"]
    assert excluded == [".codex/config.toml"]


def test_validate_stage_paths_rejects_unsafe_manifest_paths(tmp_path: Path) -> None:
    valid, missing, excluded = validate_stage_paths(
        [
            "../outside.txt",
            "/tmp/outside.txt",
            "C:\\Temp\\secret.txt",
            "dir//file.py",
            "dir/./file.py",
        ],
        root=tmp_path,
    )

    assert valid == []
    assert missing == []
    assert excluded == sorted(
        [
            "../outside.txt",
            "/tmp/outside.txt",
            "C:/Temp/secret.txt",
            "dir//file.py",
            "dir/./file.py",
        ]
    )


def test_build_staging_commands_chunks_and_quotes_paths() -> None:
    commands = build_staging_commands(["a.py", "dir/file name.py", "z.py"], chunk_size=2)

    assert len(commands) == 2
    assert commands[0].command == 'git add -- "a.py" "dir/file name.py"'
    assert commands[1].command == 'git add -- "z.py"'


def test_build_staging_plan_from_manifest_without_mutation(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path / "manifest.md")
    (tmp_path / "README.md").write_text("readme", encoding="utf-8")
    (tmp_path / "backend" / "app").mkdir(parents=True)
    (tmp_path / "backend" / "app" / "main.py").write_text("print('ok')", encoding="utf-8")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "rc_final_gate.py").write_text("print('gate')", encoding="utf-8")

    report = build_staging_plan(manifest_path=manifest, root=tmp_path, chunk_size=2)

    assert report.status == "planned"
    assert report.manifest_sha256 == hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert report.file_count == 3
    assert report.command_count == 2
    assert report.errors == []
    assert "git diff --cached --stat" in report.next_commands[-1]


def test_build_staging_plan_fails_on_manifest_excluded_path(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.md"
    manifest.write_text(
        """
## Tracked Modified Candidate Files

```text
.agents/config.toml
```
""",
        encoding="utf-8",
    )

    report = build_staging_plan(manifest_path=manifest, root=tmp_path)

    assert report.status == "failed"
    assert report.excluded_files == [".agents/config.toml"]
