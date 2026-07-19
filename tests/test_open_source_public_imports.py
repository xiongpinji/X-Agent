from __future__ import annotations

import importlib

_LEGACY_OPEN_SOURCE = ".".join(("backend", "app", "core", "open_source"))
_PUBLIC_OPEN_SOURCE_API = ".".join(("backend", "app", "core", "open_source_api"))


def test_public_open_source_api_exports_are_available() -> None:
    module = importlib.import_module(_PUBLIC_OPEN_SOURCE_API)

    assert hasattr(module, "OpenSourceCandidateRecord")
    assert hasattr(module, "OpenSourceDiscoveryStore")
    assert hasattr(module, "build_default_open_source_store")


def test_legacy_open_source_module_is_not_public_entrypoint_for_new_code() -> None:
    legacy = importlib.import_module(_LEGACY_OPEN_SOURCE)
    public = importlib.import_module(_PUBLIC_OPEN_SOURCE_API)

    assert hasattr(public, "OpenSourceCandidateRecord")
    assert hasattr(public, "OpenSourceDiscoveryStore")
    assert legacy.__name__ == _LEGACY_OPEN_SOURCE
