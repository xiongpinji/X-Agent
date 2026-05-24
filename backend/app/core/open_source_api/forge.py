from __future__ import annotations

from backend.app.core.open_source_forge_githublike import BitbucketOpenSourceProvider, CodebergOpenSourceProvider, GitLabOpenSourceProvider, SourceHutOpenSourceProvider
from backend.app.core.open_source_forge_archive import FossilOpenSourceProvider, LaunchpadOpenSourceProvider
from backend.app.core.open_source_forge_mirror import SourceForgeOpenSourceProvider
from backend.app.core.open_source_forge_hosting import ForgejoOpenSourceProvider, GiteaOpenSourceProvider, SavannahOpenSourceProvider

__all__ = [
    "BitbucketOpenSourceProvider",
    "CodebergOpenSourceProvider",
    "GitLabOpenSourceProvider",
    "SourceHutOpenSourceProvider",
    "FossilOpenSourceProvider",
    "LaunchpadOpenSourceProvider",
    "SourceForgeOpenSourceProvider",
    "ForgejoOpenSourceProvider",
    "GiteaOpenSourceProvider",
    "SavannahOpenSourceProvider",
]
