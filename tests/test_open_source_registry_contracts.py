from __future__ import annotations

import pytest

from backend.app.core.open_source_registry import CratesIoOpenSourceProvider, MavenCentralOpenSourceProvider, NpmRegistryOpenSourceProvider, PackageRegistryOpenSourceProvider, RubyGemsOpenSourceProvider

pytestmark = pytest.mark.contracts


def test_registry_imports_available() -> None:
    providers = [CratesIoOpenSourceProvider(), MavenCentralOpenSourceProvider(), NpmRegistryOpenSourceProvider(), PackageRegistryOpenSourceProvider(), RubyGemsOpenSourceProvider()]
    assert len({provider.name for provider in providers}) == 5
