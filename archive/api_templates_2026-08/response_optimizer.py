"""API response optimization for X-Agent.

Implements strategies for:
- Response compression (gzip)
- Fast JSON serialization
- Pagination and cursors
- Response streaming
"""

from __future__ import annotations

import gzip
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class PaginationParams:
    """Pagination parameters."""

    page: int = 1
    page_size: int = 20
    sort_by: str | None = None
    sort_order: str = "asc"

    def validate(self) -> None:
        """Validate pagination parameters."""
        if self.page < 1:
            raise ValueError("page must be >= 1")
        if self.page_size < 1 or self.page_size > 1000:
            raise ValueError("page_size must be between 1 and 1000")
        if self.sort_order not in ("asc", "desc"):
            raise ValueError("sort_order must be 'asc' or 'desc'")

    @property
    def offset(self) -> int:
        """Calculate offset for query."""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Get limit for query."""
        return self.page_size


@dataclass
class CursorPaginationParams:
    """Cursor-based pagination parameters."""

    cursor: str | None = None
    limit: int = 20
    sort_by: str | None = None
    sort_order: str = "asc"

    def validate(self) -> None:
        """Validate cursor pagination parameters."""
        if self.limit < 1 or self.limit > 1000:
            raise ValueError("limit must be between 1 and 1000")
        if self.sort_order not in ("asc", "desc"):
            raise ValueError("sort_order must be 'asc' or 'desc'")


@dataclass
class PaginatedResponse(Generic[T]):
    """Paginated response wrapper."""

    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int

    @classmethod
    def from_items(
        cls,
        items: list[T],
        total: int,
        page: int,
        page_size: int,
    ) -> PaginatedResponse[T]:
        """Create paginated response.

        Args:
            items: List of items
            total: Total number of items
            page: Current page
            page_size: Items per page

        Returns:
            Paginated response
        """
        total_pages = (total + page_size - 1) // page_size
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )


@dataclass
class CursorPaginatedResponse(Generic[T]):
    """Cursor-based paginated response."""

    items: list[T]
    next_cursor: str | None
    has_more: bool
    limit: int


class JSONSerializer:
    """Fast JSON serialization using orjson if available."""

    @staticmethod
    def serialize(obj: Any) -> str:
        """Serialize object to JSON.

        Args:
            obj: Object to serialize

        Returns:
            JSON string
        """
        if HAS_ORJSON:
            return orjson.dumps(obj).decode("utf-8")
        else:
            return json.dumps(obj, default=str)

    @staticmethod
    def deserialize(data: str) -> Any:
        """Deserialize JSON string.

        Args:
            data: JSON string

        Returns:
            Deserialized object
        """
        if HAS_ORJSON:
            return orjson.loads(data)
        else:
            return json.loads(data)


class ResponseCompressor:
    """Compresses responses using gzip."""

    @staticmethod
    def compress(data: str | bytes, level: int = 6) -> bytes:
        """Compress data using gzip.

        Args:
            data: Data to compress
            level: Compression level (1-9)

        Returns:
            Compressed data
        """
        if isinstance(data, str):
            data = data.encode("utf-8")

        return gzip.compress(data, compresslevel=level)

    @staticmethod
    def decompress(data: bytes) -> str:
        """Decompress gzip data.

        Args:
            data: Compressed data

        Returns:
            Decompressed string
        """
        return gzip.decompress(data).decode("utf-8")

    @staticmethod
    def should_compress(data: str | bytes, min_size: int = 1024) -> bool:
        """Check if data should be compressed.

        Args:
            data: Data to check
            min_size: Minimum size for compression

        Returns:
            True if data should be compressed
        """
        size = len(data.encode("utf-8")) if isinstance(data, str) else len(data)

        return size > min_size


class Paginator:
    """Handles offset-based pagination."""

    @staticmethod
    def paginate(
        items: list[T],
        params: PaginationParams,
    ) -> PaginatedResponse[T]:
        """Paginate items.

        Args:
            items: List of items to paginate
            params: Pagination parameters

        Returns:
            Paginated response
        """
        params.validate()

        total = len(items)
        start = params.offset
        end = start + params.limit

        paginated_items = items[start:end]

        return PaginatedResponse.from_items(
            items=paginated_items,
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    @staticmethod
    def paginate_query(
        query_fn: Callable[[int, int], tuple[list[T], int]],
        params: PaginationParams,
    ) -> PaginatedResponse[T]:
        """Paginate query results.

        Args:
            query_fn: Function that takes (offset, limit) and returns (items, total)
            params: Pagination parameters

        Returns:
            Paginated response
        """
        params.validate()

        items, total = query_fn(params.offset, params.limit)

        return PaginatedResponse.from_items(
            items=items,
            total=total,
            page=params.page,
            page_size=params.page_size,
        )


class CursorPaginator:
    """Handles cursor-based pagination for better performance."""

    @staticmethod
    def encode_cursor(value: Any) -> str:
        """Encode cursor value.

        Args:
            value: Value to encode

        Returns:
            Encoded cursor
        """
        import base64
        data = json.dumps(value, default=str).encode("utf-8")
        return base64.b64encode(data).decode("utf-8")

    @staticmethod
    def decode_cursor(cursor: str) -> Any:
        """Decode cursor value.

        Args:
            cursor: Encoded cursor

        Returns:
            Decoded value
        """
        import base64
        try:
            data = base64.b64decode(cursor.encode("utf-8"))
            return json.loads(data.decode("utf-8"))
        except Exception as e:
            logger.error(f"Failed to decode cursor: {e}")
            return None

    @staticmethod
    def paginate_query(
        query_fn: Callable[[Any, int], tuple[list[T], bool]],
        params: CursorPaginationParams,
    ) -> CursorPaginatedResponse[T]:
        """Paginate query results using cursor.

        Args:
            query_fn: Function that takes (cursor, limit) and returns (items, has_more)
            params: Cursor pagination parameters

        Returns:
            Cursor paginated response
        """
        params.validate()

        # Decode cursor if provided
        cursor_value = None
        if params.cursor:
            cursor_value = CursorPaginator.decode_cursor(params.cursor)

        # Query with limit + 1 to detect if there are more items
        items, has_more = query_fn(cursor_value, params.limit + 1)

        # If we got more items than limit, we have more pages
        if len(items) > params.limit:
            items = items[: params.limit]
            has_more = True
            # Encode next cursor from last item
            next_cursor = CursorPaginator.encode_cursor(items[-1])
        else:
            has_more = False
            next_cursor = None

        return CursorPaginatedResponse(
            items=items,
            next_cursor=next_cursor,
            has_more=has_more,
            limit=params.limit,
        )


class ResponseBuilder:
    """Builds optimized API responses."""

    @staticmethod
    def build_success_response(
        data: Any,
        message: str = "Success",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build success response.

        Args:
            data: Response data
            message: Success message
            metadata: Optional metadata

        Returns:
            Response dictionary
        """
        response = {
            "success": True,
            "message": message,
            "data": data,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        if metadata:
            response["metadata"] = metadata

        return response

    @staticmethod
    def build_error_response(
        error: str,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build error response.

        Args:
            error: Error message
            code: Error code
            details: Optional error details

        Returns:
            Response dictionary
        """
        response = {
            "success": False,
            "error": error,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        if code:
            response["code"] = code

        if details:
            response["details"] = details

        return response

    @staticmethod
    def build_paginated_response(
        paginated: PaginatedResponse[T],
        message: str = "Success",
    ) -> dict[str, Any]:
        """Build paginated response.

        Args:
            paginated: Paginated response
            message: Success message

        Returns:
            Response dictionary
        """
        return {
            "success": True,
            "message": message,
            "data": paginated.items,
            "pagination": {
                "page": paginated.page,
                "page_size": paginated.page_size,
                "total": paginated.total,
                "total_pages": paginated.total_pages,
            },
            "timestamp": datetime.now(UTC).isoformat(),
        }

    @staticmethod
    def build_cursor_paginated_response(
        paginated: CursorPaginatedResponse[T],
        message: str = "Success",
    ) -> dict[str, Any]:
        """Build cursor paginated response.

        Args:
            paginated: Cursor paginated response
            message: Success message

        Returns:
            Response dictionary
        """
        return {
            "success": True,
            "message": message,
            "data": paginated.items,
            "pagination": {
                "next_cursor": paginated.next_cursor,
                "has_more": paginated.has_more,
                "limit": paginated.limit,
            },
            "timestamp": datetime.now(UTC).isoformat(),
        }
