"""Externalized model profile loading for the LLM router (P1-08).

The model catalog used by smart routing and cost accounting lives in
``config/model_profiles.yaml`` instead of being hardcoded in
``selector.ModelSelector`` / ``TokenUsage.calculate_cost``.

Failure policy (no silent behavior):
- File missing  -> explicit degrade: log a warning and signal callers to use
  the selector's built-in defaults (``used_builtin_fallback=True``).
- File invalid  -> raise :class:`ModelProfileLoadError` with the precise
  location/field problem.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from backend.app.core.llm.selector import ModelProfile, ModelSelector, TaskType

logger = logging.getLogger(__name__)

# backend/app/core/llm/profiles.py -> project root is parents[4]
PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_PROFILES_PATH = PROJECT_ROOT / "config" / "model_profiles.yaml"

_REQUIRED_FIELDS = (
    "name",
    "provider",
    "cost_per_1k_input",
    "cost_per_1k_output",
    "latency_ms",
    "quality_score",
    "max_tokens",
)


class ModelProfileLoadError(RuntimeError):
    """Raised when the model profiles file exists but is malformed."""


@dataclass
class QuotaFileConfig:
    """Per-tenant / per-user quota overrides declared in the YAML file.

    Enablement and default limits come from environment variables
    (``XAGENT_LLM_QUOTA_*``, see ``llm_settings.py``); the file only carries
    override maps, which are configuration data by nature.
    """

    tenant_overrides: dict[str, int] = field(default_factory=dict)
    user_overrides: dict[str, int] = field(default_factory=dict)


@dataclass
class ModelProfileConfig:
    """Result of loading the profiles file."""

    models: list[ModelProfile]
    quota: QuotaFileConfig
    source_path: Path | None
    used_builtin_fallback: bool = False


def _parse_task_type(value: Any, *, model_name: str) -> TaskType:
    try:
        return TaskType(str(value))
    except ValueError as exc:
        valid = ", ".join(t.value for t in TaskType)
        raise ModelProfileLoadError(
            f"model '{model_name}' has unknown supported_task '{value}'; "
            f"valid values: {valid}"
        ) from exc


def _parse_model_entry(entry: Any, index: int) -> ModelProfile:
    if not isinstance(entry, dict):
        raise ModelProfileLoadError(
            f"models[{index}] must be a mapping, got {type(entry).__name__}"
        )
    missing = [key for key in _REQUIRED_FIELDS if key not in entry]
    if missing:
        raise ModelProfileLoadError(
            f"models[{index}] is missing required fields: {', '.join(missing)}"
        )

    name = str(entry["name"])
    try:
        supported = {
            _parse_task_type(item, model_name=name)
            for item in (entry.get("supported_tasks") or [])
        }
        return ModelProfile(
            name=name,
            provider=str(entry["provider"]),
            cost_per_1k_input=float(entry["cost_per_1k_input"]),
            cost_per_1k_output=float(entry["cost_per_1k_output"]),
            latency_ms=float(entry["latency_ms"]),
            quality_score=float(entry["quality_score"]),
            max_tokens=int(entry["max_tokens"]),
            supported_tasks=supported,
            availability=float(entry.get("availability", 0.99)),
            rate_limit_rpm=int(entry.get("rate_limit_rpm", 3500)),
            rate_limit_tpm=int(entry.get("rate_limit_tpm", 90000)),
        )
    except (TypeError, ValueError) as exc:
        raise ModelProfileLoadError(
            f"models[{index}] ('{name}') has a non-numeric or invalid field: {exc}"
        ) from exc


def _parse_quota_section(raw: Any) -> QuotaFileConfig:
    if raw is None:
        return QuotaFileConfig()
    if not isinstance(raw, dict):
        raise ModelProfileLoadError(
            f"'quota' section must be a mapping, got {type(raw).__name__}"
        )

    def _overrides(key: str) -> dict[str, int]:
        value = raw.get(key) or {}
        if not isinstance(value, dict):
            raise ModelProfileLoadError(f"quota.{key} must be a mapping of id -> token limit")
        result: dict[str, int] = {}
        for ident, limit in value.items():
            try:
                result[str(ident)] = int(limit)
            except (TypeError, ValueError) as exc:
                raise ModelProfileLoadError(
                    f"quota.{key}['{ident}'] is not an integer token limit: {limit!r}"
                ) from exc
        return result

    return QuotaFileConfig(
        tenant_overrides=_overrides("tenant_overrides"),
        user_overrides=_overrides("user_overrides"),
    )


def load_model_profiles(path: str | Path | None = None) -> ModelProfileConfig:
    """Load model profiles from YAML.

    Args:
        path: Explicit file path. ``None`` uses ``config/model_profiles.yaml``.

    Returns:
        ModelProfileConfig. When the file does not exist, ``models`` is empty
        and ``used_builtin_fallback`` is True so callers can explicitly fall
        back to ``ModelSelector``'s built-in catalog (a warning is logged).
    """
    profiles_path = Path(path) if path else DEFAULT_PROFILES_PATH
    if not profiles_path.exists():
        logger.warning(
            "Model profiles file %s not found; using ModelSelector built-in "
            "defaults (explicit degrade).",
            profiles_path,
        )
        return ModelProfileConfig(
            models=[],
            quota=QuotaFileConfig(),
            source_path=None,
            used_builtin_fallback=True,
        )

    try:
        raw = yaml.safe_load(profiles_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ModelProfileLoadError(
            f"Invalid YAML in {profiles_path}: {exc}"
        ) from exc

    if not isinstance(raw, dict):
        raise ModelProfileLoadError(
            f"{profiles_path} must contain a top-level mapping, "
            f"got {type(raw).__name__}"
        )

    raw_models = raw.get("models")
    if not isinstance(raw_models, list) or not raw_models:
        raise ModelProfileLoadError(
            f"{profiles_path} must define a non-empty 'models' list"
        )

    models = [_parse_model_entry(entry, i) for i, entry in enumerate(raw_models)]
    names = [m.name for m in models]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        raise ModelProfileLoadError(
            f"{profiles_path} declares duplicate model names: {', '.join(duplicates)}"
        )

    return ModelProfileConfig(
        models=models,
        quota=_parse_quota_section(raw.get("quota")),
        source_path=profiles_path,
    )


def build_selector(config: ModelProfileConfig) -> ModelSelector:
    """Build a ModelSelector from a loaded config.

    Falls back to the selector's built-in catalog when the file was missing
    (explicit degrade already logged by :func:`load_model_profiles`).
    """
    if config.used_builtin_fallback or not config.models:
        return ModelSelector()
    return ModelSelector(profiles=config.models)


def pricing_table_from_profiles(config: ModelProfileConfig) -> dict[str, dict[str, float]]:
    """Derive the TokenUsage pricing table from loaded profiles."""
    return {
        m.name: {"prompt": m.cost_per_1k_input, "completion": m.cost_per_1k_output}
        for m in config.models
    }
