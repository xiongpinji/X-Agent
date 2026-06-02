"""Hooks configuration loading.

Mirrors the dataclass + JSON pattern of ``backend/app/core/mcp/config.py``.
Configuration lives in ``.xagent/hooks.json`` (the directory the CLI
``init project`` command already creates).

Two hook flavours can be declared:
    - ``command`` hooks run an external program; the :class:`HookContext` is
      delivered as JSON on stdin and the program's stdout (JSON) / exit code
      determines the decision. (Execution is implemented by the executor
      module; this file only models the declaration.)
    - ``python`` hooks reference an importable dotted path resolving to a
      :class:`~backend.app.core.hooks.types.Hook`-compatible callable/factory.

Example ``hooks.json``::

    {
      "hooks": [
        {
          "name": "block-prod-writes",
          "type": "command",
          "events": ["pre_tool_use"],
          "command": ["python", ".xagent/hooks/guard.py"],
          "tool_matcher": "write_file|apply_text_patch",
          "priority": 10,
          "timeout_seconds": 5.0,
          "enabled": true
        },
        {
          "name": "audit-logger",
          "type": "python",
          "events": ["post_tool_use"],
          "target": "mypkg.hooks:AuditHook",
          "priority": 50,
          "enabled": true
        }
      ]
    }
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from backend.app.core.hooks.types import HookEvent

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_RELPATH = ".xagent/hooks.json"

#: Allowed values for ``HookDefinition.type``.
_VALID_TYPES = {"command", "python"}


@dataclass
class HookDefinition:
    """Declarative description of one hook loaded from configuration.

    Attributes:
        name: Unique identifier used in logs and audit records.
        type: ``"command"`` (subprocess) or ``"python"`` (in-process import).
        events: Hook events this definition subscribes to.
        command: Argv list for ``command`` hooks (never a shell string, to
            avoid injection). Required when ``type == "command"``.
        target: Dotted import path ``"module:attr"`` for ``python`` hooks.
            Required when ``type == "python"``.
        tool_matcher: Optional regex matched against ``tool_name``; when set,
            the hook only fires for matching tools.
        priority: Lower runs first. Defaults to 100.
        timeout_seconds: Max runtime for ``command`` hooks.
        enabled: When False the definition is skipped at load time.
    """

    name: str
    type: str
    events: list[str] = field(default_factory=list)
    command: list[str] | None = None
    target: str | None = None
    tool_matcher: str | None = None
    priority: int = 100
    timeout_seconds: float = 5.0
    enabled: bool = True

    def event_enums(self) -> list[HookEvent]:
        """Return ``events`` as :class:`HookEvent` values, skipping unknowns."""
        resolved: list[HookEvent] = []
        for raw in self.events:
            try:
                resolved.append(HookEvent(raw))
            except ValueError:
                logger.warning("Unknown hook event %r in hook %r", raw, self.name)
        return resolved

    def validate(self) -> list[str]:
        """Return a list of validation errors (empty when valid)."""
        errors: list[str] = []
        if not self.name:
            errors.append("hook missing 'name'")
        if self.type not in _VALID_TYPES:
            errors.append(f"hook {self.name!r}: invalid type {self.type!r}")
        if not self.events:
            errors.append(f"hook {self.name!r}: no events declared")
        if not self.event_enums():
            errors.append(f"hook {self.name!r}: no valid events resolved")
        if self.type == "command":
            if not self.command:
                errors.append(f"hook {self.name!r}: command type requires 'command'")
            elif not isinstance(self.command, list):
                errors.append(f"hook {self.name!r}: 'command' must be a list (argv)")
        if self.type == "python" and not self.target:
            errors.append(f"hook {self.name!r}: python type requires 'target'")
        if self.timeout_seconds <= 0:
            errors.append(f"hook {self.name!r}: timeout_seconds must be > 0")
        return errors


class HooksConfig:
    """Loads, validates, and serialises hook definitions from JSON.

    Args:
        config_path: Path to ``hooks.json``. When omitted, callers typically
            pass the project-relative :data:`DEFAULT_CONFIG_RELPATH`.
    """

    def __init__(self, config_path: str | Path | None = None) -> None:
        self.config_path: Path | None = Path(config_path) if config_path else None
        self.hooks: list[HookDefinition] = []
        if self.config_path and self.config_path.exists():
            self.load_from_file()

    def load_from_file(self) -> None:
        """Load and parse the configuration file if it exists."""
        if not self.config_path or not self.config_path.exists():
            logger.warning("Hooks configuration file not found: %s", self.config_path)
            return
        try:
            with open(self.config_path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Failed to load hooks configuration: %s", exc)
            return

        self.hooks = []
        for entry in data.get("hooks", []):
            if not isinstance(entry, dict):
                logger.warning("Skipping non-object hook entry: %r", entry)
                continue
            definition = HookDefinition(
                name=entry.get("name", ""),
                type=entry.get("type", ""),
                events=list(entry.get("events", [])),
                command=entry.get("command"),
                target=entry.get("target"),
                tool_matcher=entry.get("tool_matcher"),
                priority=int(entry.get("priority", 100)),
                timeout_seconds=float(entry.get("timeout_seconds", 5.0)),
                enabled=bool(entry.get("enabled", True)),
            )
            self.hooks.append(definition)
        logger.info(
            "Loaded %d hook definition(s) from %s", len(self.hooks), self.config_path
        )

    def save_to_file(self, path: str | Path | None = None) -> None:
        """Serialise definitions back to JSON."""
        save_path = Path(path) if path else self.config_path
        if not save_path:
            logger.warning("No hooks configuration path specified")
            return
        try:
            payload = {"hooks": [asdict(h) for h in self.hooks]}
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
            logger.info("Hooks configuration saved to %s", save_path)
        except OSError as exc:
            logger.error("Failed to save hooks configuration: %s", exc)

    def enabled_hooks(self) -> list[HookDefinition]:
        """Return only the definitions whose ``enabled`` flag is True."""
        return [h for h in self.hooks if h.enabled]

    def validate(self) -> tuple[bool, list[str]]:
        """Validate all definitions.

        Returns:
            ``(is_valid, errors)``. Also flags duplicate hook names.
        """
        errors: list[str] = []
        seen: set[str] = set()
        for hook in self.hooks:
            errors.extend(hook.validate())
            if hook.name in seen:
                errors.append(f"duplicate hook name: {hook.name!r}")
            seen.add(hook.name)
        return len(errors) == 0, errors

    def to_dict(self) -> dict[str, Any]:
        """Return the configuration as a plain dict."""
        return {"hooks": [asdict(h) for h in self.hooks]}
