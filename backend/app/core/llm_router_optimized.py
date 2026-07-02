"""
LLM路由器优化版 - 支持路由缓存、增量更新、连接池

优化特性:
- 路由决策缓存 (TTL: 5秒)
- 增量指标更新
- 连接池管理
- 批处理支持
- 性能监控
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Callable
from collections import defaultdict
import hashlib

logger = logging.getLogger(__name__)


class ModelProvider(str, Enum):
    """模型提供商"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    AZURE = "azure"
    LOCAL = "local"


class ModelType(str, Enum):
    """模型类型"""
    GPT_4 = "gpt-4"
    GPT_35_TURBO = "gpt-3.5-turbo"
    CLAUDE_3_OPUS = "claude-3-opus"
    CLAUDE_3_SONNET = "claude-3-sonnet"
    CLAUDE_3_HAIKU = "claude-3-haiku"
    GEMINI_PRO = "gemini-pro"
    LLAMA_2 = "llama-2"


@dataclass
class ModelConfig:
    """模型配置"""
    provider: ModelProvider
    model_type: ModelType
    api_key: str
    api_endpoint: Optional[str] = None
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout_seconds: int = 30
    retry_count: int = 3
    cost_per_1k_tokens: float = 0.0
    enabled: bool = True
    priority: int = 0


