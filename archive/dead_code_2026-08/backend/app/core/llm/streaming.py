"""Streaming response handling for LLM outputs."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class StreamChunk:
    """A chunk of streamed response."""

    content: str
    chunk_type: str = "text"  # "text", "tool_call", "metadata"
    timestamp: datetime = field(default_factory=datetime.now)
    token_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StreamingResponse:
    """Manages a streaming LLM response."""

    model: str
    provider: str
    request_id: str
    start_time: datetime = field(default_factory=datetime.now)
    chunks: list[StreamChunk] = field(default_factory=list)
    is_complete: bool = False
    error: str | None = None
    total_tokens: int = 0

    def add_chunk(self, chunk: StreamChunk) -> None:
        """Add a chunk to the response."""
        self.chunks.append(chunk)
        self.total_tokens += chunk.token_count

    def get_full_content(self) -> str:
        """Get complete response content."""
        return "".join(c.content for c in self.chunks if c.chunk_type == "text")

    def get_elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        return (datetime.now() - self.start_time).total_seconds() * 1000

    def mark_complete(self) -> None:
        """Mark response as complete."""
        self.is_complete = True

    def mark_error(self, error: str) -> None:
        """Mark response as errored."""
        self.error = error
        self.is_complete = True


class StreamManager:
    """Manage streaming responses from LLMs."""

    def __init__(self, buffer_size: int = 100):
        """Initialize stream manager."""
        self.buffer_size = buffer_size
        self.active_streams: dict[str, StreamingResponse] = {}
        self._chunk_callbacks: list[Callable[[StreamChunk], None]] = []

    def create_stream(
        self,
        model: str,
        provider: str,
        request_id: str,
    ) -> StreamingResponse:
        """Create a new streaming response."""
        stream = StreamingResponse(
            model=model,
            provider=provider,
            request_id=request_id,
        )
        self.active_streams[request_id] = stream
        return stream

    def get_stream(self, request_id: str) -> StreamingResponse | None:
        """Get an active stream."""
        return self.active_streams.get(request_id)

    def add_chunk(self, request_id: str, chunk: StreamChunk) -> None:
        """Add a chunk to a stream."""
        stream = self.get_stream(request_id)
        if stream:
            stream.add_chunk(chunk)
            self._notify_callbacks(chunk)

    def complete_stream(self, request_id: str) -> StreamingResponse | None:
        """Mark a stream as complete and return it."""
        stream = self.get_stream(request_id)
        if stream:
            stream.mark_complete()
            # Keep stream for a bit for retrieval
            return stream
        return None

    def error_stream(self, request_id: str, error: str) -> StreamingResponse | None:
        """Mark a stream as errored."""
        stream = self.get_stream(request_id)
        if stream:
            stream.mark_error(error)
            return stream
        return None

    def register_chunk_callback(self, callback: Callable[[StreamChunk], None]) -> None:
        """Register a callback for each chunk."""
        self._chunk_callbacks.append(callback)

    def _notify_callbacks(self, chunk: StreamChunk) -> None:
        """Notify all registered callbacks."""
        for callback in self._chunk_callbacks:
            try:
                callback(chunk)
            except Exception:
                pass  # Ignore callback errors

    async def stream_to_sse(
        self,
        request_id: str,
        timeout_s: float = 300.0,
    ) -> AsyncIterator[str]:
        """Convert stream to Server-Sent Events format."""
        stream = self.get_stream(request_id)
        if not stream:
            yield f"data: {json.dumps({'error': 'Stream not found'})}\n\n"
            return

        last_chunk_index = 0
        start_time = datetime.now()

        while True:
            # Check timeout
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > timeout_s:
                yield f"data: {json.dumps({'error': 'Stream timeout'})}\n\n"
                break

            # Get new chunks
            if last_chunk_index < len(stream.chunks):
                for chunk in stream.chunks[last_chunk_index:]:
                    data = {
                        "type": chunk.chunk_type,
                        "content": chunk.content,
                        "tokens": chunk.token_count,
                    }
                    yield f"data: {json.dumps(data)}\n\n"
                last_chunk_index = len(stream.chunks)

            # Check if complete
            if stream.is_complete:
                if stream.error:
                    yield f"data: {json.dumps({'error': stream.error})}\n\n"
                else:
                    yield f"data: {json.dumps({'done': True, 'total_tokens': stream.total_tokens})}\n\n"
                break

            # Wait a bit before checking again
            await asyncio.sleep(0.1)

    async def stream_to_json_lines(
        self,
        request_id: str,
        timeout_s: float = 300.0,
    ) -> AsyncIterator[str]:
        """Convert stream to JSON Lines format."""
        stream = self.get_stream(request_id)
        if not stream:
            yield json.dumps({"error": "Stream not found"}) + "\n"
            return

        last_chunk_index = 0
        start_time = datetime.now()

        while True:
            # Check timeout
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > timeout_s:
                yield json.dumps({"error": "Stream timeout"}) + "\n"
                break

            # Get new chunks
            if last_chunk_index < len(stream.chunks):
                for chunk in stream.chunks[last_chunk_index:]:
                    data = {
                        "type": chunk.chunk_type,
                        "content": chunk.content,
                        "tokens": chunk.token_count,
                    }
                    yield json.dumps(data) + "\n"
                last_chunk_index = len(stream.chunks)

            # Check if complete
            if stream.is_complete:
                if stream.error:
                    yield json.dumps({"error": stream.error}) + "\n"
                else:
                    yield json.dumps({"done": True, "total_tokens": stream.total_tokens}) + "\n"
                break

            # Wait a bit before checking again
            await asyncio.sleep(0.1)

    def cleanup_old_streams(self, max_age_s: int = 3600) -> int:
        """Remove old completed streams."""
        now = datetime.now()
        to_remove = []

        for request_id, stream in self.active_streams.items():
            if stream.is_complete:
                age = (now - stream.start_time).total_seconds()
                if age > max_age_s:
                    to_remove.append(request_id)

        for request_id in to_remove:
            del self.active_streams[request_id]

        return len(to_remove)

    def get_stats(self) -> dict[str, Any]:
        """Get streaming statistics."""
        active_count = sum(1 for s in self.active_streams.values() if not s.is_complete)
        completed_count = sum(1 for s in self.active_streams.values() if s.is_complete)
        error_count = sum(1 for s in self.active_streams.values() if s.error)

        total_tokens = sum(s.total_tokens for s in self.active_streams.values())
        avg_latency = 0.0

        if self.active_streams:
            latencies = [s.get_elapsed_ms() for s in self.active_streams.values()]
            avg_latency = sum(latencies) / len(latencies)

        return {
            "active_streams": active_count,
            "completed_streams": completed_count,
            "error_streams": error_count,
            "total_tokens_streamed": total_tokens,
            "average_latency_ms": avg_latency,
        }
