"""Unit tests for Qdrant snapshot manager and API endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.core.qdrant_snapshot import (
    QdrantSnapshotError,
    QdrantSnapshotManager,
    QdrantUnavailableError,
)

# ---------------------------------------------------------------------------
# QdrantSnapshotManager unit tests (mocked HTTP)
# ---------------------------------------------------------------------------


class TestQdrantSnapshotManager:
    """Test QdrantSnapshotManager with mocked httpx responses."""

    def _make_manager(self) -> QdrantSnapshotManager:
        return QdrantSnapshotManager(qdrant_url="http://localhost:6333", api_key="test-key")

    @pytest.mark.asyncio
    async def test_create_snapshot_success(self):
        manager = self._make_manager()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {
                "name": "memories-2026-07-24.snapshot",
                "creation_time": "2026-07-24T10:00:00Z",
                "size": 1024000,
                "checksum": "abc123",
            }
        }

        with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=mock_response):
            result = await manager.create_snapshot("memories")

        assert result["collection"] == "memories"
        assert result["snapshot_name"] == "memories-2026-07-24.snapshot"
        assert result["size"] == 1024000

    @pytest.mark.asyncio
    async def test_list_snapshots_success(self):
        manager = self._make_manager()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": [
                {"name": "snap1.snapshot", "creation_time": "2026-07-23T10:00:00Z", "size": 100, "checksum": "a"},
                {"name": "snap2.snapshot", "creation_time": "2026-07-24T10:00:00Z", "size": 200, "checksum": "b"},
            ]
        }

        with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=mock_response):
            result = await manager.list_snapshots("memories")

        assert len(result) == 2
        assert result[0]["name"] == "snap1.snapshot"

    @pytest.mark.asyncio
    async def test_restore_snapshot_success(self):
        manager = self._make_manager()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": True}

        with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=mock_response):
            result = await manager.restore_snapshot("memories", "snap1.snapshot")

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_snapshot_success(self):
        manager = self._make_manager()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": True}

        with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=mock_response):
            result = await manager.delete_snapshot("memories", "old.snapshot")

        assert result is True

    @pytest.mark.asyncio
    async def test_create_full_backup(self):
        manager = self._make_manager()

        collections_resp = MagicMock()
        collections_resp.status_code = 200
        collections_resp.json.return_value = {
            "result": {"collections": [{"name": "col_a"}, {"name": "col_b"}]}
        }

        snapshot_resp = MagicMock()
        snapshot_resp.status_code = 200
        snapshot_resp.json.return_value = {
            "result": {"name": "snap.snapshot", "creation_time": "2026-07-24T10:00:00Z", "size": 500, "checksum": "x"}
        }

        call_count = {"n": 0}

        async def mock_request(method, path, **kwargs):
            call_count["n"] += 1
            if path == "/collections":
                return collections_resp
            return snapshot_resp

        with patch("httpx.AsyncClient.request", side_effect=mock_request):
            result = await manager.create_full_backup()

        assert result["collections_backed_up"] == 2
        assert result["collections_failed"] == 0
        assert len(result["snapshots"]) == 2

    @pytest.mark.asyncio
    async def test_cleanup_old_snapshots(self):
        manager = self._make_manager()

        collections_resp = MagicMock()
        collections_resp.status_code = 200
        collections_resp.json.return_value = {
            "result": {"collections": [{"name": "col_a"}]}
        }

        snapshots_resp = MagicMock()
        snapshots_resp.status_code = 200
        snapshots_resp.json.return_value = {
            "result": [
                {"name": f"snap{i}.snapshot", "creation_time": f"2026-07-{20+i:02d}T10:00:00Z", "size": 100, "checksum": "c"}
                for i in range(8)
            ]
        }

        delete_resp = MagicMock()
        delete_resp.status_code = 200
        delete_resp.json.return_value = {"result": True}

        async def mock_request(method, path, **kwargs):
            if path == "/collections":
                return collections_resp
            if method == "DELETE":
                return delete_resp
            return snapshots_resp

        with patch("httpx.AsyncClient.request", side_effect=mock_request):
            deleted = await manager.cleanup_old_snapshots(keep_latest=5)

        assert deleted == 3  # 8 - 5 = 3 deleted

    @pytest.mark.asyncio
    async def test_unavailable_raises(self):
        import httpx as _httpx

        manager = self._make_manager()

        with (
            patch(
                "httpx.AsyncClient.request",
                side_effect=_httpx.ConnectError("Connection refused"),
            ),
            pytest.raises(QdrantUnavailableError),
        ):
            await manager.create_snapshot("memories")

    @pytest.mark.asyncio
    async def test_api_error_raises(self):
        manager = self._make_manager()
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Collection not found"

        with (
            patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=mock_response),
            pytest.raises(QdrantSnapshotError, match="404"),
        ):
            await manager.create_snapshot("nonexistent")


# ---------------------------------------------------------------------------
# API endpoint tests (mocked manager + settings)
# ---------------------------------------------------------------------------


class TestQdrantBackupAPI:
    """Test API endpoints with mocked snapshot manager."""

    @pytest.mark.asyncio
    async def test_snapshot_disabled_returns_503(self):
        """When feature is disabled, endpoints return 503."""
        from fastapi import HTTPException

        from backend.app.api.backup_qdrant import _ensure_enabled

        mock_settings = MagicMock()
        mock_settings.qdrant_snapshot_enabled = False

        with patch("backend.app.api.backup_qdrant.get_settings", return_value=mock_settings):
            with pytest.raises(HTTPException) as exc_info:
                _ensure_enabled()
            assert exc_info.value.status_code == 503
