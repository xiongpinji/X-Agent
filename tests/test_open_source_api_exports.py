from __future__ import annotations

import pytest

from backend.app.core.open_source_api import *  # noqa: F401,F403

pytestmark = pytest.mark.contracts


def test_open_source_api_wildcard_import_exports_core_symbols() -> None:
    assert OpenSourceCandidateRecord is not None
    assert OpenSourceDiscoveryStore is not None
    assert build_default_open_source_store is not None
