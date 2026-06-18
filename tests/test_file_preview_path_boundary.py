"""Path-boundary tests for the file preview / download / listing API.

Verifies that every file endpoint confines access to the workspace
allowlist and rejects the three escape classes with HTTP 403:
* absolute-path escape (e.g. /etc/passwd, project source outside workspaces)
* ``..`` traversal escape
* symlink escape

Also exercises the reusable WorkspaceBoundary tool directly.
"""

from __future__ import annotations

import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api import file_preview
from backend.app.api.errors import XAgentAPIError, xagent_api_error_handler
from backend.app.core.path_security import (
    PathBoundaryError,
    WorkspaceBoundary,
)
from backend.app.core.security import Principal, ROLE_SCOPES
from backend.app.dependencies import get_current_principal


def _principal(role: str = "developer") -> Principal:
    return Principal(
        tenant_id="tenant-a",
        user_id=f"{role}-user",
        role=role,
        scopes=list(ROLE_SCOPES.get(role, [])),
        authenticated=True,
    )


@pytest.fixture
def workspace_root(tmp_path, monkeypatch):
    """Create an isolated workspaces root and point the API allowlist at it."""
    root = tmp_path / "workspaces"
    root.mkdir()
    # get_workspace_roots() derives from settings.PROJECT_ROOT; redirect it.
    import backend.app.settings as settings_module

    monkeypatch.setattr(settings_module, "PROJECT_ROOT", tmp_path)
    return root


@pytest.fixture
def client(workspace_root):
    app = FastAPI()
    app.include_router(file_preview.router)
    app.add_exception_handler(XAgentAPIError, xagent_api_error_handler)
    app.dependency_overrides[get_current_principal] = lambda: _principal("developer")
    return TestClient(app)


# --- happy path: file inside workspace is previewable -----------------------


def test_preview_file_inside_workspace_ok(client, workspace_root) -> None:
    target = workspace_root / "hello.txt"
    target.write_text("hello world\n", encoding="utf-8")

    resp = client.get(f"/api/v1/files/preview/{target}")
    assert resp.status_code == 200
    assert resp.json()["content"].startswith("hello world")


# --- absolute-path escape ---------------------------------------------------


def test_preview_absolute_path_escape_forbidden(client, tmp_path) -> None:
    # A real, existing file outside the workspace root must still be refused.
    secret = tmp_path / "secret_outside.txt"
    secret.write_text("top secret", encoding="utf-8")

    resp = client.get(f"/api/v1/files/preview/{secret}")
    assert resp.status_code == 403


def test_metadata_absolute_path_escape_forbidden(client, tmp_path) -> None:
    secret = tmp_path / "secret_outside.txt"
    secret.write_text("top secret", encoding="utf-8")

    resp = client.get(f"/api/v1/files/metadata/{secret}")
    assert resp.status_code == 403


def test_download_absolute_path_escape_forbidden(client, tmp_path) -> None:
    secret = tmp_path / "secret_outside.txt"
    secret.write_text("top secret", encoding="utf-8")

    resp = client.get(f"/api/v1/files/download/{secret}")
    assert resp.status_code == 403


def test_directory_listing_escape_forbidden(client, tmp_path) -> None:
    outside_dir = tmp_path / "outside_dir"
    outside_dir.mkdir()

    resp = client.get(f"/api/v1/files/directory/{outside_dir}")
    assert resp.status_code == 403


def test_code_preview_escape_forbidden(client, tmp_path) -> None:
    secret = tmp_path / "secret.py"
    secret.write_text("SECRET = 1\n", encoding="utf-8")

    resp = client.get(f"/api/v1/files/code/{secret}")
    assert resp.status_code == 403


# --- .. traversal escape ----------------------------------------------------


def test_dot_dot_traversal_forbidden(client, workspace_root, tmp_path) -> None:
    # Place a secret one level above the workspace root, then try to climb to it.
    secret = tmp_path / "escape_target.txt"
    secret.write_text("nope", encoding="utf-8")

    traversal = f"{workspace_root}/../escape_target.txt"
    resp = client.get(f"/api/v1/files/preview/{traversal}")
    assert resp.status_code == 403


# --- symlink escape ---------------------------------------------------------


@pytest.mark.skipif(sys.platform == "win32", reason="symlink creation needs privilege on Windows")
def test_symlink_escape_forbidden(client, workspace_root, tmp_path) -> None:
    secret = tmp_path / "real_secret.txt"
    secret.write_text("classified", encoding="utf-8")

    link = workspace_root / "link_to_secret.txt"
    link.symlink_to(secret)

    resp = client.get(f"/api/v1/files/preview/{link}")
    assert resp.status_code == 403


# --- direct WorkspaceBoundary unit tests ------------------------------------


def test_boundary_allows_nested_path(tmp_path) -> None:
    root = tmp_path / "ws"
    root.mkdir()
    nested = root / "a" / "b.txt"
    nested.parent.mkdir(parents=True)
    nested.write_text("x", encoding="utf-8")

    boundary = WorkspaceBoundary([root])
    assert boundary.resolve_strict(nested) == nested.resolve()
    assert boundary.is_allowed(nested) is True


def test_boundary_rejects_sibling_prefix(tmp_path) -> None:
    # A sibling dir sharing a name prefix must NOT be considered inside.
    root = tmp_path / "ws"
    root.mkdir()
    evil = tmp_path / "ws-evil"
    evil.mkdir()

    boundary = WorkspaceBoundary([root])
    assert boundary.is_allowed(evil / "f.txt") is False
    with pytest.raises(PathBoundaryError):
        boundary.resolve_strict(evil / "f.txt")


def test_boundary_empty_allowlist_denies_everything(tmp_path) -> None:
    boundary = WorkspaceBoundary([])
    with pytest.raises(PathBoundaryError):
        boundary.resolve_strict(tmp_path / "anything")


def test_boundary_rejects_dot_dot(tmp_path) -> None:
    root = tmp_path / "ws"
    root.mkdir()
    boundary = WorkspaceBoundary([root])
    with pytest.raises(PathBoundaryError):
        boundary.resolve_strict(f"{root}/../outside.txt")
