from __future__ import annotations

from pathlib import Path

from scripts.rc_release_audit import (
    candidate_paths,
    is_excluded,
    is_safe_manifest_path,
    manifest_candidate_sections,
    manifest_candidate_paths,
    manifest_classification_mismatches,
    manifest_extra_paths,
    manifest_unsafe_path_findings,
    missing_from_manifest,
    repository_classification_paths,
    scan_excluded_reference_findings,
    scan_file_hygiene_findings,
    scan_local_path_findings,
    scan_secret_findings,
)


def _windows_user_path(*parts: str) -> str:
    return "C:" + "\\Users\\" + "canqu" + "\\" + "\\".join(parts)


def test_excluded_paths_cover_local_agent_and_analysis_artifacts() -> None:
    assert is_excluded(".agents/skills/example/SKILL.md")
    assert is_excluded(".codex/config.toml")
    assert is_excluded("backend/app/core/creative_studio/storyboard.py")
    assert is_excluded("backend/app/api/creative_studio.py")
    assert is_excluded("tests/test_creative_studio.py")
    assert is_excluded("AGENTS.md")
    assert is_excluded("COMPETITIVE_ANALYSIS_2026.md")
    assert not is_excluded("scripts/rc_runtime_smoke.py")


def test_missing_from_manifest_reports_candidate_omissions() -> None:
    manifest = "scripts/rc_runtime_smoke.py\n"

    assert missing_from_manifest(["scripts/rc_runtime_smoke.py", "tests/new_test.py"], manifest) == ["tests/new_test.py"]


def test_manifest_candidate_paths_extracts_only_staging_candidate_blocks() -> None:
    manifest = """
# X-Agent RC Staging Manifest

## Always Exclude Unless Owner Explicitly Approves

```text
AGENTS.md
```

## Tracked Modified Candidate Files

```text
scripts/rc_release_audit.py
```

## New Candidate Files

```text
tests/test_rc_release_audit.py
```

## Generated Evidence Not Intended For Git

```text
.xagent_runtime/reports/rc-release-audit.json
```
"""

    assert manifest_candidate_paths(manifest) == [
        "scripts/rc_release_audit.py",
        "tests/test_rc_release_audit.py",
    ]
    assert manifest_candidate_sections(manifest) == {
        "New Candidate Files": ["tests/test_rc_release_audit.py"],
        "Tracked Modified Candidate Files": ["scripts/rc_release_audit.py"],
    }


def test_manifest_extra_paths_reports_entries_not_in_current_candidate_diff() -> None:
    assert manifest_extra_paths(
        ["scripts/rc_release_audit.py", "tests/test_rc_release_audit.py"],
        ["scripts/rc_release_audit.py"],
    ) == ["tests/test_rc_release_audit.py"]


def test_candidate_paths_falls_back_to_manifest_when_diff_is_clean(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("scripts.rc_release_audit.ROOT", tmp_path)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "rc_runtime_smoke.py").write_text("print('ok')\n", encoding="utf-8")
    manifest = """
## Tracked Modified Candidate Files

```text
scripts/rc_runtime_smoke.py
missing.py
```

## New Candidate Files

```text
```
"""

    monkeypatch.setattr("scripts.rc_release_audit._git_lines", lambda *args: [])

    candidates, excluded, manifest_fallback = candidate_paths(manifest)

    assert candidates == ["scripts/rc_runtime_smoke.py"]
    assert excluded == []
    assert manifest_fallback is True


def test_candidate_paths_includes_staged_diff(monkeypatch) -> None:
    def fake_git_lines(*args: str) -> list[str]:
        if args == ("diff", "--name-only"):
            return []
        if args == ("diff", "--cached", "--name-only"):
            return ["scripts/rc_release_audit.py"]
        if args == ("ls-files", "--others", "--exclude-standard"):
            return []
        raise AssertionError(args)

    monkeypatch.setattr("scripts.rc_release_audit._git_lines", fake_git_lines)

    candidates, excluded, manifest_fallback = candidate_paths()

    assert candidates == ["scripts/rc_release_audit.py"]
    assert excluded == []
    assert manifest_fallback is False


def test_repository_classification_uses_ls_files_not_diff(monkeypatch) -> None:
    def fake_git_lines(*args: str) -> list[str]:
        if args == ("ls-tree", "-r", "--name-only", "HEAD"):
            return ["tracked_file.py"]
        if args == ("ls-files", "--cached"):
            return ["new_staged_file.py", "tracked_file.py"]
        if args == ("ls-files", "--others", "--exclude-standard"):
            return ["new_file.py"]
        raise AssertionError(args)

    monkeypatch.setattr("scripts.rc_release_audit._git_lines", fake_git_lines)

    tracked, untracked = repository_classification_paths()

    assert tracked == {"tracked_file.py"}
    assert untracked == {"new_file.py", "new_staged_file.py"}


