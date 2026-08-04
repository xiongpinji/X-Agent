"""LLM routing and optimization module for X-Agent.

This package historically coexisted with a ``backend/app/core/llm.py`` module of
the same name. Because a package shadows a same-named module on the import path,
the legacy backend classes (``LLMRouter`` and friends) became unreachable via
``from backend.app.core.llm import LLMRouter``. Those classes now live in
``backends.py`` inside this package and are re-exported below, so both the legacy
callers and the enhanced-routing submodules share a single namespace.

2026-08-04 死代码收敛：``adapters/``、``fallback.py``、``monitor.py``、
``prompt_optimizer.py``、``streaming.py`` 经全仓核查零生产调用，已归档至
``archive/dead_code_2026-08/backend/app/core/llm/``（含对应测试）。
"""

from .anthropic_backend import AnthropicBackend
from .backends import (
    BaseLLMBackend,
    LLMBackendError,
    LLMResponse,
    LLMRouter,
    MockLLMBackend,
    OpenAIBackend,
    OpenAIResponsesBackend,
    TokenUsage,
    build_llm_router,
    get_pricing_table,
)
from .cost_optimizer import CostOptimizer, CostTracker, TokenEstimator
from .llm_settings import LLMFeatureSettings, get_llm_feature_settings
from .ollama_backend import OllamaBackend

# P1-08 routing convergence: external profiles, new providers, smart routing,
# tenant/user token quotas.
from .profiles import (
    ModelProfileConfig,
    ModelProfileLoadError,
    QuotaFileConfig,
    build_selector,
    load_model_profiles,
    pricing_table_from_profiles,
)
from .quota import QuotaExceededError, TokenQuotaManager

# Enhanced routing / optimization components.
from .selector import ModelProfile, ModelSelector, SelectionStrategy, TaskType
from .smart_router import SmartLLMRouter, classify_task

__all__ = [
    "AnthropicBackend",
    # Legacy backends + core router
    "BaseLLMBackend",
    "CostOptimizer",
    "CostTracker",
    "LLMBackendError",
    "LLMFeatureSettings",
    "LLMResponse",
    "LLMRouter",
    "MockLLMBackend",
    "ModelProfile",
    # P1-08 routing convergence
    "ModelProfileConfig",
    "ModelProfileLoadError",
    # Enhanced routing / optimization
    "ModelSelector",
    "OllamaBackend",
    "OpenAIBackend",
    "OpenAIResponsesBackend",
    "QuotaExceededError",
    "QuotaFileConfig",
    "SelectionStrategy",
    "SmartLLMRouter",
    "TaskType",
    "TokenEstimator",
    "TokenQuotaManager",
    "TokenUsage",
    "build_llm_router",
    "build_selector",
    "classify_task",
    "get_llm_feature_settings",
    "get_pricing_table",
    "load_model_profiles",
    "pricing_table_from_profiles",
]
