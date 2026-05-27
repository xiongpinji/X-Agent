"""LLM routing and optimization module for X-Agent."""

from .selector import ModelSelector, SelectionStrategy, TaskType
from .cost_optimizer import CostOptimizer, CostTracker, TokenEstimator
from .fallback import FallbackStrategy, FallbackManager
from .streaming import StreamingResponse, StreamManager
from .prompt_optimizer import PromptOptimizer, PromptTemplate
from .monitor import PerformanceMonitor, ModelMetrics
from .adapters.base import LLMAdapter
from .adapters.openai_adapter import OpenAIAdapter
from .adapters.deepseek_adapter import DeepSeekAdapter
from .adapters.local_adapter import LocalAdapter

__all__ = [
    "ModelSelector",
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
]
