from __future__ import annotations

from backend.app.core.open_source_base import OpenSourceCandidateRecord, StaticOpenSourceProvider
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
from backend.app.core.open_source_registry_java import MavenCentralOpenSourceProvider
from backend.app.core.open_source_registry_javascript import NpmRegistryOpenSourceProvider
from backend.app.core.open_source_registry_python import (
    PackageRegistryOpenSourceProvider,
    RubyGemsOpenSourceProvider,
)
from backend.app.core.open_source_registry_rust import CratesIoOpenSourceProvider
from backend.app.core.open_source_store import OpenSourceDiscoveryStore


def build_default_open_source_store() -> OpenSourceDiscoveryStore:
    return OpenSourceDiscoveryStore(
        providers=[
            BitbucketOpenSourceProvider(),
            CodebergOpenSourceProvider(),
            ForgejoOpenSourceProvider(),
            FossilOpenSourceProvider(),
            GiteaOpenSourceProvider(),
            GitLabOpenSourceProvider(),
            LaunchpadOpenSourceProvider(),
            MavenCentralOpenSourceProvider(),
            NpmRegistryOpenSourceProvider(),
            PackageRegistryOpenSourceProvider(),
            RubyGemsOpenSourceProvider(),
            CratesIoOpenSourceProvider(),
            SourceForgeOpenSourceProvider(),
            SourceHutOpenSourceProvider(),
            SavannahOpenSourceProvider(),
            StaticOpenSourceProvider("docs", [
                OpenSourceCandidateRecord(name="Playwright Docs", source="docs", url="https://playwright.dev", license="Apache-2.0", summary="Reliable browser automation for web tasks.", score=0.92, reasons=["browser automation", "rpa"], tags=["browser", "automation", "web"]),
                OpenSourceCandidateRecord(name="Qdrant Docs", source="docs", url="https://qdrant.tech", license="Apache-2.0", summary="Vector database for memory retrieval and semantic search.", score=0.91, reasons=["memory", "vector search"], tags=["memory", "vector-db", "search"]),
            ]),
            StaticOpenSourceProvider("package-registry", [
                OpenSourceCandidateRecord(name="OpenAI SDK", source="package-registry", url="https://pypi.org/project/openai/", license="MIT", summary="Client SDK for model interactions and responses APIs.", score=0.9, reasons=["llm integration", "sdk"], tags=["llm", "sdk", "integration"]),
            ]),
        ]
    )
