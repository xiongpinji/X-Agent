"""Unified pagination support for X-Agent API endpoints.

Supports both offset-based and cursor-based pagination with consistent metadata.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Standard pagination parameters for offset-based pagination."""

    limit: int = Field(default=50, ge=1, le=1000, description="Number of items per page")
    offset: int = Field(default=0, ge=0, description="Number of items to skip")


class CursorPaginationParams(BaseModel):
    """Standard pagination parameters for cursor-based pagination."""

    limit: int = Field(default=50, ge=1, le=1000, description="Number of items per page")
    cursor: str | None = Field(default=None, description="Cursor for next page")


class PaginationMetadata(BaseModel):
    """Metadata for paginated responses."""

    total: int = Field(description="Total number of items")
    limit: int = Field(description="Items per page")
    offset: int = Field(description="Current offset")
    has_more: bool = Field(description="Whether more items exist")


class CursorPaginationMetadata(BaseModel):
    """Metadata for cursor-based paginated responses."""

    limit: int = Field(description="Items per page")
    cursor: str | None = Field(description="Cursor for next page")
    has_more: bool = Field(description="Whether more items exist")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""

    data: list[T] = Field(description="Items in this page")
    pagination: PaginationMetadata = Field(description="Pagination metadata")


class CursorPaginatedResponse(BaseModel, Generic[T]):
    """Generic cursor-based paginated response wrapper."""

    data: list[T] = Field(description="Items in this page")
    pagination: CursorPaginationMetadata = Field(description="Pagination metadata")


def apply_pagination(
    items: list[T],
    limit: int,
    offset: int,
) -> tuple[list[T], PaginationMetadata]:
    """Apply offset-based pagination to a list of items.

    Args:
        items: List of items to paginate
        limit: Number of items per page
        offset: Number of items to skip

    Returns:
        Tuple of (paginated_items, metadata)
    """
    total = len(items)
    paginated = items[offset : offset + limit]
    has_more = offset + limit < total

    metadata = PaginationMetadata(
        total=total,
        limit=limit,
        offset=offset,
        has_more=has_more,
    )

    return paginated, metadata


def apply_cursor_pagination(
    items: list[T],
    limit: int,
    cursor: str | None = None,
    cursor_key: str = "id",
) -> tuple[list[T], CursorPaginationMetadata]:
    """Apply cursor-based pagination to a list of items.

    Args:
        items: List of items to paginate (should be sorted)
        limit: Number of items per page
        cursor: Cursor from previous response
        cursor_key: Key to use for cursor (default: "id")

    Returns:
        Tuple of (paginated_items, metadata)
    """
    start_idx = 0

    if cursor:
        # Find the item matching the cursor
        for idx, item in enumerate(items):
            item_dict = item.model_dump() if hasattr(item, "model_dump") else item
            if str(item_dict.get(cursor_key)) == cursor:
                start_idx = idx + 1
                break

    paginated = items[start_idx : start_idx + limit]
    has_more = start_idx + limit < len(items)

    next_cursor = None
    if paginated and has_more:
        last_item = paginated[-1]
        last_dict = last_item.model_dump() if hasattr(last_item, "model_dump") else last_item
        next_cursor = str(last_dict.get(cursor_key))

    metadata = CursorPaginationMetadata(
        limit=limit,
        cursor=next_cursor,
        has_more=has_more,
    )

    return paginated, metadata
