"""X-Agent CLI package.

Provides command-line interface for X-Agent framework with support for both
HTTP-based remote API calls and local direct module imports.
"""

from __future__ import annotations


def _resolve_version() -> str:
    """Resolve the X-Agent version.

    ``pyproject.toml`` is the single source of truth for the repository
    version, so when the CLI runs from a source checkout (a ``pyproject.toml``
    next to this package) it always wins — installed distribution metadata may
    be stale (e.g. an older ``x-agent-core`` still present in the venv).
    Outside a source checkout, fall back to ``importlib.metadata``.
    """
    try:
        import tomllib
        from pathlib import Path

        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
        if pyproject.is_file():
            with pyproject.open("rb") as fh:
                return str(tomllib.load(fh)["project"]["version"])
    except Exception:
        pass
    try:
        from importlib.metadata import PackageNotFoundError, version

        try:
            return version("x-agent-core")
        except PackageNotFoundError:
            pass
    except Exception:
        pass
    return "0.0.0+unknown"


__version__ = _resolve_version()
__all__ = ["__version__"]
