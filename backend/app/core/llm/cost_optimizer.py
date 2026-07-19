"""Cost optimization and tracking for LLM usage."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import json


@dataclass
class TokenEstimate:
    """Estimate of token usage for a request."""

    input_tokens: int
    output_tokens: int
    confidence: float = 0.8  # 0-1, how confident we are


class TokenEstimator:
    """Estimate token usage based on text length and model."""

    # Rough estimates: 1 token ≈ 4 characters for English
    CHARS_PER_TOKEN = 4.0

    @staticmethod
    def estimate_input_tokens(text: str) -> int:
        """Estimate input tokens from text."""
        return max(1, int(len(text) / TokenEstimator.CHARS_PER_TOKEN))

    @staticmethod
    def estimate_output_tokens(
        expected_length: str = "medium",
        task_type: str = "general"
    ) -> int:
        """Estimate output tokens based on expected length."""
        estimates = {
            "short": 50,
            "medium": 200,
            "long": 500,
            "very_long": 2000,
        }

        base = estimates.get(expected_length, 200)

        # Adjust for task type
        task_multipliers = {
            "code_generation": 1.5,
            "analysis": 1.3,
            "creative": 1.2,
            "simple_qa": 0.8,
        }

        multiplier = task_multipliers.get(task_type, 1.0)
        return int(base * multiplier)

    @staticmethod
    def estimate_from_prompt(
        system_prompt: str,
        user_message: str,
        expected_output: str = "medium"
    ) -> TokenEstimate:
        """Estimate tokens for a complete prompt."""
        input_tokens = (
            TokenEstimator.estimate_input_tokens(system_prompt) +
            TokenEstimator.estimate_input_tokens(user_message)
        )
        output_tokens = TokenEstimator.estimate_output_tokens(expected_output)

        return TokenEstimate(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            confidence=0.75,
        )


@dataclass
class CostRecord:
    """Record of a single LLM API call cost."""

    timestamp: datetime
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    success: bool
    latency_ms: float
    task_type: str = "unknown"
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CostBudget:
    """Cost budget configuration."""

    total_budget_usd: float
    period_days: int = 1
    alert_threshold_percent: float = 80.0  # Alert when 80% spent
    hard_limit: bool = False  # Reject requests over budget if True


class CostTracker:
    """Track and analyze LLM usage costs."""

    def __init__(self):
        """Initialize cost tracker."""
        self.records: list[CostRecord] = []
        self.budgets: dict[str, CostBudget] = {}
        self._alerts: list[dict[str, Any]] = []

    def record_call(
        self,
        model: str,
        provider: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        success: bool,
        latency_ms: float,
        task_type: str = "unknown",
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Record an LLM API call."""
        record = CostRecord(
            timestamp=datetime.now(),
            model=model,
            provider=provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            success=success,
            latency_ms=latency_ms,
            task_type=task_type,
            user_id=user_id,
            session_id=session_id,
            metadata=metadata or {},
        )

        self.records.append(record)

        # Check budget alerts
        self._check_budget_alerts()

    def set_budget(self, budget_name: str, budget: CostBudget) -> None:
        """Set a cost budget."""
        self.budgets[budget_name] = budget

    def get_total_cost(self, hours: int = 24) -> float:
        """Get total cost in the last N hours."""
        cutoff = datetime.now() - timedelta(hours=hours)
        return sum(
            r.cost_usd for r in self.records
            if r.timestamp > cutoff
        )

    def get_cost_by_model(self, hours: int = 24) -> dict[str, float]:
        """Get cost breakdown by model."""
        cutoff = datetime.now() - timedelta(hours=hours)
        costs = defaultdict(float)

        for record in self.records:
            if record.timestamp > cutoff:
                costs[record.model] += record.cost_usd

        return dict(costs)

    def get_cost_by_provider(self, hours: int = 24) -> dict[str, float]:
        """Get cost breakdown by provider."""
        cutoff = datetime.now() - timedelta(hours=hours)
        costs = defaultdict(float)

        for record in self.records:
            if record.timestamp > cutoff:
                costs[record.provider] += record.cost_usd

        return dict(costs)

    def get_cost_by_task_type(self, hours: int = 24) -> dict[str, float]:
        """Get cost breakdown by task type."""
        cutoff = datetime.now() - timedelta(hours=hours)
        costs = defaultdict(float)

        for record in self.records:
            if record.timestamp > cutoff:
                costs[record.task_type] += record.cost_usd

        return dict(costs)

    def get_cost_by_user(self, hours: int = 24) -> dict[str, float]:
        """Get cost breakdown by user."""
        cutoff = datetime.now() - timedelta(hours=hours)
        costs = defaultdict(float)

        for record in self.records:
            if record.timestamp > cutoff and record.user_id:
                costs[record.user_id] += record.cost_usd

        return dict(costs)

    def get_success_rate(self, hours: int = 24) -> float:
        """Get success rate of API calls."""
        cutoff = datetime.now() - timedelta(hours=hours)
        recent = [r for r in self.records if r.timestamp > cutoff]

        if not recent:
            return 1.0

        success_count = sum(1 for r in recent if r.success)
        return success_count / len(recent)

    def get_average_latency(self, hours: int = 24) -> float:
        """Get average latency of API calls."""
        cutoff = datetime.now() - timedelta(hours=hours)
        recent = [r for r in self.records if r.timestamp > cutoff]

        if not recent:
            return 0.0

        return sum(r.latency_ms for r in recent) / len(recent)

    def get_token_efficiency(self, hours: int = 24) -> dict[str, float]:
        """Get token efficiency (cost per token) by model."""
        cutoff = datetime.now() - timedelta(hours=hours)
        efficiency = defaultdict(lambda: {"cost": 0.0, "tokens": 0})

        for record in self.records:
            if record.timestamp > cutoff:
                total_tokens = record.input_tokens + record.output_tokens
                efficiency[record.model]["cost"] += record.cost_usd
                efficiency[record.model]["tokens"] += total_tokens

        result = {}
        for model, data in efficiency.items():
            if data["tokens"] > 0:
                result[model] = data["cost"] / data["tokens"] * 1000  # Cost per 1K tokens

        return result

    def _check_budget_alerts(self) -> None:
        """Check if any budgets have been exceeded."""
        for budget_name, budget in self.budgets.items():
            current_cost = self.get_total_cost(hours=budget.period_days * 24)
            spent_percent = (current_cost / budget.total_budget_usd) * 100

            if spent_percent >= budget.alert_threshold_percent:
                alert = {
                    "timestamp": datetime.now(),
                    "budget_name": budget_name,
                    "spent_usd": current_cost,
                    "budget_usd": budget.total_budget_usd,
                    "spent_percent": spent_percent,
                    "severity": "warning" if spent_percent < 100 else "critical",
                }
                self._alerts.append(alert)

    def get_alerts(self, hours: int = 24) -> list[dict[str, Any]]:
        """Get recent alerts."""
        cutoff = datetime.now() - timedelta(hours=hours)
        return [a for a in self._alerts if a["timestamp"] > cutoff]

    def get_report(self, hours: int = 24) -> dict[str, Any]:
        """Get comprehensive cost report."""
        return {
            "period_hours": hours,
            "total_cost_usd": self.get_total_cost(hours),
            "cost_by_model": self.get_cost_by_model(hours),
            "cost_by_provider": self.get_cost_by_provider(hours),
            "cost_by_task_type": self.get_cost_by_task_type(hours),
            "cost_by_user": self.get_cost_by_user(hours),
            "success_rate": self.get_success_rate(hours),
            "average_latency_ms": self.get_average_latency(hours),
            "token_efficiency": self.get_token_efficiency(hours),
            "alerts": self.get_alerts(hours),
        }


