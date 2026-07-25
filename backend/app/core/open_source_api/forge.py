from __future__ import annotations

from backend.app.core.open_source_forge_archive import (
    FossilOpenSourceProvider,
    LaunchpadOpenSourceProvider,
)
from backend.app.core.open_source_forge_githublike import (
    BitbucketOpenSourceProvider,
    CodebergOpenSourceProvider,
    GitLabOpenSourceProvider,
    SourceHutOpenSourceProvider,
)
from backend.app.core.open_source_forge_hosting import (
    ForgejoOpenSourceProvider,
    GiteaOpenSourceProvider,
    SavannahOpenSourceProvider,
)
from backend.app.core.open_source_forge_mirror import SourceForgeOpenSourceProvider

__all__ = [
    "BitbucketOpenSourceProvider",
    "CodebergOpenSourceProvider",
    "ForgejoOpenSourceProvider",
    "FossilOpenSourceProvider",
    "GitLabOpenSourceProvider",
    "GiteaOpenSourceProvider",
    "LaunchpadOpenSourceProvider",
    "SavannahOpenSourceProvider",
    "SourceForgeOpenSourceProvider",
    "SourceHutOpenSourceProvider",
]
