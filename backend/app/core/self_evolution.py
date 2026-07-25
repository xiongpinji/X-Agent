"""Self-Evolution Engine — Execute-Evaluate-Optimize-Learn closed loop.

P1-06: Implements a four-stage self-evolution cycle that enables agents to
improve over time by:
1. Execute: Record agent execution traces
2. Evaluate: Score execution quality (success rate, user feedback)
3. Optimize: Adjust prompt/tool selection based on evaluation
4. Learn: Distill successful patterns into reusable skills

This module complements the existing ``evolution_engine.py`` (GEPA-style)
by providing a more structured, record-based approach with explicit stage
tracking and skill distillation from multiple executions.
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class EvolutionStage(StrEnum):
    """Stages of the self-evolution cycle."""

    EXECUTE = "execute"
    EVALUATE = "evaluate"
    OPTIMIZE = "optimize"
    LEARN = "learn"


@dataclass
class EvolutionRecord:
    """A record of one evolution stage execution."""

    id: str = field(default_factory=lambda: str(uuid4()))
    task_id: str = ""
    stage: EvolutionStage = EvolutionStage.EXECUTE
    input_data: dict[str, Any] = field(default_factory=dict)
    output_data: dict[str, Any] = field(default_factory=dict)
    score: float | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "stage": self.stage.value,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "score": self.score,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class DistilledSkill:
    """A skill distilled from successful execution patterns."""

    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    pattern: str = ""
    tool_sequence: list[str] = field(default_factory=list)
    success_rate: float = 0.0
    source_execution_ids: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "pattern": self.pattern,
            "tool_sequence": self.tool_sequence,
            "success_rate": self.success_rate,
            "source_execution_ids": self.source_execution_ids,
            "created_at": self.created_at.isoformat(),
        }


class SelfEvolutionEngine:
    """Execute-Evaluate-Optimize-Learn closed-loop self-evolution engine.

    Maintains execution records, evaluates quality, optimizes strategies,
    and distills reusable skills from successful patterns.

    Args:
        llm_router: Optional LLM router for intelligent evaluation/optimization.
        min_skill_confidence: Minimum confidence to distill a skill (0.0-1.0).
    """

    def __init__(
        self,
        llm_router: Any | None = None,
        min_skill_confidence: float = 0.7,
    ) -> None:
        self._llm_router = llm_router
        self._min_skill_confidence = min_skill_confidence
        self._records: list[EvolutionRecord] = []
        self._skills: list[DistilledSkill] = []
        self._task_records: dict[str, list[str]] = defaultdict(list)  # task_id -> record_ids
        self._optimization_history: list[dict[str, Any]] = []

    @property
    def llm_router(self) -> Any:
        """Lazy-load the LLM router if not provided at construction."""
        if self._llm_router is None:
            try:
                from backend.app.dependencies import get_llm_router
                self._llm_router = get_llm_router()
            except Exception:
                pass
        return self._llm_router

    async def record_execution(self, task_id: str, trace: dict[str, Any]) -> str:
        """Stage 1 - Execute: Record an agent execution trace.

        Args:
            task_id: Identifier for the task that was executed.
            trace: Execution trace data (tool calls, outputs, timing, etc.).

        Returns:
            The execution record ID.
        """
        record = EvolutionRecord(
            task_id=task_id,
            stage=EvolutionStage.EXECUTE,
            input_data={"task_id": task_id},
            output_data=trace,
        )
        self._records.append(record)
        self._task_records[task_id].append(record.id)
        logger.info(f"Recorded execution for task {task_id}: {record.id}")
        return record.id

    async def evaluate_execution(
        self,
        execution_id: str,
        feedback: dict[str, Any] | None = None,
    ) -> float:
        """Stage 2 - Evaluate: Score execution quality.

        Evaluates based on:
        - Task completion status
        - Tool call efficiency
        - Error count
        - User feedback (if provided)

        Args:
            execution_id: The execution record ID to evaluate.
            feedback: Optional user feedback dict with keys like
                      'rating' (1-5), 'comment', 'success' (bool).

        Returns:
            Quality score between 0.0 and 1.0.
        """
        record = self._find_record(execution_id)
        if record is None:
            logger.warning(f"Execution record not found: {execution_id}")
            return 0.0

        trace = record.output_data
        score = 0.5  # Base score

        # Factor 1: Task completion status
        status = trace.get("status", "")
        if status in ("completed", "success"):
            score += 0.2
        elif status in ("failed", "error"):
            score -= 0.3

        # Factor 2: Tool call efficiency
        tool_calls = trace.get("tool_calls", [])
        if tool_calls:
            failed_tools = sum(
                1 for tc in tool_calls
                if isinstance(tc, dict) and tc.get("status") == "failed"
            )
            efficiency = 1.0 - (failed_tools / len(tool_calls))
            score += efficiency * 0.15

        # Factor 3: Error count
        errors = trace.get("errors", [])
        if errors:
            score -= min(0.2, len(errors) * 0.05)

        # Factor 4: User feedback
        if feedback:
            if feedback.get("success") is True:
                score += 0.15
            elif feedback.get("success") is False:
                score -= 0.15
            rating = feedback.get("rating")
            if rating is not None:
                # Normalize 1-5 rating to -0.1..+0.1
                score += (float(rating) - 3.0) / 20.0

        # Factor 5: LLM-based evaluation (if available)
        if self.llm_router and trace:
            try:
                llm_score = await self._llm_evaluate(trace)
                score = score * 0.6 + llm_score * 0.4  # Weighted blend
            except Exception as exc:
                logger.debug(f"LLM evaluation failed: {exc}")

        # Clamp to [0, 1]
        score = max(0.0, min(1.0, score))

        # Store evaluation record
        eval_record = EvolutionRecord(
            task_id=record.task_id,
            stage=EvolutionStage.EVALUATE,
            input_data={"execution_id": execution_id, "feedback": feedback or {}},
            output_data={"score": score},
            score=score,
        )
        self._records.append(eval_record)
        self._task_records[record.task_id].append(eval_record.id)
        record.score = score

        logger.info(f"Evaluated execution {execution_id}: score={score:.3f}")
        return score

    async def optimize_strategy(self, execution_id: str, score: float) -> dict[str, Any]:
        """Stage 3 - Optimize: Adjust strategy based on evaluation.

        Analyzes the execution and suggests optimizations for:
        - Prompt adjustments
        - Tool selection changes
        - Workflow restructuring

        Args:
            execution_id: The execution record ID to optimize.
            score: The evaluation score for this execution.

        Returns:
            Optimization recommendations dict.
        """
        record = self._find_record(execution_id)
        if record is None:
            return {"error": "execution_not_found", "optimizations": []}

        trace = record.output_data
        optimizations: list[dict[str, str]] = []

        # Rule-based optimizations
        tool_calls = trace.get("tool_calls", [])
        if tool_calls:
            failed_tools = [
                tc.get("name", "unknown")
                for tc in tool_calls
                if isinstance(tc, dict) and tc.get("status") == "failed"
            ]
            if failed_tools:
                optimizations.append({
                    "type": "tool_selection",
                    "action": "avoid_or_retry",
                    "detail": f"Tools with failures: {', '.join(failed_tools)}. "
                              "Consider alternatives or add pre-validation.",
                })

        duration_ms = trace.get("duration_ms", 0)
        if duration_ms > 30000:
            optimizations.append({
                "type": "efficiency",
                "action": "reduce_steps",
                "detail": f"Execution took {duration_ms:.0f}ms. "
                          "Consider parallelizing independent steps or reducing iterations.",
            })

        if score < 0.5:
            optimizations.append({
                "type": "prompt",
                "action": "refine_instruction",
                "detail": "Low score suggests task instruction may need clarification "
                          "or decomposition into smaller subtasks.",
            })

        # LLM-based optimization suggestions
        if self.llm_router and score < 0.8:
            try:
                llm_opts = await self._llm_optimize(trace, score)
                optimizations.extend(llm_opts)
            except Exception as exc:
                logger.debug(f"LLM optimization failed: {exc}")

        result = {
            "execution_id": execution_id,
            "score": score,
            "optimizations": optimizations,
            "should_retry": score < 0.4,
            "suggested_approach": self._suggest_approach(score, trace),
        }

        # Store optimization record
        opt_record = EvolutionRecord(
            task_id=record.task_id,
            stage=EvolutionStage.OPTIMIZE,
            input_data={"execution_id": execution_id, "score": score},
            output_data=result,
            score=score,
        )
        self._records.append(opt_record)
        self._task_records[record.task_id].append(opt_record.id)
        self._optimization_history.append(result)

        logger.info(f"Optimized strategy for {execution_id}: {len(optimizations)} suggestions")
        return result

    async def distill_skill(self, execution_ids: list[str]) -> dict[str, Any]:
        """Stage 4 - Learn: Distill successful patterns into reusable skills.

        Analyzes multiple successful executions to extract common patterns
        and create a reusable skill definition.

        Args:
            execution_ids: List of execution record IDs to distill from.

        Returns:
            Distilled skill dict or error info.
        """
        if not execution_ids:
            return {"error": "no_executions_provided"}

        # Gather successful executions
        successful_traces: list[dict[str, Any]] = []
        for eid in execution_ids:
            record = self._find_record(eid)
            if record and record.stage == EvolutionStage.EXECUTE:
                status = record.output_data.get("status", "")
                if status in ("completed", "success") or (record.score and record.score >= 0.7):
                    successful_traces.append(record.output_data)

        if not successful_traces:
            return {"error": "no_successful_executions", "skill": None}

        # Extract common tool sequences
        tool_sequences = []
        for trace in successful_traces:
            tools = [
                tc.get("name", "")
                for tc in trace.get("tool_calls", [])
                if isinstance(tc, dict)
            ]
            if tools:
                tool_sequences.append(tools)

        common_tools = self._find_common_sequence(tool_sequences)

        # Generate skill definition
        skill = DistilledSkill(
            name=f"skill_{uuid4().hex[:8]}",
            description=f"Distilled from {len(successful_traces)} successful executions",
            pattern=self._describe_pattern(successful_traces),
            tool_sequence=common_tools,
            success_rate=len(successful_traces) / max(len(execution_ids), 1),
            source_execution_ids=execution_ids,
        )

        # LLM-based skill naming and description
        if self.llm_router:
            try:
                enhanced = await self._llm_distill(successful_traces, common_tools)
                skill.name = enhanced.get("name", skill.name)
                skill.description = enhanced.get("description", skill.description)
                skill.pattern = enhanced.get("pattern", skill.pattern)
            except Exception as exc:
                logger.debug(f"LLM skill distillation failed: {exc}")

        # Only keep skills above confidence threshold
        if skill.success_rate >= self._min_skill_confidence:
            self._skills.append(skill)
            logger.info(f"Distilled skill: {skill.name} (success_rate={skill.success_rate:.2f})")

        # Store learn record
        learn_record = EvolutionRecord(
            task_id=execution_ids[0] if execution_ids else "",
            stage=EvolutionStage.LEARN,
            input_data={"execution_ids": execution_ids},
            output_data=skill.to_dict(),
            score=skill.success_rate,
        )
        self._records.append(learn_record)

        return {"skill": skill.to_dict(), "promoted": skill.success_rate >= self._min_skill_confidence}

    async def get_evolution_history(self, limit: int = 50) -> list[EvolutionRecord]:
        """Get recent evolution records across all stages.

        Args:
            limit: Maximum number of records to return.

        Returns:
            List of EvolutionRecord, most recent first.
        """
        return list(reversed(self._records[-limit:]))

    async def trigger_evolution_cycle(self, task_id: str) -> dict[str, Any]:
        """Trigger a full evolution cycle for a task.

        Runs all four stages in sequence:
        Execute → Evaluate → Optimize → Learn

        Args:
            task_id: The task to run the evolution cycle for.

        Returns:
            Summary of the full evolution cycle.
        """
        record_ids = self._task_records.get(task_id, [])
        if not record_ids:
            return {"error": "no_records_for_task", "task_id": task_id}

        # Find the execute record
        execute_record = None
        for rid in record_ids:
            record = self._find_record(rid)
            if record and record.stage == EvolutionStage.EXECUTE:
                execute_record = record
                break

        if execute_record is None:
            return {"error": "no_execution_record", "task_id": task_id}

        # Stage 2: Evaluate
        score = await self.evaluate_execution(execute_record.id)

        # Stage 3: Optimize
        optimization = await self.optimize_strategy(execute_record.id, score)

        # Stage 4: Learn (only if score is good enough)
        skill_result: dict[str, Any] = {"skill": None, "promoted": False}
        if score >= self._min_skill_confidence:
            skill_result = await self.distill_skill([execute_record.id])

        return {
            "task_id": task_id,
            "execution_id": execute_record.id,
            "score": score,
            "optimization": optimization,
            "skill_distilled": skill_result.get("promoted", False),
            "skill": skill_result.get("skill"),
            "cycle_complete": True,
        }

    def get_stats(self) -> dict[str, Any]:
        """Get engine statistics."""
        stage_counts = defaultdict(int)
        for r in self._records:
            stage_counts[r.stage.value] += 1

        scores = [r.score for r in self._records if r.score is not None]
        avg_score = sum(scores) / len(scores) if scores else 0.0

        return {
            "total_records": len(self._records),
            "stage_counts": dict(stage_counts),
            "distilled_skills": len(self._skills),
            "skill_names": [s.name for s in self._skills],
            "average_score": round(avg_score, 3),
            "optimizations_applied": len(self._optimization_history),
        }

    # ─── Internal helpers ─────────────────────────────────────────────────────

    def _find_record(self, record_id: str) -> EvolutionRecord | None:
        """Find a record by ID."""
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def _suggest_approach(self, score: float, trace: dict[str, Any]) -> str:
        """Suggest an approach based on score and trace."""
        if score >= 0.8:
            return "current_approach_effective"
        if score >= 0.5:
            return "minor_adjustments_needed"
        if trace.get("tool_calls"):
            return "try_alternative_tools"
        return "decompose_task_further"

    def _find_common_sequence(self, sequences: list[list[str]]) -> list[str]:
        """Find the most common tool sequence pattern."""
        if not sequences:
            return []
        # Use the longest common subsequence approach (simplified)
        from collections import Counter

        # Count tool frequency across all sequences
        tool_freq: Counter[str] = Counter()
        for seq in sequences:
            tool_freq.update(set(seq))  # Count presence, not repetition

        # Return tools that appear in >50% of sequences, in order of first appearance
        threshold = len(sequences) / 2
        common = [t for t, c in tool_freq.items() if c > threshold]

        # Order by first appearance in the first sequence
        if sequences:
            first_seq = sequences[0]
            common.sort(key=lambda t: first_seq.index(t) if t in first_seq else 999)

        return common

    @staticmethod
    def _describe_pattern(traces: list[dict[str, Any]]) -> str:
        """Generate a human-readable pattern description."""
        if not traces:
            return ""
        statuses = [t.get("status", "unknown") for t in traces]
        tool_counts = [len(t.get("tool_calls", [])) for t in traces]
        avg_tools = sum(tool_counts) / len(tool_counts) if tool_counts else 0
        return (
            f"Pattern from {len(traces)} executions. "
            f"Avg tool calls: {avg_tools:.1f}. "
            f"Success statuses: {statuses.count('completed')}/{len(statuses)}."
        )

    async def _llm_evaluate(self, trace: dict[str, Any]) -> float:
        """Use LLM to evaluate execution quality."""
        prompt = (
            "Rate the quality of this agent execution on a scale of 0.0 to 1.0.\n\n"
            f"Status: {trace.get('status', 'unknown')}\n"
            f"Tool calls: {len(trace.get('tool_calls', []))}\n"
            f"Output length: {len(str(trace.get('output', '')))}\n"
            f"Errors: {trace.get('errors', [])}\n\n"
            "Respond with ONLY a JSON object: {\"score\": float}"
        )
        messages = [{"role": "user", "content": prompt}]
        response = await self.llm_router.chat(messages, tools=[])
        content = response.content if hasattr(response, "content") else str(response)
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(content[start:end])
            return max(0.0, min(1.0, float(data.get("score", 0.5))))
        return 0.5

    async def _llm_optimize(self, trace: dict[str, Any], score: float) -> list[dict[str, str]]:
        """Use LLM to suggest optimizations."""
        prompt = (
            f"This agent execution scored {score:.2f}/1.0. Suggest optimizations.\n\n"
            f"Tool calls: {json.dumps(trace.get('tool_calls', [])[:5], default=str)}\n"
            f"Status: {trace.get('status')}\n\n"
            "Return a JSON array of optimizations: "
            "[{\"type\": str, \"action\": str, \"detail\": str}]"
        )
        messages = [{"role": "user", "content": prompt}]
        response = await self.llm_router.chat(messages, tools=[])
        content = response.content if hasattr(response, "content") else str(response)
        start = content.find("[")
        end = content.rfind("]") + 1
        if start >= 0 and end > start:
            items = json.loads(content[start:end])
            return [item for item in items if isinstance(item, dict)]
        return []

    async def _llm_distill(
        self,
        traces: list[dict[str, Any]],
        common_tools: list[str],
    ) -> dict[str, str]:
        """Use LLM to name and describe a distilled skill."""
        prompt = (
            f"Based on {len(traces)} successful agent executions with common tools "
            f"{common_tools}, generate a skill definition.\n\n"
            "Return JSON: {\"name\": str, \"description\": str, \"pattern\": str}"
        )
        messages = [{"role": "user", "content": prompt}]
        response = await self.llm_router.chat(messages, tools=[])
        content = response.content if hasattr(response, "content") else str(response)
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(content[start:end])
        return {}


# Global singleton
self_evolution_engine = SelfEvolutionEngine()
