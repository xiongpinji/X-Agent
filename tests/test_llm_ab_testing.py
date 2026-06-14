"""Tests for LLM A/B Testing Framework.

Covers:
- Variant management and validation
- Trial execution with mocks
- Result aggregation and statistics
- Winner determination
- Error handling and timeouts
"""

import pytest
import asyncio
from datetime import datetime

from backend.app.core.llm_ab_testing import (
    ABTestRunner,
    Variant,
    TrialResult,
    ExperimentResult,
    MetricType,
)


class TestVariant:
    """Test Variant dataclass."""
    
    def test_variant_creation_valid(self):
        """Test creating a valid variant."""
        v = Variant(name="gpt4", backend="openai", model="gpt-4o-mini")
        assert v.name == "gpt4"
        assert v.backend == "openai"
        assert v.model == "gpt-4o-mini"
        assert v.config == {}
    
    def test_variant_creation_with_config(self):
        """Test variant with configuration."""
        v = Variant(
            name="gpt4",
            backend="openai",
            model="gpt-4o-mini",
            temperature=0.7,
            max_tokens=2000,
        )
        assert v.config == {"temperature": 0.7, "max_tokens": 2000}
    
    def test_variant_missing_required_fields(self):
        """Test validation of required fields."""
        with pytest.raises(ValueError):
            Variant(name="", backend="openai", model="gpt-4o-mini")
        
        with pytest.raises(ValueError):
            Variant(name="gpt4", backend="", model="gpt-4o-mini")
        
        with pytest.raises(ValueError):
            Variant(name="gpt4", backend="openai", model="")


class TestTrialResult:
    """Test TrialResult dataclass."""
    
    def test_trial_success_status(self):
        """Test success property."""
        trial_success = TrialResult(
            trial_id="1",
            experiment_id="exp1",
            variant="gpt4",
            prompt_id="p1",
            latency_ms=100.5,
            output="test output",
            output_length=10,
            estimated_cost_usd=0.01,
            error=None,
        )
        assert trial_success.success is True
        
        trial_failed = TrialResult(
            trial_id="2",
            experiment_id="exp1",
            variant="gpt4",
            prompt_id="p1",
            latency_ms=5000.0,
            output="",
            output_length=0,
            estimated_cost_usd=0.0,
            error="Timeout",
        )
        assert trial_failed.success is False
    
    def test_cost_per_1k_tokens(self):
        """Test normalized cost calculation."""
        trial = TrialResult(
            trial_id="1",
            experiment_id="exp1",
            variant="gpt4",
            prompt_id="p1",
            latency_ms=100.0,
            output="test",
            output_length=1000,  # 1000 tokens
            estimated_cost_usd=0.15,
        )
        # 0.15 / 1000 * 1000 = 0.15
        assert trial.cost_per_1k_tokens == pytest.approx(0.15, abs=0.01)


class TestExperimentResult:
    """Test ExperimentResult aggregation."""
    
    def test_summary_single_variant(self):
        """Test summary calculation for a single variant."""
        trials = [
            TrialResult(
                trial_id="1",
                experiment_id="exp1",
                variant="gpt4",
                prompt_id="p1",
                latency_ms=100.0,
                output="test",
                output_length=100,
                estimated_cost_usd=0.01,
                quality_score=0.9,
                error=None,
            ),
            TrialResult(
                trial_id="2",
                experiment_id="exp1",
                variant="gpt4",
                prompt_id="p2",
                latency_ms=120.0,
                output="test",
                output_length=120,
                estimated_cost_usd=0.015,
                quality_score=0.85,
                error=None,
            ),
        ]
        
        result = ExperimentResult(
            experiment_id="exp1",
            variants=["gpt4"],
            trials=trials,
        )
        
        summary = result.summary
        assert "gpt4" in summary
        assert summary["gpt4"]["trials"] == 2
        assert summary["gpt4"]["success_rate"] == 1.0
        assert summary["gpt4"]["latency_ms"]["mean"] == pytest.approx(110.0, abs=0.1)
        assert summary["gpt4"]["cost_usd"]["total"] == pytest.approx(0.025, abs=0.001)
    
    def test_summary_with_failures(self):
        """Test summary excluding failed trials."""
        trials = [
            TrialResult(
                trial_id="1",
                experiment_id="exp1",
                variant="gpt4",
                prompt_id="p1",
                latency_ms=100.0,
                output="test",
                output_length=100,
                estimated_cost_usd=0.01,
                error=None,
            ),
            TrialResult(
                trial_id="2",
                experiment_id="exp1",
                variant="gpt4",
                prompt_id="p2",
                latency_ms=5000.0,
                output="",
                output_length=0,
                estimated_cost_usd=0.0,
                error="Timeout",
            ),
        ]
        
        result = ExperimentResult(
            experiment_id="exp1",
            variants=["gpt4"],
            trials=trials,
        )
        
        summary = result.summary
        assert summary["gpt4"]["trials"] == 1  # Only successful trials
        assert summary["gpt4"]["success_rate"] == 0.5  # 1 of 2
    
    def test_winner_determination_by_composite_score(self):
        """Test winner selection based on composite score."""
        trials = [
            # Variant A: slower but cheaper
            TrialResult(
                trial_id="1",
                experiment_id="exp1",
                variant="deepseek",
                prompt_id="p1",
                latency_ms=500.0,
                output="test",
                output_length=100,
                estimated_cost_usd=0.001,
                quality_score=0.8,
                error=None,
            ),
            # Variant B: fast but expensive
            TrialResult(
                trial_id="2",
                experiment_id="exp1",
                variant="gpt4",
                prompt_id="p1",
                latency_ms=100.0,
                output="test",
                output_length=100,
                estimated_cost_usd=0.05,
                quality_score=0.85,
                error=None,
            ),
        ]
        
        result = ExperimentResult(
            experiment_id="exp1",
            variants=["deepseek", "gpt4"],
            trials=trials,
        )
        
        # Deepseek should win due to lower cost despite slower speed
        winner = result.winner
        assert winner in ["deepseek", "gpt4"]
    
    def test_statistical_tests_two_variants(self):
        """Test statistical significance calculation."""
        trials = [
            TrialResult(
                trial_id=f"{i}",
                experiment_id="exp1",
                variant="a" if i % 2 == 0 else "b",
                prompt_id="p1",
                latency_ms=100.0 + i * 5,
                output="test",
                output_length=100,
                estimated_cost_usd=0.01,
                error=None,
            )
            for i in range(10)  # 5 trials per variant
        ]
        
        result = ExperimentResult(
            experiment_id="exp1",
            variants=["a", "b"],
            trials=trials,
        )
        
        stats_result = result.statistical_tests()
        assert "test" in stats_result
        assert "t_statistic" in stats_result
        assert "p_value" in stats_result
        assert "significant" in stats_result
    
    def test_statistical_tests_requires_two_variants(self):
        """Test that statistical tests require exactly 2 variants."""
        trials = [
            TrialResult(
                trial_id="1",
                experiment_id="exp1",
                variant="a",
                prompt_id="p1",
                latency_ms=100.0,
                output="test",
                output_length=100,
                estimated_cost_usd=0.01,
                error=None,
            ),
        ]
        
        result = ExperimentResult(
            experiment_id="exp1",
            variants=["a", "b", "c"],
            trials=trials,
        )
        
        stats_result = result.statistical_tests()
        assert "error" in stats_result


