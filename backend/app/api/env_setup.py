"""Environment Setup Pipeline — Codex-style automated workspace preparation.

Given a repository URL (or local path), this module automates:
1. Clone / copy the repository into a sandbox workspace
2. Detect the project type and package manager
3. Install dependencies
4. Run a verification command (build/test/lint)

Exposed as an API so the frontend or CI can trigger environment provisioning
before an agent run.

Endpoints:
    POST /api/v1/env-setup          — Start environment setup
    GET  /api/v1/env-setup/{id}     — Get setup status/result
    GET  /api/v1/env-setup          — List recent setups
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/env-setup", tags=["env-setup"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


# ─── Models ────────────────────────────────────────────────────────────────────


class EnvSetupRequest(BaseModel):
    repo_url: str | None = Field(default=None, description="Git repo URL to clone (or local path)")
    branch: str | None = Field(default=None, description="Branch to checkout")
    workspace_name: str | None = Field(default=None, description="Custom workspace directory name")
    install_command: str | None = Field(default=None, description="Override install command")
    verify_command: str | None = Field(default=None, description="Override verification command")
    env_vars: dict[str, str] = Field(default_factory=dict, description="Extra env vars for setup")
    timeout_seconds: int = Field(default=300, ge=30, le=1800)


class SetupStep(BaseModel):
    name: str
    status: str = "pending"  # pending | running | success | failed | skipped
    output: str = ""
    duration_ms: float = 0


class EnvSetupRecord(BaseModel):
    id: str
    repo_url: str | None
    branch: str | None
    workspace_path: str
    status: str = "running"  # running | completed | failed
    project_type: str = "unknown"
    package_manager: str = "unknown"
    steps: list[SetupStep] = Field(default_factory=list)
    created_at: str
    completed_at: str | None = None
    error: str | None = None


# ─── Store ─────────────────────────────────────────────────────────────────────

_SETUPS: dict[str, EnvSetupRecord] = {}
_BASE_DIR = Path(os.environ.get("XAGENT_ENV_DIR", ".xagent_runtime/envs"))


# ─── Detection Logic ───────────────────────────────────────────────────────────

_PROJECT_MARKERS: list[tuple[str, str, str, str]] = [
    # (marker_file, project_type, package_manager, install_cmd)
    ("package-lock.json", "nodejs", "npm", "npm ci"),
    ("yarn.lock", "nodejs", "yarn", "yarn install --frozen-lockfile"),
    ("pnpm-lock.yaml", "nodejs", "pnpm", "pnpm install --frozen-lockfile"),
    ("bun.lockb", "nodejs", "bun", "bun install"),
    ("package.json", "nodejs", "npm", "npm install"),
    ("requirements.txt", "python", "pip", "pip install -r requirements.txt"),
    ("pyproject.toml", "python", "pip", "pip install -e ."),
    ("setup.py", "python", "pip", "pip install -e ."),
    ("Pipfile", "python", "pipenv", "pipenv install"),
    ("poetry.lock", "python", "poetry", "poetry install"),
    ("go.mod", "golang", "go", "go mod download"),
    ("Cargo.toml", "rust", "cargo", "cargo fetch"),
    ("Gemfile", "ruby", "bundler", "bundle install"),
    ("composer.json", "php", "composer", "composer install"),
    ("pom.xml", "java", "maven", "mvn dependency:resolve -q"),
    ("build.gradle", "java", "gradle", "gradle dependencies --quiet"),
    ("build.gradle.kts", "java", "gradle", "gradle dependencies --quiet"),
]

_VERIFY_COMMANDS: dict[str, str] = {
    "nodejs": "npm run build --if-present || echo 'no build script'",
    "python": "python -c \"import sys; print(f'Python {sys.version}')\"",
    "golang": "go build ./...",
    "rust": "cargo check",
    "ruby": "ruby -c Gemfile",
    "php": "php -l composer.json || true",
    "java": "mvn compile -q || gradle compileJava --quiet || true",
}


def _detect_project(workspace: Path) -> tuple[str, str, str]:
    """Detect project type, package manager, and install command."""
    for marker, ptype, pm, cmd in _PROJECT_MARKERS:
        if (workspace / marker).exists():
            return ptype, pm, cmd
    return "unknown", "unknown", ""


# ─── Pipeline Execution ────────────────────────────────────────────────────────


async def _run_cmd(cmd: str, cwd: str, env: dict[str, str] | None = None, timeout: int = 300) -> tuple[int, str]:
    """Run a shell command and return (returncode, combined_output)."""
    full_env = {**os.environ, **(env or {})}
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            cwd=cwd,
            env=full_env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        output = stdout.decode("utf-8", errors="replace")[:10000]
        return proc.returncode or 0, output
    except asyncio.TimeoutError:
        return -1, f"Command timed out after {timeout}s"
    except Exception as exc:
        return -1, str(exc)


async def _execute_setup(record: EnvSetupRecord, request: EnvSetupRequest) -> None:
    """Run the full setup pipeline asynchronously."""
    workspace = Path(record.workspace_path)
    env = request.env_vars or {}

    try:
        # Step 1: Clone / Copy
        step_clone = SetupStep(name="clone", status="running")
        record.steps.append(step_clone)
        t0 = time.time()

        if request.repo_url:
            repo_url = request.repo_url
            if os.path.isdir(repo_url):
                # Local path — copy
                if workspace.exists():
                    shutil.rmtree(workspace, ignore_errors=True)
                shutil.copytree(repo_url, workspace, dirs_exist_ok=True)
                step_clone.output = f"Copied local path: {repo_url}"
                step_clone.status = "success"
            else:
                # Git clone
                workspace.parent.mkdir(parents=True, exist_ok=True)
                branch_flag = f" --branch {request.branch}" if request.branch else ""
                rc, out = await _run_cmd(
                    f"git clone --depth 1{branch_flag} {repo_url} {workspace}",
                    cwd=str(workspace.parent),
                    env=env,
                    timeout=request.timeout_seconds,
                )
                step_clone.output = out
                step_clone.status = "success" if rc == 0 else "failed"
                if rc != 0:
                    record.status = "failed"
                    record.error = f"Clone failed: {out[:500]}"
                    step_clone.duration_ms = (time.time() - t0) * 1000
                    return
        else:
            workspace.mkdir(parents=True, exist_ok=True)
            step_clone.output = "No repo_url — using empty workspace"
            step_clone.status = "success"

        step_clone.duration_ms = (time.time() - t0) * 1000

        # Step 2: Detect project type
        step_detect = SetupStep(name="detect", status="running")
        record.steps.append(step_detect)
        t0 = time.time()

        ptype, pm, default_install = _detect_project(workspace)
        record.project_type = ptype
        record.package_manager = pm
        step_detect.output = f"type={ptype}, pm={pm}"
        step_detect.status = "success"
        step_detect.duration_ms = (time.time() - t0) * 1000

        # Step 3: Install dependencies
        install_cmd = request.install_command or default_install
        step_install = SetupStep(name="install", status="running")
        record.steps.append(step_install)
        t0 = time.time()

        if install_cmd:
            rc, out = await _run_cmd(install_cmd, cwd=str(workspace), env=env, timeout=request.timeout_seconds)
            step_install.output = out[:5000]
            step_install.status = "success" if rc == 0 else "failed"
            if rc != 0:
                record.status = "failed"
                record.error = f"Install failed: {out[:500]}"
                step_install.duration_ms = (time.time() - t0) * 1000
                return
        else:
            step_install.output = "No install command detected — skipped"
            step_install.status = "skipped"

        step_install.duration_ms = (time.time() - t0) * 1000

        # Step 4: Verify
        verify_cmd = request.verify_command or _VERIFY_COMMANDS.get(ptype, "")
        step_verify = SetupStep(name="verify", status="running")
        record.steps.append(step_verify)
        t0 = time.time()

        if verify_cmd:
            rc, out = await _run_cmd(verify_cmd, cwd=str(workspace), env=env, timeout=request.timeout_seconds)
            step_verify.output = out[:5000]
            step_verify.status = "success" if rc == 0 else "failed"
            if rc != 0:
                record.status = "failed"
                record.error = f"Verify failed: {out[:500]}"
                step_verify.duration_ms = (time.time() - t0) * 1000
                return
        else:
            step_verify.output = "No verify command — skipped"
            step_verify.status = "skipped"

        step_verify.duration_ms = (time.time() - t0) * 1000

        # Done
        record.status = "completed"
        record.completed_at = datetime.now(UTC).isoformat()

    except Exception as exc:
        record.status = "failed"
        record.error = str(exc)[:1000]
        record.completed_at = datetime.now(UTC).isoformat()
        logger.exception("Env setup failed for %s", record.id)


# ─── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("", status_code=201)
async def start_env_setup(body: EnvSetupRequest, principal: PrincipalDependency) -> dict[str, Any]:
    """Start an automated environment setup pipeline."""
    enforce_scope(principal, "agent:run")

    ws_name = body.workspace_name or f"env-{uuid4().hex[:8]}"
    workspace = _BASE_DIR / ws_name
    now = datetime.now(UTC).isoformat()

    record = EnvSetupRecord(
        id=str(uuid4()),
        repo_url=body.repo_url,
        branch=body.branch,
        workspace_path=str(workspace),
        status="running",
        created_at=now,
    )
    _SETUPS[record.id] = record

    # Run pipeline in background
    asyncio.create_task(_execute_setup(record, body))

    return {
        "id": record.id,
        "status": "running",
        "workspace_path": str(workspace),
        "created_at": now,
    }


@router.get("/{setup_id}")
async def get_env_setup(setup_id: str, principal: PrincipalDependency) -> dict[str, Any]:
    """Get environment setup status and results."""
    enforce_scope(principal, "agent:run")
    record = _SETUPS.get(setup_id)
    if not record:
        raise HTTPException(status_code=404, detail="Setup not found")
    return record.model_dump()


@router.get("")
async def list_env_setups(principal: PrincipalDependency) -> dict[str, Any]:
    """List recent environment setups."""
    enforce_scope(principal, "agent:run")
    items = sorted(_SETUPS.values(), key=lambda r: r.created_at, reverse=True)
    return {
        "setups": [
            {
                "id": r.id,
                "repo_url": r.repo_url,
                "status": r.status,
                "project_type": r.project_type,
                "package_manager": r.package_manager,
                "workspace_path": r.workspace_path,
                "created_at": r.created_at,
                "completed_at": r.completed_at,
            }
            for r in items[:30]
        ],
        "total": len(items),
    }
