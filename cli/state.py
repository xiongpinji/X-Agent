"""Shared CLI runtime state.

Holds the active CLIConfig so that command modules can access it without
importing cli.main. This breaks the circular import between cli.main
(which mounts command apps) and cli.commands.* (which need the config).

Both `python -m cli.main` and the `xagent` console entry point share this
single module instance, so state set by the main callback is visible to all
subcommands.
"""

from __future__ import annotations

from cli.config import CLIConfig

# Global state for CLI context
_current_config: CLIConfig | None = None


def get_current_config() -> CLIConfig:
    """Get current CLI configuration.

    Returns:
        Current CLIConfig instance

    Raises:
        RuntimeError: If config not initialized
    """
    if _current_config is None:
        raise RuntimeError("CLI config not initialized")
    return _current_config


def set_current_config(config: CLIConfig) -> None:
    """Set current CLI configuration.

    Args:
        config: CLIConfig instance to set
    """
    global _current_config
    _current_config = config


def apply_mode_override(mode: str | None) -> CLIConfig:
    """Apply a per-command ``--mode`` override to the active config.

    ``--mode`` is a global option on the main callback and therefore must
    appear *before* the subcommand (``xagent --mode local agent run ...``).
    Codex-style CLIs accept it anywhere, so subcommands may also declare a
    local ``--mode`` option and funnel it through this helper.

    Args:
        mode: 'http', 'local', or None (no override).

    Returns:
        The active (possibly updated) CLIConfig.

    Raises:
        ValueError: If mode is not 'http' or 'local'.
    """
    config = get_current_config()
    if mode is None:
        return config
    if mode not in ("http", "local"):
        raise ValueError(f"Invalid mode: {mode!r} (expected 'http' or 'local')")
    config = config.model_copy(update={"mode": mode})
    set_current_config(config)
    return config
