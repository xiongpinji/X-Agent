"""LLM evaluation system for assessing response quality and correctness."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class EvaluationMetric(StrEnum):
    """Types of evaluation metrics."""
    ACCURACY = "accuracy"
    RELEVANCE = "relevance"
    COHERENCE = "coherence"
    COMPLETENESS = "completeness"
    SAFETY = "safety"
    FACTUALITY = "factuality"
    FLUENCY = "fluency"
    TOXICITY = "toxicity"


class EvaluationMethod(StrEnum):
    """Methods for evaluation."""
    HUMAN = "human"
    AUTOMATED = "automated"
    HYBRID = "hybrid"


class EvaluationScore(BaseModel):
    """Score for a single evaluation metric."""

    metric: EvaluationMetric
    score: float  # 0.0 to 1.0
    confidence: float = 0.0  # 0.0 to 1.0
    reasoning: str = ""
    evaluator_id: str | None = None


class LLMResponse(BaseModel):
    """An LLM response to be evaluated."""

    response_id: str = Field(default_factory=lambda: str(uuid4()))
    prompt: str
    response: str
    model_name: str
    provider: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class Evaluation(BaseModel):
    """Evaluation of an LLM response."""

    evaluation_id: str = Field(default_factory=lambda: str(uuid4()))
    response_id: str
    method: EvaluationMethod
    scores: list[EvaluationScore] = Field(default_factory=list)
    overall_score: float = 0.0
    feedback: str = ""
    evaluator_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    def calculate_overall_score(self) -> float:
        """Calculate overall score from individual metrics."""
        if not self.scores:
            return 0.0
        total = sum(s.score for s in self.scores)
        self.overall_score = total / len(self.scores)
        return self.overall_score

    def add_score(
        self,
        metric: EvaluationMetric,
        score: float,
        confidence: float = 0.0,
        reasoning: str = "",
        evaluator_id: str | None = None,
    ) -> None:
        """Add a score for a metric."""
        eval_score = EvaluationScore(
            metric=metric,
            score=score,
            confidence=confidence,
            reasoning=reasoning,
            evaluator_id=evaluator_id,
        )
        self.scores.append(eval_score)
        self.calculate_overall_score()


class EvaluationDataset(BaseModel):
    """Dataset for evaluation."""

    dataset_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str = ""
    size: int = 0
    test_cases: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    def add_test_case(self, prompt: str, expected_output: str, metadata: dict[str, Any] | None = None) -> None:
        """Add a test case to the dataset."""
        self.test_cases.append(
            {
                "prompt": prompt,
                "expected_output": expected_output,
                "metadata": metadata or {},
            }
        )
        self.size = len(self.test_cases)


class EvaluationRun(BaseModel):
    """A run of evaluations on a dataset."""

    run_id: str = Field(default_factory=lambda: str(uuid4()))
    dataset_id: str
    model_name: str
    provider: str
    evaluations: list[Evaluation] = Field(default_factory=list)
    status: str = "running"  # running, completed, failed
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    metrics_summary: dict[str, float] = Field(default_factory=dict)


class LLMEvaluation:
    """Main LLM evaluation system."""

    def __init__(self, storage_path: str | Path | None = None) -> None:
        self._responses: dict[str, LLMResponse] = {}
        self._evaluations: dict[str, list[Evaluation]] = {}
        self._datasets: dict[str, EvaluationDataset] = {}
        self._runs: dict[str, EvaluationRun] = {}
        self._storage_path = Path(storage_path) if storage_path else None
        if self._storage_path:
            self._load_from_disk()

    def record_response(
        self,
        prompt: str,
        response: str,
        model_name: str,
        provider: str,
        metadata: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Record an LLM response."""
        llm_response = LLMResponse(
            prompt=prompt,
            response=response,
            model_name=model_name,
            provider=provider,
            metadata=metadata or {},
        )
        self._responses[llm_response.response_id] = llm_response
        self._save_to_disk()
        return llm_response

    def get_response(self, response_id: str) -> LLMResponse | None:
        """Get a response by ID."""
        return self._responses.get(response_id)

    def evaluate_response(
        self,
        response_id: str,
        method: EvaluationMethod = EvaluationMethod.AUTOMATED,
        evaluator_id: str | None = None,
    ) -> Evaluation | None:
        """Evaluate a response."""
        response = self._responses.get(response_id)
        if not response:
            return None

        evaluation = Evaluation(
            response_id=response_id,
            method=method,
            evaluator_id=evaluator_id,
        )

        # Run automated evaluations
        if method in (EvaluationMethod.AUTOMATED, EvaluationMethod.HYBRID):
            self._run_automated_evaluation(response, evaluation)

        if response_id not in self._evaluations:
            self._evaluations[response_id] = []
        self._evaluations[response_id].append(evaluation)

        self._save_to_disk()
        return evaluation

    def get_evaluations(self, response_id: str) -> list[Evaluation]:
        """Get all evaluations for a response."""
        return self._evaluations.get(response_id, [])

    def create_dataset(
        self,
        name: str,
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> EvaluationDataset:
        """Create an evaluation dataset."""
        dataset = EvaluationDataset(
            name=name,
            description=description,
            metadata=metadata or {},
        )
        self._datasets[dataset.dataset_id] = dataset
        self._save_to_disk()
        return dataset

    def get_dataset(self, dataset_id: str) -> EvaluationDataset | None:
        """Get a dataset by ID."""
        return self._datasets.get(dataset_id)

    def list_datasets(self) -> list[EvaluationDataset]:
        """List all datasets."""
        return list(self._datasets.values())

    def add_test_case(
        self,
        dataset_id: str,
        prompt: str,
        expected_output: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Add a test case to a dataset."""
        dataset = self._datasets.get(dataset_id)
        if not dataset:
            return False
        dataset.add_test_case(prompt, expected_output, metadata)
        self._save_to_disk()
        return True

    def create_evaluation_run(
        self,
        dataset_id: str,
        model_name: str,
        provider: str,
    ) -> EvaluationRun | None:
        """Create an evaluation run."""
        dataset = self._datasets.get(dataset_id)
        if not dataset:
            return None

        run = EvaluationRun(
            dataset_id=dataset_id,
            model_name=model_name,
            provider=provider,
        )
        self._runs[run.run_id] = run
        self._save_to_disk()
        return run

    def get_run(self, run_id: str) -> EvaluationRun | None:
        """Get an evaluation run by ID."""
        return self._runs.get(run_id)

    def list_runs(self, dataset_id: str | None = None) -> list[EvaluationRun]:
        """List evaluation runs."""
        runs = list(self._runs.values())
        if dataset_id:
            runs = [r for r in runs if r.dataset_id == dataset_id]
        return runs

    def add_evaluation_to_run(self, run_id: str, evaluation: Evaluation) -> bool:
        """Add an evaluation to a run."""
        run = self._runs.get(run_id)
        if not run:
            return False
        run.evaluations.append(evaluation)
        self._save_to_disk()
        return True

    def complete_run(self, run_id: str) -> EvaluationRun | None:
        """Mark a run as completed and calculate summary metrics."""
        run = self._runs.get(run_id)
        if not run:
            return None

        run.status = "completed"
        run.completed_at = datetime.now(UTC)

        # Calculate summary metrics
        if run.evaluations:
            metrics_by_type = {}
            for evaluation in run.evaluations:
                for score in evaluation.scores:
                    metric_name = score.metric.value
                    if metric_name not in metrics_by_type:
                        metrics_by_type[metric_name] = []
                    metrics_by_type[metric_name].append(score.score)

            for metric_name, scores in metrics_by_type.items():
                run.metrics_summary[metric_name] = sum(scores) / len(scores)

            # Overall score
            all_scores = [s for scores in metrics_by_type.values() for s in scores]
            if all_scores:
                run.metrics_summary["overall"] = sum(all_scores) / len(all_scores)

        self._save_to_disk()
        return run

    def get_evaluation_report(self, run_id: str) -> dict[str, Any]:
        """Get a report for an evaluation run."""
        run = self._runs.get(run_id)
        if not run:
            return {}

        return {
            "run_id": run.run_id,
            "dataset_id": run.dataset_id,
            "model_name": run.model_name,
            "provider": run.provider,
            "status": run.status,
            "total_evaluations": len(run.evaluations),
            "metrics_summary": run.metrics_summary,
            "started_at": run.started_at.isoformat(),
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        }

    def _run_automated_evaluation(self, response: LLMResponse, evaluation: Evaluation) -> None:
        """Run automated evaluation on a response."""
        # Evaluate relevance
        relevance_score = self._evaluate_relevance(response.prompt, response.response)
        evaluation.add_score(
            EvaluationMetric.RELEVANCE,
            relevance_score,
            confidence=0.8,
            reasoning="Based on keyword overlap and semantic similarity",
        )

        # Evaluate coherence
        coherence_score = self._evaluate_coherence(response.response)
        evaluation.add_score(
            EvaluationMetric.COHERENCE,
            coherence_score,
            confidence=0.7,
            reasoning="Based on sentence structure and flow",
        )

        # Evaluate completeness
        completeness_score = self._evaluate_completeness(response.response)
        evaluation.add_score(
            EvaluationMetric.COMPLETENESS,
            completeness_score,
            confidence=0.6,
            reasoning="Based on response length and detail",
        )

        # Evaluate safety
        safety_score = self._evaluate_safety(response.response)
        evaluation.add_score(
            EvaluationMetric.SAFETY,
            safety_score,
            confidence=0.9,
            reasoning="Based on content filtering",
        )

        # Evaluate fluency
        fluency_score = self._evaluate_fluency(response.response)
        evaluation.add_score(
            EvaluationMetric.FLUENCY,
            fluency_score,
            confidence=0.75,
            reasoning="Based on language quality",
        )

        evaluation.calculate_overall_score()

    def _evaluate_relevance(self, prompt: str, response: str) -> float:
        """Evaluate relevance of response to prompt."""
        # Simple keyword overlap
        prompt_words = set(prompt.lower().split())
        response_words = set(response.lower().split())
        overlap = len(prompt_words & response_words)
        total = len(prompt_words | response_words)
        return min(overlap / max(total, 1), 1.0)

    def _evaluate_coherence(self, response: str) -> float:
        """Evaluate coherence of response."""
        # Simple heuristic: check for sentence structure
        sentences = response.split(".")
        if len(sentences) < 2:
            return 0.5
        # More sentences = better coherence (up to a point)
        return min(len(sentences) / 10, 1.0)

    def _evaluate_completeness(self, response: str) -> float:
        """Evaluate completeness of response."""
        # Simple heuristic: based on length
        words = len(response.split())
        if words < 10:
            return 0.3
        elif words < 50:
            return 0.6
        elif words < 200:
            return 0.85
        else:
            return 1.0

    def _evaluate_safety(self, response: str) -> float:
        """Evaluate safety of response."""
        # Simple heuristic: check for harmful keywords
        harmful_keywords = ["kill", "harm", "illegal", "dangerous"]
        response_lower = response.lower()
        for keyword in harmful_keywords:
            if keyword in response_lower:
                return 0.2
        return 0.95

    def _evaluate_fluency(self, response: str) -> float:
        """Evaluate fluency of response."""
        # Simple heuristic: check for common language patterns
        words = response.split()
        if len(words) < 5:
            return 0.4
        # Check for variety in word length
        word_lengths = [len(w) for w in words]
        avg_length = sum(word_lengths) / len(word_lengths)
        if 4 < avg_length < 8:
            return 0.9
        return 0.7

    def _save_to_disk(self) -> None:
        """Save all data to disk."""
        if self._storage_path is None:
            return

        self._storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Save responses
        responses_file = self._storage_path.parent / "responses.jsonl"
        with responses_file.open("w", encoding="utf-8") as f:
            for response in self._responses.values():
                f.write(response.model_dump_json() + "\n")

        # Save evaluations
        evaluations_file = self._storage_path.parent / "evaluations.jsonl"
        with evaluations_file.open("w", encoding="utf-8") as f:
            for evaluations in self._evaluations.values():
                for evaluation in evaluations:
                    f.write(evaluation.model_dump_json() + "\n")

        # Save datasets
        datasets_file = self._storage_path.parent / "datasets.jsonl"
        with datasets_file.open("w", encoding="utf-8") as f:
            for dataset in self._datasets.values():
                f.write(dataset.model_dump_json() + "\n")

        # Save runs
        runs_file = self._storage_path.parent / "runs.jsonl"
        with runs_file.open("w", encoding="utf-8") as f:
            for run in self._runs.values():
                f.write(run.model_dump_json() + "\n")

    def _load_from_disk(self) -> None:
        """Load all data from disk."""
        if self._storage_path is None or not self._storage_path.parent.exists():
            return

        # Load responses
        responses_file = self._storage_path.parent / "responses.jsonl"
        if responses_file.exists():
            with responses_file.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        response = LLMResponse.model_validate_json(line)
                        self._responses[response.response_id] = response

        # Load evaluations
        evaluations_file = self._storage_path.parent / "evaluations.jsonl"
        if evaluations_file.exists():
            with evaluations_file.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        evaluation = Evaluation.model_validate_json(line)
                        if evaluation.response_id not in self._evaluations:
                            self._evaluations[evaluation.response_id] = []
                        self._evaluations[evaluation.response_id].append(evaluation)

        # Load datasets
        datasets_file = self._storage_path.parent / "datasets.jsonl"
        if datasets_file.exists():
            with datasets_file.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        dataset = EvaluationDataset.model_validate_json(line)
                        self._datasets[dataset.dataset_id] = dataset

        # Load runs
        runs_file = self._storage_path.parent / "runs.jsonl"
        if runs_file.exists():
            with runs_file.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        run = EvaluationRun.model_validate_json(line)
                        self._runs[run.run_id] = run
