"""MoA (Mixture of Agents) 混合模型推理引擎。

多模型并行推理 → 聚合器综合最优答案（对标 Hermes MoA 超越 Opus 4.8）。

策略:
- consensus: 聚合器模型综合所有回答生成最终答案
- best_of_n: 评分器对每个回答打分，选最优
- weighted_vote: 按模型质量加权投票

用法:
    from backend.app.core.llm.moa import MoAEngine, MoAConfig

    engine = MoAEngine(backends=[backend1, backend2, backend3])
    response = await engine.generate(messages, tools, MoAConfig(strategy="consensus"))
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from backend.app.core.llm.backends import BaseLLMBackend, LLMResponse

logger = logging.getLogger(__name__)


# ─── 配置 ─────────────────────────────────────────────────────────────────────


@dataclass
class MoAConfig:
    """MoA 配置."""

    enabled: bool = False
    strategy: str = "consensus"  # consensus | best_of_n | weighted_vote
    timeout_per_model: float = 60.0
    min_responses: int = 2  # 最少需要几个模型响应才进行聚合
    aggregator_model: str = ""  # 聚合器使用的模型名（空=用第一个后端）


@dataclass
class MoAResponseMeta:
    """MoA 响应元数据."""

    strategy: str = ""
    models_used: list[str] = field(default_factory=list)
    responses_collected: int = 0
    responses_failed: int = 0
    aggregation_time_ms: float = 0.0
    total_time_ms: float = 0.0
    individual_latencies: dict[str, float] = field(default_factory=dict)


# ─── 核心引擎 ─────────────────────────────────────────────────────────────────


class MoAEngine:
    """Mixture of Agents 引擎 — 多模型并行推理 + 聚合.

    Args:
        backends: 参与推理的 LLM 后端列表
        aggregator: 聚合器后端（None 则使用 backends[0]）
    """

    def __init__(
        self,
        backends: list[BaseLLMBackend],
        aggregator: BaseLLMBackend | None = None,
    ) -> None:
        if len(backends) < 2:
            raise ValueError("MoA requires at least 2 backends")
        self._backends = backends
        self._aggregator = aggregator or backends[0]

    @property
    def backend_count(self) -> int:
        return len(self._backends)

    async def generate(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        config: MoAConfig | None = None,
    ) -> LLMResponse:
        """多模型并行推理 + 聚合.

        Args:
            messages: 对话消息
            tools: 工具定义
            config: MoA 配置

        Returns:
            聚合后的 LLMResponse（附带 moa_metadata）
        """
        config = config or MoAConfig(enabled=True)
        start_time = time.time()
        meta = MoAResponseMeta(strategy=config.strategy)

        # 1. 并行调用所有后端
        individual_responses = await self._parallel_generate(
            messages, tools, config.timeout_per_model, meta
        )

        # 2. 检查最少响应数
        if len(individual_responses) < config.min_responses:
            # 不足时返回第一个成功的响应（降级）
            if individual_responses:
                logger.warning(
                    "MoA: only %d/%d responses (min=%d), degrading to single response",
                    len(individual_responses), self.backend_count, config.min_responses,
                )
                fallback = individual_responses[0]
                meta.total_time_ms = (time.time() - start_time) * 1000
                return self._attach_meta(fallback, meta)
            raise RuntimeError("MoA: all backends failed, no responses available")

        # 3. 聚合
        agg_start = time.time()
        if config.strategy == "best_of_n":
            aggregated = await self._aggregate_best_of_n(messages, individual_responses, meta)
        elif config.strategy == "weighted_vote":
            aggregated = await self._aggregate_weighted_vote(individual_responses, meta)
        else:  # consensus
            aggregated = await self._aggregate_consensus(messages, tools, individual_responses, meta)

        meta.aggregation_time_ms = (time.time() - agg_start) * 1000
        meta.total_time_ms = (time.time() - start_time) * 1000

        logger.info(
            "MoA %s: %d responses, aggregation=%.0fms, total=%.0fms",
            config.strategy, len(individual_responses),
            meta.aggregation_time_ms, meta.total_time_ms,
        )
        return self._attach_meta(aggregated, meta)

    async def _parallel_generate(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        timeout: float,
        meta: MoAResponseMeta,
    ) -> list[LLMResponse]:
        """并行调用所有后端，收集成功响应."""

        async def _call_one(backend: BaseLLMBackend) -> LLMResponse | None:
            model_name = getattr(backend, "model", backend.name)
            call_start = time.time()
            try:
                resp = await asyncio.wait_for(
                    backend.chat(messages, tools),
                    timeout=timeout,
                )
                latency = (time.time() - call_start) * 1000
                meta.individual_latencies[model_name] = latency
                meta.models_used.append(model_name)
                return resp
            except TimeoutError:
                logger.warning("MoA: %s timed out after %.0fs", model_name, timeout)
                return None
            except Exception as exc:
                logger.warning("MoA: %s failed: %s", model_name, exc)
                return None

        results = await asyncio.gather(
            *[_call_one(b) for b in self._backends],
            return_exceptions=False,
        )

        responses = [r for r in results if r is not None]
        meta.responses_collected = len(responses)
        meta.responses_failed = self.backend_count - len(responses)
        return responses

    async def _aggregate_consensus(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        responses: list[LLMResponse],
        meta: MoAResponseMeta,
    ) -> LLMResponse:
        """共识聚合：聚合器模型综合所有回答."""
        # 构建聚合提示
        synthesis_prompt = (
            "以下是多个 AI 模型对同一问题的回答。"
            "请综合所有回答的优点，生成一个最完整、最准确的最终答案。\n\n"
        )
        for i, resp in enumerate(responses, 1):
            content = resp.content or ""
            synthesis_prompt += f"--- 模型 {i} ---\n{content[:3000]}\n\n"
        synthesis_prompt += "请输出综合后的最终答案："

        agg_messages = [*list(messages), {"role": "user", "content": synthesis_prompt}]

        try:
            aggregated = await self._aggregator.chat(agg_messages, tools)
            # 累加所有 token
            total_tokens = sum(r.tokens_used for r in responses) + aggregated.tokens_used
            return LLMResponse(
                content=aggregated.content,
                tokens_used=total_tokens,
                model=f"moa-consensus({len(responses)} models)",
                tool_calls=aggregated.tool_calls,
            )
        except Exception as exc:
            logger.warning("MoA consensus aggregation failed: %s, using longest", exc)
            return max(responses, key=lambda r: len(r.content or ""))

    async def _aggregate_best_of_n(
        self,
        messages: list[dict[str, str]],
        responses: list[LLMResponse],
        meta: MoAResponseMeta,
    ) -> LLMResponse:
        """Best-of-N：评分器选最优回答."""
        # 使用聚合器对每个回答评分
        best = responses[0]
        best_score = 0.0

        for resp in responses:
            score_prompt = (
                f"请对以下回答的质量打分（0-100），只返回数字：\n\n"
                f"回答: {(resp.content or '')[:2000]}"
            )
            try:
                score_resp = await self._aggregator.chat(
                    messages=[{"role": "user", "content": score_prompt}],
                    tools=[],
                )
                score_text = (score_resp.content or "0").strip()
                score = float("".join(c for c in score_text if c.isdigit() or c == ".")[:5] or "0")
            except Exception:
                score = len(resp.content or "") / 100.0  # 启发式 fallback

            if score > best_score:
                best_score = score
                best = resp

        total_tokens = sum(r.tokens_used for r in responses)
        return LLMResponse(
            content=best.content,
            tokens_used=total_tokens,
            model=f"moa-best-of-{len(responses)}",
            tool_calls=best.tool_calls,
        )

    async def _aggregate_weighted_vote(
        self,
        responses: list[LLMResponse],
        meta: MoAResponseMeta,
    ) -> LLMResponse:
        """加权投票：按内容相似度聚类，选最大簇的代表."""
        # 简化实现：按内容长度加权 + 关键词重叠度
        if not responses:
            return LLMResponse(content="", tokens_used=0)

        # 计算每个响应与其他响应的关键词重叠度作为"投票"
        scores: list[float] = []
        for i, resp_i in enumerate(responses):
            words_i = set((resp_i.content or "").lower().split())
            score = 0.0
            for j, resp_j in enumerate(responses):
                if i == j:
                    continue
                words_j = set((resp_j.content or "").lower().split())
                if words_i and words_j:
                    overlap = len(words_i & words_j) / max(len(words_i | words_j), 1)
                    score += overlap
            scores.append(score)

        best_idx = scores.index(max(scores))
        best = responses[best_idx]
        total_tokens = sum(r.tokens_used for r in responses)
        return LLMResponse(
            content=best.content,
            tokens_used=total_tokens,
            model=f"moa-vote({len(responses)} models)",
            tool_calls=best.tool_calls,
        )

    def _attach_meta(self, response: LLMResponse, meta: MoAResponseMeta) -> LLMResponse:
        """将 MoA 元数据附加到响应."""
        if not hasattr(response, "metadata"):
            response.metadata = {}
        if isinstance(getattr(response, "metadata", None), dict):
            response.metadata["moa"] = {
                "strategy": meta.strategy,
                "models_used": meta.models_used,
                "responses_collected": meta.responses_collected,
                "responses_failed": meta.responses_failed,
                "aggregation_time_ms": meta.aggregation_time_ms,
                "total_time_ms": meta.total_time_ms,
            }
        return response
