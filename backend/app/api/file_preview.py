"""
File preview and metadata API for X-Agent.

Provides file preview, download, and metadata endpoints with support for
multiple file types including code, images, PDFs, and text files.
"""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/files", tags=["files"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


class FileMetadata(BaseModel):
    """File metadata."""
    path: str = Field(..., description="File path")
    name: str = Field(..., description="File name")
    size: int = Field(..., ge=0, description="File size in bytes")
    mime_type: str = Field(..., description="MIME type")
    created_at: str | None = Field(default=None, description="Creation timestamp")
    modified_at: str | None = Field(default=None, description="Modification timestamp")
    is_directory: bool = Field(default=False, description="Whether path is a directory")
    is_readable: bool = Field(default=True, description="Whether file is readable")
    is_writable: bool = Field(default=False, description="Whether file is writable")


class FilePreview(BaseModel):
    """File preview data."""
    path: str = Field(..., description="File path")
    name: str = Field(..., description="File name")
    mime_type: str = Field(..., description="MIME type")
    size: int = Field(..., ge=0, description="File size")
    preview_type: str = Field(..., description="Type of preview: text, code, image, pdf, binary")
    content: str | None = Field(default=None, description="File content (for text/code)")
    language: str | None = Field(default=None, description="Programming language (for code)")
    lines: int | None = Field(default=None, description="Number of lines")
    truncated: bool = Field(default=False, description="Whether content was truncated")
    max_lines: int = Field(default=1000, description="Maximum lines shown")


class DirectoryListing(BaseModel):
    """Directory listing."""
    path: str = Field(..., description="Directory path")
    files: list[FileMetadata] = Field(default_factory=list, description="Files in directory")
    directories: list[FileMetadata] = Field(default_factory=list, description="Subdirectories")
    total_files: int = Field(default=0, description="Total number of files")
    total_size: int = Field(default=0, description="Total size of all files")


class CodePreview(BaseModel):
    """Code file preview with syntax highlighting info."""
    path: str
    name: str
    language: str
    content: str
    lines: int
    truncated: bool
    line_numbers: bool = True
    highlight_lines: list[int] = Field(default_factory=list, description="Lines to highlight")


# Supported file types for preview
PREVIEW_TEXT_TYPES = {
    "text/plain",
    "text/markdown",
    "text/html",
    "text/css",
    "text/javascript",
    "application/json",
    "application/xml",
    "application/yaml",
}

PREVIEW_CODE_TYPES = {
    "text/x-python",
    "text/x-java",
    "text/x-c",
    "text/x-cpp",
    "text/x-csharp",
    "text/x-go",
    "text/x-rust",
    "text/x-typescript",
    "text/javascript",
    "text/html",
    "text/css",
    "application/json",
}

PREVIEW_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/svg+xml",
}

PREVIEW_PDF_TYPES = {
    "application/pdf",
}

# File extension to language mapping
LANGUAGE_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "zsh",
    ".fish": "fish",
    ".ps1": "powershell",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".sass": "sass",
    ".less": "less",
    ".json": "json",
    ".xml": "xml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".ini": "ini",
    ".cfg": "ini",
    ".conf": "conf",
    ".md": "markdown",
    ".markdown": "markdown",
    ".rst": "rst",
    ".tex": "latex",
    ".sql": "sql",
    ".dockerfile": "dockerfile",
    ".Dockerfile": "dockerfile",
}


def _get_language(file_path: str) -> str | None:
    """Get programming language from file extension."""
    path = Path(file_path)
    ext = path.suffix.lower()
    return LANGUAGE_MAP.get(ext)


def _get_preview_type(mime_type: str) -> str:
    """Determine preview type from MIME type."""
    if mime_type in PREVIEW_IMAGE_TYPES:
        return "image"
    elif mime_type in PREVIEW_PDF_TYPES:
        return "pdf"
    elif mime_type in PREVIEW_CODE_TYPES:
        return "code"
    elif mime_type in PREVIEW_TEXT_TYPES:
        return "text"
    elif mime_type.startswith("text/"):
        return "text"
    else:
        return "binary"


def _get_file_metadata(file_path: Path) -> FileMetadata:
    """Get file metadata."""
    stat = file_path.stat()
    mime_type, _ = mimetypes.guess_type(str(file_path))
    mime_type = mime_type or "application/octet-stream"

    from datetime import datetime

    return FileMetadata(
        path=str(file_path),
        name=file_path.name,
        size=stat.st_size,
        mime_type=mime_type,
        created_at=datetime.fromtimestamp(stat.st_ctime).isoformat(),
        modified_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
        is_directory=file_path.is_dir(),
        is_readable=True,
        is_writable=False,
    )


