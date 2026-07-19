"""LLM routing and optimization module for X-Agent.

This package historically coexisted with a ``backend/app/core/llm.py`` module of
the same name. Because a package shadows a same-named module on the import path,
the legacy backend classes (``LLMRouter`` and friends) became unreachable via
``from backend.app.core.llm import LLMRouter``. Those classes now live in
``backends.py`` inside this package and are re-exported below, so both the legacy
callers and the enhanced-routing submodules share a single namespace.
"""

# Legacy backend classes + core router (moved here from the old llm.py module).
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

# Enhanced routing / optimization components.
from .selector import ModelSelector, ModelProfile, SelectionStrategy, TaskType
from .cost_optimizer import CostOptimizer, CostTracker, TokenEstimator
from .fallback import FallbackStrategy, FallbackManager
from .streaming import StreamingResponse, StreamManager
from .prompt_optimizer import PromptOptimizer, PromptTemplate
from .monitor import PerformanceMonitor, ModelMetrics
from .adapters.base import LLMAdapter
from .adapters.openai_adapter import OpenAIAdapter
from .adapters.deepseek_adapter import DeepSeekAdapter
from .adapters.local_adapter import LocalAdapter

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
from .llm_settings import LLMFeatureSettings, get_llm_feature_settings
from .anthropic_backend import AnthropicBackend
from .ollama_backend import OllamaBackend
from .quota import QuotaExceededError, TokenQuotaManager
from .smart_router import SmartLLMRouter, classify_task

__all__ = [
    # Legacy backends + core router
    "BaseLLMBackend",
    "LLMBackendError",
    "LLMResponse",
    "LLMRouter",
    "MockLLMBackend",
    "OpenAIBackend",
    "OpenAIResponsesBackend",
    "TokenUsage",
    "build_llm_router",
    "get_pricing_table",
    # Enhanced routing / optimization
    "ModelSelector",
    "ModelProfile",
    "SelectionStrategy",
    "TaskType",
    "CostOptimizer",
    "CostTracker",
    "TokenEstimator",
    "FallbackStrategy",
    "FallbackManager",
    "StreamingResponse",
    "StreamManager",
    "PromptOptimizer",
    "PromptTemplate",
    "PerformanceMonitor",
    "ModelMetrics",
    "LLMAdapter",
    "OpenAIAdapter",
    "DeepSeekAdapter",
    "LocalAdapter",
    # P1-08 routing convergence
    "ModelProfileConfig",
    "ModelProfileLoadError",
    "QuotaFileConfig",
    "build_selector",
    "load_model_profiles",
    "pricing_table_from_profiles",
    "LLMFeatureSettings",
    "get_llm_feature_settings",
    "AnthropicBackend",
    "OllamaBackend",
    "QuotaExceededError",
    "TokenQuotaManager",
    "SmartLLMRouter",
    "classify_task",
]
