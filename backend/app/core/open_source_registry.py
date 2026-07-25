from __future__ import annotations

from backend.app.core.open_source_registry_java import MavenCentralOpenSourceProvider
from backend.app.core.open_source_registry_javascript import NpmRegistryOpenSourceProvider
from backend.app.core.open_source_registry_python import (
    PackageRegistryOpenSourceProvider,
    RubyGemsOpenSourceProvider,
)
from backend.app.core.open_source_registry_rust import CratesIoOpenSourceProvider

__all__ = [
    "CratesIoOpenSourceProvider",
    "MavenCentralOpenSourceProvider",
    "NpmRegistryOpenSourceProvider",
    "PackageRegistryOpenSourceProvider",
    "RubyGemsOpenSourceProvider",
]
