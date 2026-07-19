from __future__ import annotations

from pathlib import Path

from fastapi.responses import FileResponse


def build_index_response(frontend_dir: Path) -> FileResponse:
    return FileResponse(frontend_dir / "index.html")


# ---------------------------------------------------------------------------
# ASGI app re-export for backward compatibility.
#
# The canonical ASGI entrypoint is ``backend.app.main:app``. Historically some
# docs/scripts referenced ``backend.app.web:app`` (which never existed here and
# would fail to start). Re-exporting keeps those commands working while
# ``main`` remains the single source of truth.
# Prefer ``uvicorn backend.app.main:app`` in new docs/scripts.
# ---------------------------------------------------------------------------
from backend.app.main import app  # noqa: E402,F401