def test_manifest_unsafe_path_findings_flags_absolute_and_traversal_paths() -> None:
    findings = manifest_unsafe_path_findings(
        [
            "scripts/rc_release_audit.py",
            "../outside.txt",
            "/tmp/outside.txt",
            "C:\\Temp\\secret.txt",
            "dir//file.py",
            "dir/./file.py",
        ]
    )

    assert [(finding.path, finding.reason) for finding in findings] == [
        ("../outside.txt", "unsafe path segment"),
        ("/tmp/outside.txt", "absolute path"),
        ("C:/Temp/secret.txt", "windows drive path"),
        ("dir//file.py", "unsafe path segment"),
        ("dir/./file.py", "unsafe path segment"),
    ]
    assert is_safe_manifest_path("scripts/rc_release_audit.py")
    assert not is_safe_manifest_path("../outside.txt")


def test_manifest_classification_mismatches_detects_tracked_new_drift() -> None:
    manifest = """
## Tracked Modified Candidate Files

```text
new_file.py
tracked_file.py
```

## New Candidate Files

```text
also_new.py
tracked_test.py
```
"""

    tracked_misclassified, new_misclassified = manifest_classification_mismatches(
        manifest,
        tracked_paths=["tracked_file.py", "tracked_test.py"],
        untracked_paths=["also_new.py", "new_file.py"],
    )

    assert tracked_misclassified == ["new_file.py"]
    assert new_misclassified == ["tracked_test.py"]


def test_secret_scan_ignores_placeholders_but_flags_realistic_tokens(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.py"
    fake_token = "ghp_" + "abcdefghijklmnopqrstuvwxyz1234567890"
    candidate.write_text(
        "\n".join(
            [
                "XAGENT_OPENAI_API_KEY=<required when enabled>",
                f"GITHUB_TOKEN={fake_token}",
            ]
        ),
        encoding="utf-8",
    )

    findings = scan_secret_findings(["candidate.py"], root=tmp_path)

    assert len(findings) == 1
    assert findings[0].path == "candidate.py"
    assert findings[0].line == 2


def test_secret_scan_ignores_code_identifier_token_assignments(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.py"
    candidate.write_text("token = _csrf_middleware.generate_csrf_token(session_id)", encoding="utf-8")

    assert scan_secret_findings(["candidate.py"], root=tmp_path) == []


def test_secret_scan_ignores_cli_flag_values(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.py"
    candidate.write_text('command = ["--github-execute-preflight"]\n', encoding="utf-8")

    assert scan_secret_findings(["candidate.py"], root=tmp_path) == []


def test_excluded_reference_scan_flags_creative_studio_leaks(tmp_path: Path) -> None:
    candidate = tmp_path / "main.py"
    candidate.write_text(
        "from backend.app.api.creative_studio import router as creative_studio_router\n",
        encoding="utf-8",
    )

    findings = scan_excluded_reference_findings(["main.py"], root=tmp_path)

    assert len(findings) == 1
    assert findings[0].excluded_area == "creative_studio"


def test_excluded_reference_scan_exempts_audit_self_tests(tmp_path: Path) -> None:
    audit_test = tmp_path / "test_rc_release_audit.py"
    audit_test.write_text("backend.app.api.creative_studio\n", encoding="utf-8")

    findings = scan_excluded_reference_findings(["tests/test_rc_release_audit.py"], root=tmp_path)

    assert findings == []


def test_local_path_scan_flags_user_runtime_paths(tmp_path: Path) -> None:
    candidate = tmp_path / "handoff.md"
    candidate.write_text(
        f"runtime={_windows_user_path('AppData', 'Local', 'xagent', 'venv')}\n",
        encoding="utf-8",
    )

    findings = scan_local_path_findings(["handoff.md"], root=tmp_path)

    assert len(findings) == 1
    assert findings[0].pattern == "windows_user_profile"


def test_file_hygiene_scan_flags_nul_bytes(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.py"
    candidate.write_bytes(b"print('ok')\x00\n")

    findings = scan_file_hygiene_findings(["candidate.py"], root=tmp_path)

    assert len(findings) == 1
    assert findings[0].kind == "nul_byte"
    assert findings[0].line == 0


def test_file_hygiene_scan_flags_trailing_whitespace(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.md"
    candidate.write_text("clean\nbad   \n", encoding="utf-8")

    findings = scan_file_hygiene_findings(["candidate.md"], root=tmp_path)

    assert len(findings) == 1
    assert findings[0].kind == "trailing_whitespace"
    assert findings[0].line == 2


def test_file_hygiene_scan_flags_merge_conflict_marker(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.py"
    candidate.write_text("<<<<<<< HEAD\nprint('bad')\n", encoding="utf-8")

    findings = scan_file_hygiene_findings(["candidate.py"], root=tmp_path)

    assert len(findings) == 1
    assert findings[0].kind == "merge_conflict_marker"
    assert findings[0].line == 1


def test_file_hygiene_scan_flags_utf8_decode_errors(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.md"
    candidate.write_bytes(b"\xff\xfe")

    findings = scan_file_hygiene_findings(["candidate.md"], root=tmp_path)

    assert len(findings) == 1
    assert findings[0].kind == "utf8_decode_error"
    assert findings[0].line == 0