class CostOptimizer:
    """Optimize costs through intelligent model selection and request batching."""

    def __init__(self, tracker: CostTracker):
        """Initialize cost optimizer."""
        self.tracker = tracker
        self._request_queue: list[dict[str, Any]] = []
        self._batch_size = 10
        self._batch_timeout_ms = 5000

    def should_batch_request(self, request: dict[str, Any]) -> bool:
        """Determine if a request should be batched."""
        # Don't batch if:
        # - Request is urgent (low latency requirement)
        # - Request is high priority
        # - Queue is empty

        if request.get("urgent", False):
            return False

        if request.get("priority", "normal") == "high":
            return False

        return len(self._request_queue) > 0

    def estimate_cost_savings(
        self,
        current_model: str,
        alternative_model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> dict[str, Any]:
        """Estimate cost savings by switching models."""
        # This would need access to model pricing
        # For now, return placeholder
        return {
            "current_model": current_model,
            "alternative_model": alternative_model,
            "estimated_savings_percent": 0.0,
            "estimated_savings_usd": 0.0,
        }

    def get_cost_optimization_recommendations(
        self,
        hours: int = 24
    ) -> list[dict[str, Any]]:
        """Get recommendations for cost optimization."""
        recommendations = []

        # Analyze cost by model
        cost_by_model = self.tracker.get_cost_by_model(hours)
        if cost_by_model:
            most_expensive = max(cost_by_model.items(), key=lambda x: x[1])
            recommendations.append({
                "type": "model_switch",
                "description": f"Consider switching from {most_expensive[0]} to cheaper alternatives",
                "potential_savings_usd": most_expensive[1] * 0.3,  # Estimate 30% savings
            })

        # Analyze success rate
        success_rate = self.tracker.get_success_rate(hours)
        if success_rate < 0.95:
            recommendations.append({
                "type": "reliability",
                "description": f"Success rate is {success_rate*100:.1f}%, consider using more reliable models",
                "potential_savings_usd": 0.0,
            })

        # Analyze token efficiency
        efficiency = self.tracker.get_token_efficiency(hours)
        if efficiency:
            most_expensive_model = max(efficiency.items(), key=lambda x: x[1])
            recommendations.append({
                "type": "prompt_optimization",
                "description": f"Optimize prompts for {most_expensive_model[0]} to reduce token usage",
                "potential_savings_usd": 0.0,
            })

        return recommendations
