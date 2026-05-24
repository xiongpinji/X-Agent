from __future__ import annotations

from backend.app.core.open_source_base import OpenSourceCandidateRecord, OpenSourceDiscoveryReport, OpenSourceProvider, OpenSourceStatus, StaticOpenSourceProvider
from backend.app.core.open_source_forge_archive import FossilOpenSourceProvider, LaunchpadOpenSourceProvider
from backend.app.core.open_source_forge_githublike import BitbucketOpenSourceProvider, CodebergOpenSourceProvider, GitLabOpenSourceProvider, SourceHutOpenSourceProvider
from backend.app.core.open_source_forge_hosting import ForgejoOpenSourceProvider, GiteaOpenSourceProvider, SavannahOpenSourceProvider
from backend.app.core.open_source_forge_mirror import SourceForgeOpenSourceProvider
from backend.app.core.open_source_registry_java import MavenCentralOpenSourceProvider
from backend.app.core.open_source_registry_javascript import NpmRegistryOpenSourceProvider
from backend.app.core.open_source_registry_python import PackageRegistryOpenSourceProvider, RubyGemsOpenSourceProvider
from backend.app.core.open_source_registry_rust import CratesIoOpenSourceProvider
from backend.app.core.open_source_store import OpenSourceDiscoveryStore
from backend.app.core.open_source_wiring import build_default_open_source_store

__all__ = [
    "OpenSourceCandidateRecord",
    "OpenSourceDiscoveryReport",
    "OpenSourceDiscoveryStore",
    "OpenSourceProvider",
    "OpenSourceStatus",
    "StaticOpenSourceProvider",
    "PackageRegistryOpenSourceProvider",
    "NpmRegistryOpenSourceProvider",
    "MavenCentralOpenSourceProvider",
    "CratesIoOpenSourceProvider",
    "RubyGemsOpenSourceProvider",
    "BitbucketOpenSourceProvider",
    "CodebergOpenSourceProvider",
    "ForgejoOpenSourceProvider",
    "FossilOpenSourceProvider",
    "GiteaOpenSourceProvider",
    "GitLabOpenSourceProvider",
    "LaunchpadOpenSourceProvider",
    "SavannahOpenSourceProvider",
    "SourceForgeOpenSourceProvider",
    "SourceHutOpenSourceProvider",
    "build_default_open_source_store",
]