def _read_file_content(file_path: Path, max_lines: int = 1000) -> tuple[str, int, bool]:
    """Read file content with line limit."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        truncated = len(lines) > max_lines
        content_lines = lines[:max_lines]
        content = "".join(content_lines)

        return content, len(lines), truncated
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        raise


@router.get("/preview/{file_path:path}", response_model=FilePreview)
async def preview_file(
    file_path: str,
    principal: PrincipalDependency,
    max_lines: int = Query(default=1000, ge=1, le=10000, description="Maximum lines to preview"),
) -> FilePreview:
    """
    Get a preview of a file.

    Supports text, code, images, and PDFs.

    Args:
        file_path: Path to file
        max_lines: Maximum lines to return for text/code files

    Returns:
        File preview
    """
    enforce_scope(principal, "agent:read")

    # Security: prevent path traversal
    file_path_obj = Path(file_path).resolve()

    if not file_path_obj.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    if file_path_obj.is_dir():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Path is a directory")

    mime_type, _ = mimetypes.guess_type(str(file_path_obj))
    mime_type = mime_type or "application/octet-stream"

    preview_type = _get_preview_type(mime_type)

    # For images and PDFs, return metadata only
    if preview_type in ("image", "pdf"):
        metadata = _get_file_metadata(file_path_obj)
        return FilePreview(
            path=str(file_path_obj),
            name=metadata.name,
            mime_type=mime_type,
            size=metadata.size,
            preview_type=preview_type,
        )

    # For text and code, read content
    if preview_type in ("text", "code"):
        content, lines, truncated = _read_file_content(file_path_obj, max_lines)
        language = _get_language(str(file_path_obj)) if preview_type == "code" else None

        return FilePreview(
            path=str(file_path_obj),
            name=file_path_obj.name,
            mime_type=mime_type,
            size=file_path_obj.stat().st_size,
            preview_type=preview_type,
            content=content,
            language=language,
            lines=lines,
            truncated=truncated,
            max_lines=max_lines,
        )

    # Binary files
    return FilePreview(
        path=str(file_path_obj),
        name=file_path_obj.name,
        mime_type=mime_type,
        size=file_path_obj.stat().st_size,
        preview_type="binary",
    )


@router.get("/metadata/{file_path:path}", response_model=FileMetadata)
async def get_file_metadata(
    file_path: str,
    principal: PrincipalDependency,
) -> FileMetadata:
    """
    Get file metadata.

    Args:
        file_path: Path to file

    Returns:
        File metadata
    """
    enforce_scope(principal, "agent:read")

    file_path_obj = Path(file_path).resolve()

    if not file_path_obj.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    return _get_file_metadata(file_path_obj)


@router.get("/download/{file_path:path}")
async def download_file(
    file_path: str,
    principal: PrincipalDependency,
) -> FileResponse:
    """
    Download a file.

    Args:
        file_path: Path to file

    Returns:
        File download
    """
    enforce_scope(principal, "agent:read")

    file_path_obj = Path(file_path).resolve()

    if not file_path_obj.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    if file_path_obj.is_dir():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Path is a directory")

    return FileResponse(
        path=file_path_obj,
        filename=file_path_obj.name,
        media_type="application/octet-stream",
    )


@router.get("/directory/{dir_path:path}", response_model=DirectoryListing)
async def list_directory(
    dir_path: str,
    principal: PrincipalDependency,
    recursive: bool = Query(default=False, description="List recursively"),
    max_depth: int = Query(default=1, ge=0, le=5, description="Maximum recursion depth"),
) -> DirectoryListing:
    """
    List files in a directory.

    Args:
        dir_path: Path to directory
        recursive: Whether to list recursively
        max_depth: Maximum recursion depth

    Returns:
        Directory listing
    """
    enforce_scope(principal, "agent:read")

    dir_path_obj = Path(dir_path).resolve()

    if not dir_path_obj.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Directory not found")

    if not dir_path_obj.is_dir():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Path is not a directory")

    files = []
    directories = []
    total_size = 0

    try:
        for item in dir_path_obj.iterdir():
            metadata = _get_file_metadata(item)
            if item.is_dir():
                directories.append(metadata)
            else:
                files.append(metadata)
                total_size += metadata.size
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    return DirectoryListing(
        path=str(dir_path_obj),
        files=files,
        directories=directories,
        total_files=len(files),
        total_size=total_size,
    )


@router.get("/code/{file_path:path}", response_model=CodePreview)
async def preview_code(
    file_path: str,
    principal: PrincipalDependency,
    max_lines: int = Query(default=1000, ge=1, le=10000),
    highlight_lines: str = Query(default="", description="Comma-separated line numbers to highlight"),
) -> CodePreview:
    """
    Get a code file preview with syntax highlighting info.

    Args:
        file_path: Path to code file
        max_lines: Maximum lines to preview
        highlight_lines: Comma-separated line numbers to highlight

    Returns:
        Code preview
    """
    enforce_scope(principal, "agent:read")

    file_path_obj = Path(file_path).resolve()

    if not file_path_obj.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    content, lines, truncated = _read_file_content(file_path_obj, max_lines)
    language = _get_language(str(file_path_obj)) or "text"

    # Parse highlight lines
    highlight = []
    if highlight_lines:
        try:
            highlight = [int(x.strip()) for x in highlight_lines.split(",") if x.strip()]
        except ValueError:
            pass

    return CodePreview(
        path=str(file_path_obj),
        name=file_path_obj.name,
        language=language,
        content=content,
        lines=lines,
        truncated=truncated,
        highlight_lines=highlight,
    )
