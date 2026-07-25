"""AgentLoop 与 core/context 上下文管理体系的桥接层。

本模块把 ~2500 行的 core/context 实现（ContextManager / SessionRecovery /
ContextCompactor / ContextCompressor）接入 Agent 主循环，提供三项能力：

1. Token 级上下文压缩：发给 LLM 的消息列表超阈值时自动摘要/裁剪
   （保护 system 消息与最近消息，压缩中段历史）。
2. 会话恢复：按 session_id 从存储重建上下文，并把最近历史以
   有界 recap 形式注入规划提示词。
3. 会话持久化：运行过程中的观察/答案写入会话，结束后保存快照。

显式降级原则：桥接不可用或存储失败时，主循环继续运行，但会在
execution_summary["context_management"] 中记录 error，绝不静默假成功。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from backend.app.core.context.context_manager import ContextManager
from backend.app.core.context.session_recovery import SessionRecovery, SessionState
from backend.app.core.context_compactor import ContextCompactor

logger = logging.getLogger(__name__)

#: 主循环发给 LLM 的消息列表默认 token 预算。
DEFAULT_CONTEXT_TOKEN_BUDGET = 24_000

#: fit_messages_to_token_budget 中始终保留的最新非 system 消息条数。
DEFAULT_KEEP_LAST_MESSAGES = 2


def fit_messages_to_token_budget(
    compactor: ContextCompactor,
    messages: list[dict[str, str]],
    *,
    keep_last: int = DEFAULT_KEEP_LAST_MESSAGES,
) -> tuple[list[dict[str, str]], dict[str, Any] | None]:
    """把发给 LLM 的消息列表压缩到 token 预算内。

    策略（确定性、无需 LLM、可与 mock 后端工作）：
    1. 未超阈值（compactor.compression_threshold * token_limit）→ 原样返回。
    2. system 消息全部保留；最新 keep_last 条非 system 消息原样保留；
       中段历史用 ContextCompactor 做重要性评分压缩并插入摘要。
    3. 仍超预算 → 对超长 content 做迭代减半硬截断（带显式标记）。

    Args:
        compactor: 用于 token 计数与中段压缩的 ContextCompactor。
        messages: 待压缩的消息列表（role/content 字典）。
        keep_last: 始终保留的最新非 system 消息条数。

    Returns:
        (压缩后的消息列表, 压缩元数据 | None)。未触发压缩时元数据为 None。
    """
    if not messages:
        return messages, None

    original_tokens = compactor.count_messages_tokens(messages)
    if not compactor.should_compress(messages):
        return messages, None

    system_msgs = [m for m in messages if m.get("role") == "system"]
    body = [m for m in messages if m.get("role") != "system"]
    tail = body[-keep_last:] if len(body) > keep_last else list(body)
    middle = body[:-keep_last] if len(body) > keep_last else []

    strategies: list[str] = []
    if middle:
        result = compactor.compress(middle)
        if result.success:
            new_body = list(result.messages) + tail
            strategies.append("importance_compaction")
        else:
            # 压缩失败显式降级：保留更多近期消息，不静默丢历史。
            logger.warning("fit_messages_to_token_budget: compactor failed: %s", result.error)
            new_body = list(middle[-max(keep_last, compactor.min_messages_to_keep):]) + tail
            strategies.append("fallback_keep_recent")
    else:
        new_body = tail

    candidate = system_msgs + new_body

    compressed_tokens = compactor.count_messages_tokens(candidate)
    if compressed_tokens > compactor.token_limit:
        candidate = _hard_truncate_to_budget(compactor, candidate, keep_last=keep_last)
        compressed_tokens = compactor.count_messages_tokens(candidate)
        strategies.append("hard_truncate")

    meta: dict[str, Any] = {
        "triggered": True,
        "scope": "llm_messages",
        "original_tokens": original_tokens,
        "compressed_tokens": compressed_tokens,
        "compression_ratio": round(compressed_tokens / original_tokens, 4) if original_tokens else 1.0,
        "messages_before": len(messages),
        "messages_after": len(candidate),
        "strategy": "+".join(strategies) if strategies else "none",
    }
    logger.info(
        "LLM message compression: %s → %s tokens (%s messages → %s)",
        original_tokens, compressed_tokens, len(messages), len(candidate),
    )
    return candidate, meta


def _hard_truncate_to_budget(
    compactor: ContextCompactor,
    messages: list[dict[str, str]],
    *,
    keep_last: int = DEFAULT_KEEP_LAST_MESSAGES,
    max_passes: int = 8,
) -> list[dict[str, str]]:
    """对仍超预算的消息列表做有界迭代硬截断。

    保护优先级：system 消息 > 最新 keep_last 条消息 > 中段消息。
    只有当中段没有可截内容（全部 < 200 字符）时才截尾部最新消息，
    保证极端场景下 token 预算仍可收敛。
    """
    result = [dict(m) for m in messages]
    tail_start = max(0, len(result) - keep_last)

    def _longest_index(allow_tail: bool) -> int:
        longest_idx = -1
        longest_len = 0
        for idx, msg in enumerate(result):
            if msg.get("role") == "system":
                continue
            if not allow_tail and idx >= tail_start:
                continue
            content_len = len(str(msg.get("content", "")))
            if content_len > longest_len:
                longest_len = content_len
                longest_idx = idx
        return longest_idx if longest_len >= 200 else -1

    for _ in range(max_passes):
        if compactor.count_messages_tokens(result) <= compactor.token_limit:
            break
        idx = _longest_index(allow_tail=False)
        if idx < 0:
            idx = _longest_index(allow_tail=True)
        if idx < 0:
            break
        content = str(result[idx].get("content", ""))
        half = max(100, len(content) // 2)
        result[idx]["content"] = (
            content[:half] + f"\n…[truncated {len(content) - half} chars for token budget]"
        )
    return result


class AgentLoopContextBridge:
    """AgentLoop 的上下文管理桥接器。

    包装 ContextManager，面向单次 agent 运行提供会话打开/重建、
    消息记录、LLM 消息压缩与会话保存能力。

    注意：底层 ContextManager 是单活跃会话语义。并发运行不同 session_id
    时应使用各自独立的 bridge（AgentLoop 默认按运行创建临时 bridge）。
    """

    def __init__(
        self,
        context_manager: ContextManager,
        *,
        token_budget: int = DEFAULT_CONTEXT_TOKEN_BUDGET,
        recap_max_messages: int = 12,
        recap_max_chars: int = 3_000,
    ) -> None:
        """初始化桥接器。

        Args:
            context_manager: 底层上下文管理器。
            token_budget: 发给 LLM 的消息列表 token 预算。
            recap_max_messages: 会话 recap 最多包含的历史消息条数。
            recap_max_chars: 会话 recap 最大字符数。
        """
        self.context_manager = context_manager
        self.token_budget = token_budget
        self.recap_max_messages = recap_max_messages
        self.recap_max_chars = recap_max_chars

        self.session_active: bool = False
        self.session_id: str | None = None
        self.restored_message_count: int = 0
        self.compression_events: list[dict[str, Any]] = []

    @classmethod
    def create_default(
        cls,
        *,
        storage_path: str | Path | None = None,
        token_budget: int = DEFAULT_CONTEXT_TOKEN_BUDGET,
        compression_threshold: float = 0.85,
        min_messages_to_keep: int = 3,
    ) -> AgentLoopContextBridge:
        """按默认配置创建桥接器（文件系统会话存储 + 阈值压缩）。

        Args:
            storage_path: 会话快照存储目录；None 时使用项目 data/sessions。
            token_budget: LLM 消息 token 预算（同时作为压缩阈值基数）。
            compression_threshold: 触发压缩的使用率阈值。
            min_messages_to_keep: 压缩时最少保留的消息条数。
        """
        if storage_path is None:
            storage_path = cls.default_storage_path()
        recovery = SessionRecovery(storage_path=storage_path)
        compactor = ContextCompactor(
            token_limit=token_budget,
            compression_threshold=compression_threshold,
            min_messages_to_keep=min_messages_to_keep,
        )
        manager = ContextManager(
            session_recovery=recovery,
            context_compactor=compactor,
            auto_compress_enabled=True,
        )
        return cls(manager, token_budget=token_budget)

    @staticmethod
    def default_storage_path() -> Path:
        """默认会话存储目录：<项目根>/data/sessions（与 settings 数据目录约定一致）。"""
        try:
            from backend.app.settings import PROJECT_ROOT

            return Path(PROJECT_ROOT) / "data" / "sessions"
        except Exception:  # pragma: no cover - settings 不可用时显式降级到用户目录
            return Path("~/.xagent/sessions").expanduser()

    async def open_session(
        self,
        *,
        session_id: str,
        agent_id: str = "",
        tenant_id: str = "",
        context_window: int = 128_000,
    ) -> SessionState:
        """打开（或从存储恢复）会话。

        Returns:
            SessionState（恢复的会话含历史消息）。

        Raises:
            ValueError: 恢复会话的 tenant 与请求 tenant 不一致时（显式报错）。
        """
        state = await self.context_manager.initialize_session(
            session_id=session_id,
            agent_id=agent_id,
            tenant_id=tenant_id,
            context_window=context_window,
        )
        self.session_active = True
        self.session_id = session_id
        self.restored_message_count = len(state.messages)
        if self.restored_message_count:
            logger.info(
                "Session %s restored with %s messages (%s tokens)",
                session_id, self.restored_message_count, state.total_tokens,
            )
        return state

    def build_session_recap(self) -> str:
        """把已恢复会话的最近历史渲染成有界文本块，用于注入规划提示词。

        Returns:
            recap 文本；无历史时返回空串。
        """
        session = self.context_manager.current_session
        if not session or not session.messages:
            return ""

        recent = session.messages[-self.recap_max_messages:]
        lines: list[str] = []
        total = 0
        omitted = len(session.messages) - len(recent)
        if omitted > 0:
            header = f"(… {omitted} earlier messages omitted"
            if session.compression_history:
                header += f"; {len(session.compression_history)} compression(s) applied before)"
            else:
                header += ")"
            lines.append(header)

        for msg in recent:
            content = msg.content
            remaining = self.recap_max_chars - total
            if remaining <= 0:
                break
            if len(content) > min(400, remaining):
                content = content[: min(400, remaining)] + "…"
            prefix = "[summary]" if msg.compressed else f"[{msg.role}]"
            line = f"{prefix} {content}"
            lines.append(line)
            total += len(line)

        return "\n".join(lines)

    async def record(
        self,
        role: str,
        content: str,
        *,
        metadata: dict | None = None,
        importance: float = 0.5,
    ) -> Any | None:
        """记录一条消息到活跃会话（自动压缩在 ContextManager 内按阈值触发）。

        会话未激活时显式降级为 no-op，返回 None。
        """
        if not self.session_active:
            return None
        return await self.context_manager.add_message(
            role=role,
            content=content,
            metadata=metadata or {},
            importance=importance,
        )

    def fit_messages(
        self,
        messages: list[dict[str, str]],
        *,
        keep_last: int = DEFAULT_KEEP_LAST_MESSAGES,
    ) -> tuple[list[dict[str, str]], dict[str, Any] | None]:
        """压缩发给 LLM 的消息列表（见 fit_messages_to_token_budget）。"""
        fitted, meta = fit_messages_to_token_budget(
            self.context_manager.context_compactor,
            messages,
            keep_last=keep_last,
        )
        if meta:
            self.compression_events.append(meta)
        return fitted, meta

    async def prepare_context(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int | None = None,
        strategy: str = "sliding_window",
        priority: list[str] | None = None,
        reserve_output: int = 4096,
    ) -> list[dict[str, str]]:
        """P1-14: 在 LLM 调用前准备上下文——按策略压缩/裁剪消息列表。

        支持的策略：
        - sliding_window: 保留 system + 最近消息，压缩中段历史（默认）
        - summarize: 对历史消息做摘要压缩，保留语义核心
        - hybrid: 先摘要再滑动窗口截断

        优先级顺序（priority）决定保留顺序：
        - system: system 消息始终保留
        - recent: 最近的消息优先保留
        - memory: 从记忆系统检索的相关上下文
        - history: 早期历史消息（最先被压缩）

        Args:
            messages: 待处理的消息列表（role/content 字典）。
            max_tokens: 上下文窗口总 token 数；None 时使用桥接器 token_budget。
            strategy: 压缩策略 (sliding_window | summarize | hybrid)。
            priority: 保留优先级列表；默认 ["system", "recent", "memory", "history"]。
            reserve_output: 为 LLM 输出预留的 token 数。

        Returns:
            压缩后的消息列表。失败时显式降级返回原消息（绝不抛异常）。
        """
        if not messages:
            return messages

        if priority is None:
            priority = ["system", "recent", "memory", "history"]

        effective_budget = (max_tokens or self.token_budget) - reserve_output
        if effective_budget <= 0:
            effective_budget = self.token_budget

        try:
            compactor = self.context_manager.context_compactor
            original_tokens = compactor.count_messages_tokens(messages)

            # 未超阈值，原样返回
            if original_tokens <= effective_budget:
                return messages

            if strategy == "summarize":
                result = self._apply_summarize_strategy(messages, effective_budget, priority)
            elif strategy == "hybrid":
                result = self._apply_hybrid_strategy(messages, effective_budget, priority)
            else:  # sliding_window (default)
                result = self._apply_sliding_window_strategy(messages, effective_budget, priority)

            compressed_tokens = compactor.count_messages_tokens(result)
            meta: dict[str, Any] = {
                "triggered": True,
                "scope": "prepare_context",
                "strategy": strategy,
                "original_tokens": original_tokens,
                "compressed_tokens": compressed_tokens,
                "compression_ratio": round(compressed_tokens / original_tokens, 4) if original_tokens else 1.0,
                "messages_before": len(messages),
                "messages_after": len(result),
                "priority": priority,
            }
            self.compression_events.append(meta)
            logger.info(
                "prepare_context (%s): %s → %s tokens, %s → %s messages",
                strategy, original_tokens, compressed_tokens, len(messages), len(result),
            )
            return result

        except Exception as exc:
            # 显式降级：上下文管理失败不阻断主循环
            logger.warning("prepare_context failed, falling back to original messages: %s", exc)
            return messages

    def _apply_sliding_window_strategy(
        self,
        messages: list[dict[str, str]],
        budget: int,
        priority: list[str],
    ) -> list[dict[str, str]]:
        """滑动窗口策略：保留 system + 最近消息，压缩/丢弃中段历史。"""
        compactor = self.context_manager.context_compactor

        # 按优先级分离消息
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]

        # 保留最近消息（至少保留 4 条或 50% 的非 system 消息）
        keep_recent_count = max(4, len(non_system) // 2)
        recent = non_system[-keep_recent_count:] if len(non_system) > keep_recent_count else list(non_system)
        middle = non_system[:-keep_recent_count] if len(non_system) > keep_recent_count else []

        # 对中段做重要性压缩
        if middle:
            result = compactor.compress(middle)
            if result.success:
                candidate = system_msgs + list(result.messages) + recent
            else:
                # 压缩失败：保留最近的几条中段消息
                candidate = system_msgs + middle[-3:] + recent
        else:
            candidate = system_msgs + recent

        # 如果仍超预算，硬截断
        if compactor.count_messages_tokens(candidate) > budget:
            candidate = _hard_truncate_to_budget(compactor, candidate, keep_last=len(recent))

        return candidate

    def _apply_summarize_strategy(
        self,
        messages: list[dict[str, str]],
        budget: int,
        priority: list[str],
    ) -> list[dict[str, str]]:
        """摘要策略：将历史消息压缩为摘要，保留语义核心。"""
        compactor = self.context_manager.context_compactor

        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]

        # 保留最近 2 条消息原样
        keep_last = 2
        recent = non_system[-keep_last:] if len(non_system) > keep_last else list(non_system)
        history = non_system[:-keep_last] if len(non_system) > keep_last else []

        if history:
            # 将历史消息合并为摘要
            history_text = "\n".join(
                f"[{m.get('role', 'unknown')}] {str(m.get('content', ''))[:500]}"
                for m in history
            )
            # 简单摘要：取前 1500 字符作为摘要
            summary_content = history_text[:1500]
            if len(history_text) > 1500:
                summary_content += f"\n…({len(history_text) - 1500} chars omitted)"
            summary_msg = {
                "role": "system",
                "content": f"[Conversation summary of {len(history)} earlier messages]\n{summary_content}",
            }
            candidate = [*system_msgs, summary_msg, *recent]
        else:
            candidate = system_msgs + recent

        # 如果仍超预算，硬截断
        if compactor.count_messages_tokens(candidate) > budget:
            candidate = _hard_truncate_to_budget(compactor, candidate, keep_last=keep_last)

        return candidate

    def _apply_hybrid_strategy(
        self,
        messages: list[dict[str, str]],
        budget: int,
        priority: list[str],
    ) -> list[dict[str, str]]:
        """混合策略：先摘要压缩历史，再滑动窗口截断。"""
        # 第一步：摘要压缩
        summarized = self._apply_summarize_strategy(messages, budget, priority)

        # 第二步：如果仍超预算，用滑动窗口进一步截断
        compactor = self.context_manager.context_compactor
        if compactor.count_messages_tokens(summarized) > budget:
            return self._apply_sliding_window_strategy(summarized, budget, priority)

        return summarized

    async def close(self, *, save: bool = True) -> bool:
        """关闭桥接会话；save=True 时保存快照。

        Returns:
            快照是否保存成功（未激活或 save=False 时返回 False）。
        """
        saved = False
        if save and self.session_active:
            saved = await self.context_manager.save_session()
        self.session_active = False
        return saved

    def metrics_snapshot(self) -> dict[str, Any]:
        """导出本次桥接的上下文管理指标（用于 execution_summary）。"""
        session = self.context_manager.current_session
        return {
            "session_id": self.session_id,
            "session_active": self.session_active,
            "restored_messages": self.restored_message_count,
            "session_messages": len(session.messages) if session else 0,
            "session_total_tokens": session.total_tokens if session else 0,
            "session_compressions": len(session.compression_history) if session else 0,
            "llm_compression_events": list(self.compression_events),
        }
