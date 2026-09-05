from __future__ import annotations

import pytest

from backend.app.core.open_source_api import OpenSourceCandidateRecord, OpenSourceDiscoveryStore, build_default_open_source_store

pytestmark = pytest.mark.contracts


def test_open_source_api_exports_are_available() -> None:
    assert OpenSourceCandidateRecord is not None
    assert OpenSourceDiscoveryStore is not None
    assert build_default_open_source_store is not None
