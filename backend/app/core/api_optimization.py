"""
API Response Optimization Module.

Implements response optimization techniques:
- Response compression (gzip)
- Efficient serialization
- Pagination
- Selective field loading
- Async operations
"""

from __future__ import annotations

import gzip
import io
import json
import logging
from typing import Any, Callable, TypeVar

from fastapi import Request, Response
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ResponseCompressor:
    """Compresses API responses using gzip."""

    MIN_COMPRESSION_SIZE = 1024  # Only compress responses > 1KB

    @staticmethod
    def should_compress(response_body: bytes, accept_encoding: str | None) -> bool:
        """Check if response should be compressed."""
        if not accept_encoding or "gzip" not in accept_encoding:
            return False
        return len(response_body) > ResponseCompressor.MIN_COMPRESSION_SIZE

    @staticmethod
    def compress(data: bytes) -> bytes:
        """Compress data using gzip."""
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb") as f:
            f.write(data)
        return buf.getvalue()

    @staticmethod
    async def compress_response(
        response: Response,
        request: Request,
    ) -> Response:
        """Compress response if applicable."""
        accept_encoding = request.headers.get("accept-encoding", "")

        if isinstance(response, StreamingResponse):
            return response

        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        if ResponseCompressor.should_compress(body, accept_encoding):
            compressed_body = ResponseCompressor.compress(body)
            response = Response(
                content=compressed_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )
            response.headers["content-encoding"] = "gzip"
            response.headers["content-length"] = str(len(compressed_body))

        return response


class EfficientSerializer:
    """Provides efficient JSON serialization."""

    @staticmethod
    def serialize(obj: Any, exclude_none: bool = True) -> str:
        """Serialize object to JSON efficiently."""
        return json.dumps(
            obj,
            default=str,
            separators=(",", ":"),  # Compact separators
            ensure_ascii=False,
        )

    @staticmethod
    def serialize_bytes(obj: Any, exclude_none: bool = True) -> bytes:
        """Serialize object to JSON bytes."""
        return EfficientSerializer.serialize(obj, exclude_none).encode("utf-8")

    @staticmethod
    def select_fields(obj: dict[str, Any], fields: list[str] | None) -> dict[str, Any]:
        """Select only specified fields from object."""
        if not fields:
            return obj
        return {k: v for k, v in obj.items() if k in fields}


class PaginationHelper:
    """Handles pagination for large result sets."""

    @staticmethod
    def paginate(
        items: list[T],
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """Paginate items."""
        total = len(items)
        total_pages = (total + page_size - 1) // page_size
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size

        return {
            "items": items[start_idx:end_idx],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
        }

    @staticmethod
    def cursor_paginate(
        items: list[dict[str, Any]],
        cursor: str | None = None,
        limit: int = 20,
        cursor_field: str = "id",
    ) -> dict[str, Any]:
        """Cursor-based pagination for better performance."""
        if cursor:
            # Find starting position
            start_idx = 0
            for i, item in enumerate(items):
                if item.get(cursor_field) == cursor:
                    start_idx = i + 1
                    break
        else:
            start_idx = 0

        paginated_items = items[start_idx : start_idx + limit]
        next_cursor = None

        if paginated_items and start_idx + limit < len(items):
            next_cursor = paginated_items[-1].get(cursor_field)

        return {
            "items": paginated_items,
            "pagination": {
                "cursor": cursor,
                "next_cursor": next_cursor,
                "limit": limit,
                "has_more": next_cursor is not None,
            },
        }


class ResponseOptimizer:
    """Optimizes API responses."""

    @staticmethod
    def build_optimized_response(
        data: Any,
        include_fields: list[str] | None = None,
        compress: bool = True,
        paginate: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """Build optimized response."""
        # Select fields if specified
        if include_fields and isinstance(data, dict):
            data = EfficientSerializer.select_fields(data, include_fields)
        elif include_fields and isinstance(data, list) and data and isinstance(data[0], dict):
            data = [EfficientSerializer.select_fields(item, include_fields) for item in data]

        # Paginate if needed
        if paginate and isinstance(data, list):
            return PaginationHelper.paginate(data, page, page_size)

        return {
            "data": data,
            "meta": {
                "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
                "compressed": compress,
            },
        }

    @staticmethod
    def build_list_response(
        items: list[Any],
        total: int | None = None,
        page: int = 1,
        page_size: int = 20,
        include_fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """Build optimized list response."""
        # Select fields
        if include_fields:
            items = [
                EfficientSerializer.select_fields(item, include_fields)
                if isinstance(item, dict)
                else item
                for item in items
            ]

        return {
            "items": items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total or len(items),
                "total_pages": (total or len(items) + page_size - 1) // page_size,
            },
        }


class AsyncOperationOptimizer:
    """Optimizes async operations."""

    @staticmethod
    async def gather_with_limit(
        coros: list[Any],
        limit: int = 10,
    ) -> list[Any]:
        """Execute coroutines with concurrency limit."""
        import asyncio

        semaphore = asyncio.Semaphore(limit)

        async def bounded_coro(coro: Any) -> Any:
            async with semaphore:
                return await coro

        return await asyncio.gather(*[bounded_coro(coro) for coro in coros])

    @staticmethod
    async def batch_async_operations(
        operations: list[Callable],
        batch_size: int = 10,
    ) -> list[Any]:
        """Execute async operations in batches."""
        import asyncio

        results = []
        for i in range(0, len(operations), batch_size):
            batch = operations[i : i + batch_size]
            batch_results = await asyncio.gather(*[op() for op in batch])
            results.extend(batch_results)

        return results
