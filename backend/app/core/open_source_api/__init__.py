from __future__ import annotations

from backend.app.core.open_source_api.forge import BitbucketOpenSourceProvider, CodebergOpenSourceProvider, ForgejoOpenSourceProvider, FossilOpenSourceProvider, GiteaOpenSourceProvider, GitLabOpenSourceProvider, LaunchpadOpenSourceProvider, SavannahOpenSourceProvider, SourceForgeOpenSourceProvider, SourceHutOpenSourceProvider
from backend.app.core.open_source_api.model import OpenSourceCandidateRecord, OpenSourceDiscoveryReport, OpenSourceDiscoveryStore, OpenSourceProvider, OpenSourceStatus, StaticOpenSourceProvider
from backend.app.core.open_source_api.registry import CratesIoOpenSourceProvider, MavenCentralOpenSourceProvider, NpmRegistryOpenSourceProvider, PackageRegistryOpenSourceProvider, RubyGemsOpenSourceProvider
from backend.app.core.open_source_api.wiring import build_default_open_source_store

__all__ = ["OpenSourceCandidateRecord", "OpenSourceDiscoveryReport", "OpenSourceDiscoveryStore", "OpenSourceProvider", "OpenSourceStatus", "StaticOpenSourceProvider", "PackageRegistryOpenSourceProvider", "NpmRegistryOpenSourceProvider", "MavenCentralOpenSourceProvider", "CratesIoOpenSourceProvider", "RubyGemsOpenSourceProvider", "BitbucketOpenSourceProvider", "CodebergOpenSourceProvider", "ForgejoOpenSourceProvider", "FossilOpenSourceProvider", "GiteaOpenSourceProvider", "GitLabOpenSourceProvider", "LaunchpadOpenSourceProvider", "SavannahOpenSourceProvider", "SourceForgeOpenSourceProvider", "SourceHutOpenSourceProvider", "build_default_open_source_store"]
