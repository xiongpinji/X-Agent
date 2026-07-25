"""Smart routing layer over the production sequential LLMRouter (P1-08).

``SmartLLMRouter`` keeps the sequential-fallback shell semantics of
``LLMRouter`` — every request still walks an ordered backend list and falls
back on provider errors — but the ORDER is computed per request by
``ModelSelector`` using task type / cost / latency / quality, with model
profiles loaded from ``config/model_profiles.yaml``.

Explicit degrades (never silent):
- selection itself raises      -> warning log + configured order
- selected model has no live backend -> warning log + configured order
"""

from __future__ import annotations

import logging
from typing import Any

from backend.app.core.llm.backends import BaseLLMBackend, LLMRouter
from backend.app.core.llm.cost_optimizer import TokenEstimator
from backend.app.core.llm.selector import (
    ModelSelector,
    SelectionContext,
    SelectionStrategy,
    TaskType,
)

logger = logging.getLogger(__name__)


def classify_task(
    messages: list[dict[str, str]],
    tools: list[dict[str, Any]],
) -> TaskType:
    """Lightweight heuristic task classifier for smart routing.

    Keyword-based on purpose: deterministic, offline, and cheap. Callers that
    know better can pass an explicit ``task_type`` to ``chat()`` which always
    wins over this heuristic.
    """
    last_user = next(
        (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"),
        "",
    )
    text = last_user.lower()

    if any(k in text for k in ("translate", "翻译", "译文")):
        return TaskType.TRANSLATION
    if any(k in text for k in ("summarize", "summary", "总结", "摘要", "概括")):
        return TaskType.SUMMARIZATION
    if any(k in text for k in ("code", "function", "implement", "代码", "函数", "实现", "调试", "debug")):
        return TaskType.CODE_GENERATION
    if any(k in text for k in ("analyze", "analysis", "分析", "洞察", "compare", "对比")):
        return TaskType.ANALYSIS
    if any(k in text for k in ("story", "poem", "creative", "创作", "写一首", " brainstorm")):
        return TaskType.CREATIVE
    if any(k in text for k in ("step by step", "推理", "reason", "why", "为什么")):
        return TaskType.COMPLEX_REASONING
    # Tool-driven agent turns are typically short operational prompts.
    if len(text) < 200:
        return TaskType.SIMPLE_QA
    return TaskType.UNKNOWN


class SmartLLMRouter(LLMRouter):
    """LLMRouter with per-request intelligent backend ordering."""

    def __init__(
        self,
        *,
        backends: list[BaseLLMBackend],
        selector: ModelSelector,
        strategy: str | SelectionStrategy = SelectionStrategy.BALANCED,
        quota_manager: Any | None = None,
    ) -> None:
        super().__init__(backends=backends, quota_manager=quota_manager)
        self.selector = selector
        try:
            self.default_strategy = (
                strategy
                if isinstance(strategy, SelectionStrategy)
                else SelectionStrategy(str(strategy))
            )
        except ValueError as exc:
            valid = ", ".join(s.value for s in SelectionStrategy)
            raise ValueError(
                f"unknown smart routing strategy '{strategy}'; valid: {valid}"
            ) from exc

    def _order_backends(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        *,
        task_type: str | TaskType | None = None,
        strategy: str | SelectionStrategy | None = None,
    ) -> list[BaseLLMBackend]:
        configured = list(self._backends)

        # Resolve explicit overrides; heuristic classification otherwise.
        if task_type is None:
            resolved_task = classify_task(messages, tools)
        elif isinstance(task_type, TaskType):
            resolved_task = task_type
        else:
            try:
                resolved_task = TaskType(str(task_type))
            except ValueError as exc:
                valid = ", ".join(t.value for t in TaskType)
                raise ValueError(
                    f"unknown task_type '{task_type}'; valid: {valid}"
                ) from exc

        if strategy is None:
            resolved_strategy = self.default_strategy
        elif isinstance(strategy, SelectionStrategy):
            resolved_strategy = strategy
        else:
            try:
                resolved_strategy = SelectionStrategy(str(strategy))
            except ValueError as exc:
                valid = ", ".join(s.value for s in SelectionStrategy)
                raise ValueError(
                    f"unknown routing strategy '{strategy}'; valid: {valid}"
                ) from exc

        input_tokens = sum(
            TokenEstimator.estimate_input_tokens(m.get("content", "") or "")
            for m in messages
        )
        context = SelectionContext(
            task_type=resolved_task,
            strategy=resolved_strategy,
            input_tokens=input_tokens,
        )

        try:
            ranked = self.selector.rank_candidates(context)
        except Exception as exc:
            logger.warning(
                "Smart routing selection failed (%s); using configured backend order.",
                exc,
            )
            return configured

        # Map the ranked catalog onto live backends (model name first, then
        # provider); the first candidate with a LIVE backend leads the
        # try-order. Remaining configured backends keep their relative order
        # at the tail so the sequential-fallback shell stays intact.
        ordered: list[BaseLLMBackend] = []
        chosen_model: str | None = None
        for profile in ranked:
            match = next(
                (b for b in configured
                 if getattr(b, "model", None) == profile.name and b not in ordered),
                None,
            )
            if match is None:
                match = next(
                    (b for b in configured
                     if b.name == profile.provider and b not in ordered),
                    None,
                )
            if match is not None:
                if chosen_model is None:
                    chosen_model = profile.name
                ordered.append(match)

        if not ordered:
            logger.warning(
                "Smart routing candidates %s have no live backend; using "
                "configured backend order.",
                [p.name for p in ranked[:3]],
            )
            return configured

        ordered.extend(b for b in configured if b not in ordered)
        logger.info(
            "Smart routing picked model '%s' first (task=%s, strategy=%s).",
            chosen_model,
            resolved_task.value,
            resolved_strategy.value,
        )
        return ordered

    def _on_backend_success(self, backend: BaseLLMBackend, response: Any) -> None:
        """Feed observed latency/tokens back into the selector."""
        try:
            self.selector.record_performance(
                getattr(backend, "model", backend.name),
                success=True,
                latency_ms=getattr(response, "latency_ms", 0.0),
                tokens_used=getattr(response, "tokens_used", 0),
            )
        except Exception as exc:
            logger.warning("Failed to record selector performance: %s", exc)
