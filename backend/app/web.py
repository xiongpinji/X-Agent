from __future__ import annotations

from pathlib import Path

from fastapi.responses import FileResponse


def build_index_response(frontend_dir: Path) -> FileResponse:
    return FileResponse(frontend_dir / "index.html")