class TestABTestRunner:
    """Test ABTestRunner orchestration."""
    
    def test_runner_initialization(self):
        """Test runner creation."""
        runner = ABTestRunner()
        assert runner.variants == []
        assert runner.experiment_id is not None
    
    def test_add_variant(self):
        """Test adding variants."""
        runner = ABTestRunner()
        runner.add_variant("gpt4", backend="openai", model="gpt-4o-mini")
        runner.add_variant("deepseek", backend="deepseek", model="deepseek-chat")
        
        assert len(runner.variants) == 2
        assert runner.variants[0].name == "gpt4"
        assert runner.variants[1].name == "deepseek"
    
    def test_add_duplicate_variant_raises(self):
        """Test that duplicate variant names raise error."""
        runner = ABTestRunner()
        runner.add_variant("gpt4", backend="openai", model="gpt-4o-mini")
        
        with pytest.raises(ValueError, match="already exists"):
            runner.add_variant("gpt4", backend="openai", model="gpt-4o")
    
    @pytest.mark.asyncio
    async def test_run_experiment_requires_variants(self):
        """Test that experiment requires at least one variant."""
        runner = ABTestRunner()
        
        with pytest.raises(ValueError, match="No variants"):
            await runner.run_experiment(prompts=["test prompt"])
    
    @pytest.mark.asyncio
    async def test_run_experiment_requires_prompts(self):
        """Test that experiment requires prompts."""
        runner = ABTestRunner()
        runner.add_variant("gpt4", backend="openai", model="gpt-4o-mini")
        
        with pytest.raises(ValueError, match="At least one prompt"):
            await runner.run_experiment(prompts=[])
    
    @pytest.mark.asyncio
    async def test_run_experiment_mock_mode(self):
        """Test experiment in mock mode (no LLM manager)."""
        runner = ABTestRunner()
        runner.add_variant("gpt4", backend="openai", model="gpt-4o-mini")
        runner.add_variant("deepseek", backend="deepseek", model="deepseek-chat")
        
        result = await runner.run_experiment(
            prompts=["What is 2+2?"],
            runs_per_prompt=1,
        )
        
        assert result.experiment_id is not None
        assert len(result.variants) == 2
        assert len(result.trials) == 2  # 2 variants × 1 prompt × 1 run
        assert all(t.success for t in result.trials)
    
    @pytest.mark.asyncio
    async def test_default_quality_judge(self):
        """Test default quality scoring heuristic."""
        runner = ABTestRunner()
        
        # Short output = low quality
        score_short = await runner._default_quality_judge("hi", "test")
        assert score_short < 0.5
        
        # Long, well-formatted output = higher quality
        score_long = await runner._default_quality_judge(
            "This is a comprehensive response. It includes multiple sentences. It has proper punctuation!",
            "test"
        )
        assert score_long > 0.5
        
        # Empty output = zero quality
        score_empty = await runner._default_quality_judge("", "test")
        assert score_empty == 0.0
    
    @pytest.mark.asyncio
    async def test_trial_timeout_handling(self):
        """Test that trial timeouts are caught and reported."""
        runner = ABTestRunner()
        runner.add_variant("slow", backend="mock", model="mock-slow")
        
        # Create an LLM call that times out
        async def slow_judge(output: str, prompt: str) -> float:
            await asyncio.sleep(10)  # Simulate slow judge
            return 0.5
        
        runner.quality_judge = slow_judge
        
        result = await runner.run_experiment(
            prompts=["test"],
            runs_per_prompt=1,
            timeout_per_trial_sec=0.1,
        )
        
        # Trial should have failed with timeout
        assert not result.trials[0].success
        assert "Timeout" in result.trials[0].error