@dataclass
class ModelMetrics:
    """模型指标"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_tokens_used: int = 0
    total_cost: float = 0.0
    average_latency_ms: float = 0.0
    error_rate: float = 0.0
    last_used_at: float = 0.0
    availability: float = 100.0

    # 优化: 增量更新相关
    latency_sum: float = 0.0
    latency_count: int = 0

    def update_success(self, tokens_used: int, latency_ms: float, cost: float) -> None:
        """更新成功指标 (优化版)"""
        self.total_requests += 1
        self.successful_requests += 1
        self.total_tokens_used += tokens_used
        self.total_cost += cost

        # 增量更新平均延迟
        self.latency_sum += latency_ms
        self.latency_count += 1
        self.average_latency_ms = self.latency_sum / self.latency_count

        self.last_used_at = time.time()
        self._update_error_rate()

    def update_failure(self) -> None:
        """更新失败指标"""
        self.total_requests += 1
        self.failed_requests += 1
        self._update_error_rate()

    def _update_error_rate(self) -> None:
        """更新错误率"""
        if self.total_requests > 0:
            self.error_rate = self.failed_requests / self.total_requests
            self.availability = (1 - self.error_rate) * 100


@dataclass
class RoutingStrategy:
    """路由策略"""
    name: str
    description: str
    weight_factors: dict[str, float] = field(default_factory=dict)

    def calculate_score(self, metrics: ModelMetrics, config: ModelConfig) -> float:
        """计算模型得分"""
        score = 0.0
        score += config.priority * self.weight_factors.get("priority", 10.0)
        score += metrics.availability * self.weight_factors.get("availability", 5.0)
        score -= config.cost_per_1k_tokens * self.weight_factors.get("cost", 1.0)
        score -= metrics.average_latency_ms * self.weight_factors.get("latency", 0.01)
        return score


@dataclass
class RoutingDecision:
    """路由决策缓存项"""
    model_id: str
    score: float
    timestamp: float
    ttl: int = 5  # 5秒TTL


class ConnectionPool:
    """连接池管理"""

    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self.connections: dict[str, list[Any]] = defaultdict(list)
        self.lock = asyncio.Lock()
        self.stats = {"acquired": 0, "released": 0, "created": 0}

    async def acquire(self, provider: str) -> Any:
        """获取连接"""
        async with self.lock:
            if self.connections[provider]:
                conn = self.connections[provider].pop()
                self.stats["acquired"] += 1
                return conn

            if len(self.connections[provider]) < self.max_size:
                self.stats["created"] += 1
                return f"connection_{provider}_{self.stats['created']}"

        await asyncio.sleep(0.01)
        return await self.acquire(provider)

    async def release(self, provider: str, conn: Any) -> None:
        """释放连接"""
        async with self.lock:
            if len(self.connections[provider]) < self.max_size:
                self.connections[provider].append(conn)
                self.stats["released"] += 1


class LLMRouterOptimized:
    """优化版LLM路由器"""

    def __init__(self, cache_ttl: int = 5):
        """初始化路由器"""
        self.models: dict[str, ModelConfig] = {}
        self.metrics: dict[str, ModelMetrics] = defaultdict(ModelMetrics)
        self.strategies: dict[str, RoutingStrategy] = {}
        self.current_strategy = "balanced"

        # 优化: 路由决策缓存
        self.routing_cache: dict[str, RoutingDecision] = {}
        self.cache_ttl = cache_ttl

        # 优化: 连接池
        self.connection_pool = ConnectionPool(max_size=100)

        # 优化: 批处理队列
        self.batch_queue: list[tuple[str, dict[str, Any]]] = []
        self.batch_lock = asyncio.Lock()
        self.batch_size = 10
        self.batch_timeout = 0.1

        self._setup_default_strategies()

    def _setup_default_strategies(self) -> None:
        """设置默认路由策略"""
        self.strategies["balanced"] = RoutingStrategy(
            name="balanced",
            description="平衡成本、性能和可用性",
            weight_factors={
                "priority": 10.0,
                "availability": 5.0,
                "cost": 1.0,
                "latency": 0.01,
            }
        )

        self.strategies["performance"] = RoutingStrategy(
            name="performance",
            description="优先选择性能最好的模型",
            weight_factors={
                "priority": 5.0,
                "availability": 10.0,
                "cost": 0.1,
                "latency": 0.1,
            }
        )

        self.strategies["cost"] = RoutingStrategy(
            name="cost",
            description="优先选择成本最低的模型",
            weight_factors={
                "priority": 5.0,
                "availability": 5.0,
                "cost": 10.0,
                "latency": 0.01,
            }
        )

    def register_model(self, model_id: str, config: ModelConfig) -> None:
        """注册模型"""
        self.models[model_id] = config
        logger.info(f"Registered model: {model_id}")

    def _get_cache_key(self, strategy: str) -> str:
        """生成缓存键"""
        return hashlib.md5(f"{strategy}".encode(), usedforsecurity=False).hexdigest()

    def _is_cache_valid(self, decision: RoutingDecision) -> bool:
        """检查缓存是否有效"""
        return time.time() - decision.timestamp < decision.ttl

    def select_model(self, required_tokens: int = 0) -> Optional[str]:
        """选择最佳模型 (优化版)"""
        # 优化: 检查路由缓存
        cache_key = self._get_cache_key(self.current_strategy)
        if cache_key in self.routing_cache:
            cached = self.routing_cache[cache_key]
            if self._is_cache_valid(cached):
                logger.debug(f"Cache hit for routing decision: {cached.model_id}")
                return cached.model_id
            else:
                del self.routing_cache[cache_key]

        enabled_models = {
            model_id: config
            for model_id, config in self.models.items()
            if config.enabled
        }

        if not enabled_models:
            logger.warning("No enabled models available")
            return None

        strategy = self.strategies.get(self.current_strategy)
        if not strategy:
            logger.warning(f"Strategy not found: {self.current_strategy}")
            return None

        # 计算每个模型的得分
        scores = {}
        for model_id, config in enabled_models.items():
            metrics = self.metrics[model_id]
            score = strategy.calculate_score(metrics, config)
            scores[model_id] = score

        # 选择得分最高的模型
        best_model = max(scores, key=scores.get)

        # 优化: 缓存路由决策
        self.routing_cache[cache_key] = RoutingDecision(
            model_id=best_model,
            score=scores[best_model],
            timestamp=time.time(),
            ttl=self.cache_ttl
        )

        logger.debug(f"Selected model: {best_model} (score: {scores[best_model]:.2f})")
        return best_model

    async def call_model(
        self,
        model_id: str,
        prompt: str,
        **kwargs
    ) -> tuple[bool, str, dict[str, Any]]:
        """调用模型 (优化版)"""
        config = self.models.get(model_id)
        if not config:
            return False, f"Model not found: {model_id}", {}

        # 优化: 从连接池获取连接
        conn = await self.connection_pool.acquire(config.provider.value)

        start_time = time.time()
        try:
            result = await self._call_llm_api(config, prompt, conn, **kwargs)
            latency_ms = int((time.time() - start_time) * 1000)
            tokens_used = len(prompt.split()) + len(result.get("response", "").split())
            cost = (tokens_used / 1000) * config.cost_per_1k_tokens

            self.metrics[model_id].update_success(tokens_used, latency_ms, cost)

            return True, result.get("response", ""), {
                "tokens_used": tokens_used,
                "latency_ms": latency_ms,
                "cost": cost,
            }

        except Exception as e:
            self.metrics[model_id].update_failure()
            logger.error(f"Error calling model {model_id}: {e}")
            return False, str(e), {}
        finally:
            # 优化: 释放连接回连接池
            await self.connection_pool.release(config.provider.value, conn)

    async def _call_llm_api(
        self,
        config: ModelConfig,
        prompt: str,
        conn: Any,
        **kwargs
    ) -> dict[str, Any]:
        """调用LLM API"""
        await asyncio.sleep(0.05)  # 模拟API调用
        return {
            "response": f"Response from {config.model_type.value}",
            "tokens": len(prompt.split()),
        }

    async def call_with_fallback(
        self,
        prompt: str,
        max_retries: int = 3,
        **kwargs
    ) -> tuple[bool, str, dict[str, Any]]:
        """带故障转移的模型调用"""
        attempted_models = set()

        for attempt in range(max_retries):
            model_id = self.select_model()
            if not model_id:
                return False, "No available models", {}

            if model_id in attempted_models:
                model_id = self.select_model()
                if not model_id:
                    return False, "No fallback models available", {}

            attempted_models.add(model_id)
            success, response, metadata = await self.call_model(model_id, prompt, **kwargs)

            if success:
                metadata["model_id"] = model_id
                metadata["attempt"] = attempt + 1
                return True, response, metadata

            logger.warning(f"Model {model_id} failed on attempt {attempt + 1}")

        return False, "All models failed", {}

    def get_router_stats(self) -> dict[str, Any]:
        """获取路由器统计信息"""
        return {
            "current_strategy": self.current_strategy,
            "total_models": len(self.models),
            "enabled_models": sum(1 for c in self.models.values() if c.enabled),
            "cache_size": len(self.routing_cache),
            "connection_pool_stats": self.connection_pool.stats,
        }


# 全局路由器实例
_router: Optional[LLMRouterOptimized] = None


def get_router() -> LLMRouterOptimized:
    """获取全局LLM路由器"""
    global _router
    if _router is None:
        _router = LLMRouterOptimized()
    return _router


async def call_llm(
    prompt: str,
    strategy: str = "balanced",
    max_retries: int = 3,
    **kwargs
) -> tuple[bool, str, dict[str, Any]]:
    """调用LLM的便捷函数"""
    router = get_router()
    router.set_strategy(strategy)
    return await router.call_with_fallback(prompt, max_retries, **kwargs)
