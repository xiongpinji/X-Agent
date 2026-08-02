"""Track D2 tests: one-command install scripts (install.sh / install.ps1).

Covers:
- script existence at repo root
- bash/PowerShell syntax validity
- idempotency logic (venv reuse / skip-install decision / .env guard)

These tests NEVER run a real installation: the installer functions are
exercised against stub venvs in tmp directories only.
"""

from __future__ import annotations

import shutil
import subprocess
import stat
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SH = REPO_ROOT / "install.sh"
INSTALL_PS1 = REPO_ROOT / "install.ps1"

BASH = shutil.which("bash")
POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")


def _run_bash(script: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [BASH, "-c", script],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def _source_lib(script_body: str) -> str:
    """Source install.sh in lib-only mode, then run the given body."""
    return (
        "export XAGENT_INSTALL_LIB_ONLY=1; "
        f'source "{INSTALL_SH}"; '
        f"{script_body}"
    )


def _make_stub_python(venv: Path, import_ok: bool) -> Path:
    """Create a fake venv python that 'imports backend' successfully or not."""
    scripts = venv / "Scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    stub = scripts / "python.exe"
    rc = "0" if import_ok else "1"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        'if [[ "$*" == *"import backend.app.settings"* ]]; then\n'
        f"    exit {rc}\n"
        "fi\n"
        'if [[ "$*" == *"--version"* ]]; then\n'
        '    echo "Python 3.13.0"\n'
        "    exit 0\n"
        "fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return stub


class TestScriptExistence:
    def test_install_sh_exists(self):
        assert INSTALL_SH.is_file(), "install.sh missing at repo root"

    def test_install_ps1_exists(self):
        assert INSTALL_PS1.is_file(), "install.ps1 missing at repo root"

    @pytest.mark.skipif(BASH is None, reason="bash not available")
    def test_install_sh_bash_syntax_valid(self):
        result = subprocess.run(
            [BASH, "-n", str(INSTALL_SH)], capture_output=True, text=True, check=False
        )
        assert result.returncode == 0, result.stderr

    @pytest.mark.skipif(POWERSHELL is None, reason="powershell not available")
    def test_install_ps1_powershell_syntax_valid(self):
        # Parse-only check via the PowerShell parser (no execution).
        ps_script = (
            "$errs = $null; "
            f"[System.Management.Automation.Language.Parser]::ParseFile('{INSTALL_PS1}', "
            "[ref]$null, [ref]$errs) | Out-Null; "
            "if ($errs.Count -gt 0) { $errs | ForEach-Object { Write-Host $_.Message }; exit 1 }"
        )
        result = subprocess.run(
            [POWERSHELL, "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(BASH is None, reason="bash not available")
class TestInstallShIdempotency:
    """Idempotency logic of install.sh against stub venvs (no real install)."""

    def test_skip_install_when_venv_usable(self, tmp_path):
        _make_stub_python(tmp_path / "venv", import_ok=True)
        xagent = tmp_path / "venv" / "Scripts" / "xagent.exe"
        xagent.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        xagent.chmod(0o755)

        result = _run_bash(_source_lib("should_skip_install"), cwd=tmp_path)
        assert result.returncode == 0, result.stderr

    def test_no_skip_without_xagent_entrypoint(self, tmp_path):
        _make_stub_python(tmp_path / "venv", import_ok=True)
        # No xagent.exe present -> must reinstall to repair the entry point.
        result = _run_bash(_source_lib("should_skip_install"), cwd=tmp_path)
        assert result.returncode != 0

    def test_no_skip_when_backend_not_importable(self, tmp_path):
        _make_stub_python(tmp_path / "venv", import_ok=False)
        xagent = tmp_path / "venv" / "Scripts" / "xagent.exe"
        xagent.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        xagent.chmod(0o755)

        result = _run_bash(_source_lib("should_skip_install"), cwd=tmp_path)
        assert result.returncode != 0

    def test_no_skip_without_venv(self, tmp_path):
        result = _run_bash(_source_lib("should_skip_install"), cwd=tmp_path)
        assert result.returncode != 0

    def test_env_file_created_from_template(self, tmp_path):
        (tmp_path / ".env.development").write_text("XAGENT_ENVIRONMENT=development\n", encoding="utf-8")
        result = _run_bash(_source_lib("ensure_env_file"), cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        assert (tmp_path / ".env").read_text(encoding="utf-8") == "XAGENT_ENVIRONMENT=development\n"

    def test_env_file_never_overwritten(self, tmp_path):
        (tmp_path / ".env").write_text("CUSTOM=1\n", encoding="utf-8")
        (tmp_path / ".env.development").write_text("XAGENT_ENVIRONMENT=development\n", encoding="utf-8")
        result = _run_bash(_source_lib("ensure_env_file"), cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        # Existing .env must be preserved verbatim (idempotent re-run).
        assert (tmp_path / ".env").read_text(encoding="utf-8") == "CUSTOM=1\n"

    def test_env_file_missing_template_is_warning_not_error(self, tmp_path):
        result = _run_bash(_source_lib("ensure_env_file"), cwd=tmp_path)
        assert result.returncode == 0, result.stderr
        assert not (tmp_path / ".env").exists()

    def test_find_system_python_returns_current_interpreter(self, tmp_path):
        # The CI/dev machine running this test has Python >= 3.11 on PATH.
        result = _run_bash(_source_lib("find_system_python"), cwd=tmp_path)
        assert result.returncode == 0
        assert result.stdout.strip(), "find_system_python returned nothing"

    def test_real_repo_venv_takes_reuse_path(self):
        """The repo's real venv must satisfy the skip-install condition.

        This is the idempotency guarantee behind the实测 requirement: a
        second `bash install.sh` must NOT reinstall the whole venv.
        """
        if not (REPO_ROOT / "venv" / "Scripts" / "python.exe").exists():
            pytest.skip("repo venv not present")
        result = _run_bash(_source_lib("should_skip_install"), cwd=REPO_ROOT)
        assert result.returncode == 0, (
            "repo venv should be reusable (backend importable + xagent entry)"
        )


class TestInstallPs1IdempotencyMarkers:
    """Structural checks on install.ps1 (executed for real only on Windows)."""

    def test_ps1_has_skip_install_guard(self):
        content = INSTALL_PS1.read_text(encoding="utf-8")
        assert "Test-ShouldSkipInstall" in content
        assert "Test-BackendImportable" in content
        assert "Get-VenvXagent" in content

    def test_ps1_env_guard_never_overwrites(self):
        content = INSTALL_PS1.read_text(encoding="utf-8")
        assert 'if (Test-Path $EnvFile)' in content
        assert "Copy-Item $EnvTemplate $EnvFile" in content

    def test_ps1_runs_doctor_as_final_step(self):
        content = INSTALL_PS1.read_text(encoding="utf-8")
        assert "-m cli.main doctor" in content

    def test_ps1_checks_python_311(self):
        content = INSTALL_PS1.read_text(encoding="utf-8")
        assert "$MinMajor = 3" in content and "$MinMinor = 11" in content
