"""Qdrant Snapshot Manager — create/restore/list snapshots for disaster recovery.

Uses Qdrant's built-in snapshot REST API:
  - POST   /collections/{name}/snapshots          → create snapshot
  - GET    /collections/{name}/snapshots          → list snapshots
  - POST   /collections/{name}/snapshots/recover  → restore snapshot
  - DELETE /collections/{name}/snapshots/{snap}   → delete snapshot
  - GET    /collections                           → list all collections
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 120.0  # snapshot creation can be slow for large collections


class QdrantSnapshotError(Exception):
    """Raised when a Qdrant snapshot operation fails."""


class QdrantUnavailableError(QdrantSnapshotError):
    """Raised when Qdrant server is unreachable."""


class QdrantSnapshotManager:
    """Manage Qdrant collection snapshots for disaster recovery."""

    def __init__(self, qdrant_url: str, api_key: str = "") -> None:
        self._base_url = qdrant_url.rstrip("/")
        self._headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            self._headers["api-key"] = api_key

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._headers,
            timeout=_DEFAULT_TIMEOUT,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        """Perform an HTTP request against Qdrant, raising typed errors."""
        try:
            async with self._client() as client:
                resp = await client.request(method, path, **kwargs)
        except httpx.ConnectError as exc:
            raise QdrantUnavailableError(
                f"Cannot connect to Qdrant at {self._base_url}: {exc}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise QdrantUnavailableError(
                f"Qdrant request timed out: {exc}"
            ) from exc

        if resp.status_code >= 400:
            raise QdrantSnapshotError(
                f"Qdrant API error {resp.status_code}: {resp.text}"
            )
        return resp.json()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def create_snapshot(self, collection_name: str) -> dict:
        """Create a snapshot of a collection. Returns snapshot info."""
        data = await self._request("POST", f"/collections/{collection_name}/snapshots")
        result = data.get("result", data)
        logger.info("Created snapshot for collection '%s': %s", collection_name, result.get("name"))
        return {
            "collection": collection_name,
            "snapshot_name": result.get("name", ""),
            "creation_time": result.get("creation_time", ""),
            "size": result.get("size", 0),
            "checksum": result.get("checksum", ""),
        }

    async def list_snapshots(self, collection_name: str) -> list[dict]:
        """List available snapshots for a collection."""
        data = await self._request("GET", f"/collections/{collection_name}/snapshots")
        snapshots = data.get("result", [])
        return [
            {
                "name": s.get("name", ""),
                "creation_time": s.get("creation_time", ""),
                "size": s.get("size", 0),
                "checksum": s.get("checksum", ""),
            }
            for s in snapshots
        ]

    async def restore_snapshot(self, collection_name: str, snapshot_name: str) -> bool:
        """Restore a collection from a snapshot."""
        await self._request(
            "POST",
            f"/collections/{collection_name}/snapshots/recover",
            json={"location": snapshot_name},
        )
        logger.info("Restored collection '%s' from snapshot '%s'", collection_name, snapshot_name)
        return True

    async def delete_snapshot(self, collection_name: str, snapshot_name: str) -> bool:
        """Delete an old snapshot."""
        await self._request(
            "DELETE", f"/collections/{collection_name}/snapshots/{snapshot_name}"
        )
        logger.info("Deleted snapshot '%s' from collection '%s'", snapshot_name, collection_name)
        return True

    async def list_collections(self) -> list[str]:
        """List all collection names in the Qdrant instance."""
        data = await self._request("GET", "/collections")
        collections = data.get("result", {}).get("collections", [])
        return [c.get("name", "") for c in collections if c.get("name")]

    async def create_full_backup(self) -> dict:
        """Snapshot ALL collections. Returns summary."""
        collections = await self.list_collections()
        results: list[dict] = []
        errors: list[dict] = []

        for name in collections:
            try:
                info = await self.create_snapshot(name)
                results.append(info)
            except QdrantSnapshotError as exc:
                errors.append({"collection": name, "error": str(exc)})

        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "collections_backed_up": len(results),
            "collections_failed": len(errors),
            "snapshots": results,
            "errors": errors,
        }

    async def cleanup_old_snapshots(self, keep_latest: int = 5) -> int:
        """Remove old snapshots, keeping N most recent per collection.

        Returns the number of snapshots deleted.
        """
        collections = await self.list_collections()
        deleted_count = 0

        for name in collections:
            try:
                snapshots = await self.list_snapshots(name)
            except QdrantSnapshotError:
                continue

            # Sort by creation_time descending (newest first)
            snapshots.sort(key=lambda s: s.get("creation_time", ""), reverse=True)

            for old_snap in snapshots[keep_latest:]:
                try:
                    await self.delete_snapshot(name, old_snap["name"])
                    deleted_count += 1
                except QdrantSnapshotError as exc:
                    logger.warning(
                        "Failed to delete snapshot '%s' from '%s': %s",
                        old_snap["name"], name, exc,
                    )

        logger.info("Cleanup complete: deleted %d old snapshots", deleted_count)
        return deleted_count

    async def health_check(self) -> bool:
        """Check if Qdrant is reachable."""
        try:
            async with self._client() as client:
                resp = await client.get("/healthz")
                return resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False
