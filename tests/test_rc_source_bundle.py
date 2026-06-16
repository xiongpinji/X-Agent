from __future__ import annotations

import zipfile
from pathlib import Path

from scripts.rc_source_bundle import build_bundle, inspect_bundle_files, is_safe_manifest_path, manifest_candidate_paths


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


def test_manifest_candidate_paths_reads_tracked_and_new_blocks(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path / "manifest.md")

    assert manifest_candidate_paths(manifest) == [
        "README.md",
        "backend/app/main.py",
        "scripts/rc_final_gate.py",
    ]


def test_inspect_bundle_files_rejects_excluded_paths(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")

    files, missing, excluded = inspect_bundle_files(
        ["README.md", ".agents/config.toml", "missing.py"],
        root=tmp_path,
    )

    assert [item.path for item in files] == ["README.md"]
    assert missing == ["missing.py"]
    assert excluded == [".agents/config.toml"]


def test_inspect_bundle_files_rejects_unsafe_manifest_paths(tmp_path: Path) -> None:
    files, missing, excluded = inspect_bundle_files(
        [
            "../outside.txt",
            "/tmp/outside.txt",
            "C:\\Temp\\secret.txt",
            "dir//file.py",
            "dir/./file.py",
        ],
        root=tmp_path,
    )

    assert files == []
    assert missing == []
    assert excluded == [
        "../outside.txt",
        "/tmp/outside.txt",
        "C:/Temp/secret.txt",
        "dir//file.py",
        "dir/./file.py",
    ]
    assert not is_safe_manifest_path("../outside.txt")


def test_build_bundle_dry_run_does_not_write_zip(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path / "manifest.md")
    (tmp_path / "README.md").write_text("readme", encoding="utf-8")
    (tmp_path / "backend" / "app").mkdir(parents=True)
    (tmp_path / "backend" / "app" / "main.py").write_text("print('ok')", encoding="utf-8")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "rc_final_gate.py").write_text("print('gate')", encoding="utf-8")
    output = tmp_path / "bundle.zip"

    report = build_bundle(manifest_path=manifest, output_path=output, dry_run=True, root=tmp_path)

    assert report.status == "planned"
    assert report.output_path is None
    assert report.file_count == 3
    assert not output.exists()


def test_build_bundle_create_writes_zip(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path / "manifest.md")
    (tmp_path / "README.md").write_text("readme", encoding="utf-8")
    (tmp_path / "backend" / "app").mkdir(parents=True)
    (tmp_path / "backend" / "app" / "main.py").write_text("print('ok')", encoding="utf-8")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "rc_final_gate.py").write_text("print('gate')", encoding="utf-8")
    output = tmp_path / "bundle.zip"

    report = build_bundle(manifest_path=manifest, output_path=output, dry_run=False, root=tmp_path)

    assert report.status == "created"
    assert report.output_path == str(output)
    with zipfile.ZipFile(output) as archive:
        assert sorted(archive.namelist()) == [
            "README.md",
            "backend/app/main.py",
            "scripts/rc_final_gate.py",
        ]
