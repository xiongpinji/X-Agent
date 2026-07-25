"""LLM routing and optimization module for X-Agent.

This package historically coexisted with a ``backend/app/core/llm.py`` module of
the same name. Because a package shadows a same-named module on the import path,
the legacy backend classes (``LLMRouter`` and friends) became unreachable via
``from backend.app.core.llm import LLMRouter``. Those classes now live in
``backends.py`` inside this package and are re-exported below, so both the legacy
callers and the enhanced-routing submodules share a single namespace.
"""

# Legacy backend classes + core router (moved here from the old llm.py module).
from .adapters.base import LLMAdapter
from .adapters.deepseek_adapter import DeepSeekAdapter
from .adapters.local_adapter import LocalAdapter
from .adapters.openai_adapter import OpenAIAdapter
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
from .fallback import FallbackManager, FallbackStrategy
from .llm_settings import LLMFeatureSettings, get_llm_feature_settings
from .monitor import ModelMetrics, PerformanceMonitor
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
from .prompt_optimizer import PromptOptimizer, PromptTemplate
from .quota import QuotaExceededError, TokenQuotaManager

# Enhanced routing / optimization components.
from .selector import ModelProfile, ModelSelector, SelectionStrategy, TaskType
from .smart_router import SmartLLMRouter, classify_task
from .streaming import StreamingResponse, StreamManager

__all__ = [
    "AnthropicBackend",
    # Legacy backends + core router
    "BaseLLMBackend",
    "CostOptimizer",
    "CostTracker",
    "DeepSeekAdapter",
    "FallbackManager",
    "FallbackStrategy",
    "LLMAdapter",
    "LLMBackendError",
    "LLMFeatureSettings",
    "LLMResponse",
    "LLMRouter",
    "LocalAdapter",
    "MockLLMBackend",
    "ModelMetrics",
    "ModelProfile",
    # P1-08 routing convergence
    "ModelProfileConfig",
    "ModelProfileLoadError",
    # Enhanced routing / optimization
    "ModelSelector",
    "OllamaBackend",
    "OpenAIAdapter",
    "OpenAIBackend",
    "OpenAIResponsesBackend",
    "PerformanceMonitor",
    "PromptOptimizer",
    "PromptTemplate",
    "QuotaExceededError",
    "QuotaFileConfig",
    "SelectionStrategy",
    "SmartLLMRouter",
    "StreamManager",
    "StreamingResponse",
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
