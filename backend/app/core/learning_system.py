"""
Autonomous learning system for X-Agent.

This module provides capabilities for learning from feedback, success cases,
and failures to continuously improve agent performance.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class FeedbackType(Enum):
    """Types of feedback."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    CORRECTIVE = "corrective"
    SUGGESTIVE = "suggestive"


class ErrorType(Enum):
    """Types of errors."""
    LOGIC_ERROR = "logic_error"
    CALCULATION_ERROR = "calculation_error"
    REASONING_ERROR = "reasoning_error"
    TOOL_ERROR = "tool_error"
    TIMEOUT_ERROR = "timeout_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class Task:
    """A task executed by the agent."""
    task_id: str
    description: str
    input_data: dict[str, Any]
    output_data: dict[str, Any]
    execution_time: float
    success: bool
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Feedback:
    """Feedback on a task or solution."""
    feedback_id: str
    task_id: str
    feedback_type: FeedbackType
    content: str
    rating: float  # 0-1
    suggestions: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Error:
    """Error information."""
    error_id: str
    task_id: str
    error_type: ErrorType
    message: str
    traceback: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Knowledge:
    """A piece of knowledge learned by the agent."""
    knowledge_id: str
    category: str
    content: str
    confidence: float  # 0-1
    source: str  # Where this knowledge came from
    related_tasks: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LearningPattern:
    """A pattern learned from multiple tasks."""
    pattern_id: str
    pattern_type: str
    description: str
    conditions: dict[str, Any]
    actions: list[str]
    success_rate: float
    num_occurrences: int
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)


class LearningSystem:
    """Autonomous learning system for continuous improvement."""

    def __init__(self):
        """Initialize learning system."""
        self.knowledge_base: list[Knowledge] = []
        self.learning_patterns: list[LearningPattern] = []
        self.task_history: list[Task] = []
        self.feedback_history: list[Feedback] = []
        self.error_history: list[Error] = []
        self.learning_metrics = {
            "total_tasks": 0,
            "successful_tasks": 0,
            "failed_tasks": 0,
            "average_success_rate": 0.0,
            "knowledge_items": 0,
            "patterns_discovered": 0,
        }

    async def learn_from_feedback(
        self,
        task: Task,
        feedback: Feedback,
    ) -> None:
        """Learn from user feedback on a task.

        Args:
            task: The task that was executed.
            feedback: Feedback on the task.
        """
        logger.info(f"Learning from feedback on task {task.task_id}")

        # Store feedback
        self.feedback_history.append(feedback)

        # Extract knowledge from feedback
        if feedback.feedback_type == FeedbackType.POSITIVE:
            await self._extract_success_pattern(task, feedback)
        elif feedback.feedback_type == FeedbackType.CORRECTIVE:
            await self._extract_correction_pattern(task, feedback)
        elif feedback.feedback_type == FeedbackType.SUGGESTIVE:
            await self._extract_suggestion_pattern(task, feedback)

        # Update learning metrics
        self._update_metrics()

    async def learn_from_success(self, task: Task) -> None:
        """Learn from successful task execution.

        Args:
            task: The successfully executed task.
        """
        logger.info(f"Learning from successful task {task.task_id}")

        # Store task
        self.task_history.append(task)

        # Extract success patterns
        await self._extract_success_pattern(task, None)

        # Identify generalizable patterns
        await self._identify_patterns()

        # Update metrics
        self.learning_metrics["successful_tasks"] += 1
        self.learning_metrics["total_tasks"] += 1
        self._update_metrics()

    async def learn_from_failure(
        self,
        task: Task,
        error: Error,
    ) -> None:
        """Learn from task failure.

        Args:
            task: The failed task.
            error: Error information.
        """
        logger.info(f"Learning from failure on task {task.task_id}")

        # Store task and error
        self.task_history.append(task)
        self.error_history.append(error)

        # Analyze error
        error_analysis = await self._analyze_error(error)

        # Extract error patterns
        await self._extract_error_pattern(task, error, error_analysis)

        # Generate recovery strategies
        recovery_strategies = await self._generate_recovery_strategies(error)

        # Store recovery knowledge
        for strategy in recovery_strategies:
            knowledge = Knowledge(
                knowledge_id=f"recovery_{error.error_id}_{len(self.knowledge_base)}",
                category="error_recovery",
                content=strategy,
                confidence=0.7,
                source=f"error_analysis_{error.error_type.value}",
                related_tasks=[task.task_id],
            )
            self.knowledge_base.append(knowledge)

        # Update metrics
        self.learning_metrics["failed_tasks"] += 1
        self.learning_metrics["total_tasks"] += 1
        self._update_metrics()

    async def update_knowledge_base(self, knowledge: Knowledge) -> None:
        """Update knowledge base with new knowledge.

        Args:
            knowledge: New knowledge to add.
        """
        logger.info(f"Adding knowledge: {knowledge.knowledge_id}")

        # Check if similar knowledge exists
        similar_knowledge = self._find_similar_knowledge(knowledge)

        if similar_knowledge:
            # Merge with existing knowledge
            await self._merge_knowledge(similar_knowledge, knowledge)
        else:
            # Add new knowledge
            self.knowledge_base.append(knowledge)

        self.learning_metrics["knowledge_items"] = len(self.knowledge_base)

    async def _extract_success_pattern(
        self,
        task: Task,
        feedback: Feedback | None,
    ) -> None:
        """Extract patterns from successful tasks.

        Args:
            task: The successful task.
            feedback: Optional feedback.
        """
        # Analyze task characteristics
        pattern_description = f"Successfully completed task: {task.description}"

        # Create pattern
        pattern = LearningPattern(
            pattern_id=f"success_{task.task_id}",
            pattern_type="success",
            description=pattern_description,
            conditions=task.input_data,
            actions=[f"Execute: {task.description}"],
            success_rate=1.0,
            num_occurrences=1,
            confidence=0.9 if feedback and feedback.rating > 0.8 else 0.7,
        )

        self.learning_patterns.append(pattern)
        logger.debug(f"Extracted success pattern: {pattern.pattern_id}")

    async def _extract_correction_pattern(
        self,
        task: Task,
        feedback: Feedback,
    ) -> None:
        """Extract patterns from corrective feedback.

        Args:
            task: The task with corrective feedback.
            feedback: The corrective feedback.
        """
        # Extract what was wrong and what should be done instead
        pattern_description = f"Correction: {feedback.content}"

        pattern = LearningPattern(
            pattern_id=f"correction_{task.task_id}",
            pattern_type="correction",
            description=pattern_description,
            conditions=task.input_data,
            actions=feedback.suggestions,
            success_rate=0.0,  # This was a failure
            num_occurrences=1,
            confidence=0.8,
        )

        self.learning_patterns.append(pattern)
        logger.debug(f"Extracted correction pattern: {pattern.pattern_id}")

    async def _extract_suggestion_pattern(
        self,
        task: Task,
        feedback: Feedback,
    ) -> None:
        """Extract patterns from suggestive feedback.

        Args:
            task: The task with suggestive feedback.
            feedback: The suggestive feedback.
        """
        pattern_description = f"Suggestion: {feedback.content}"

        pattern = LearningPattern(
            pattern_id=f"suggestion_{task.task_id}",
            pattern_type="suggestion",
            description=pattern_description,
            conditions=task.input_data,
            actions=feedback.suggestions,
            success_rate=0.5,  # Uncertain
            num_occurrences=1,
            confidence=0.6,
        )

        self.learning_patterns.append(pattern)
        logger.debug(f"Extracted suggestion pattern: {pattern.pattern_id}")

    async def _extract_error_pattern(
        self,
        task: Task,
        error: Error,
        error_analysis: dict[str, Any],
    ) -> None:
        """Extract patterns from errors.

        Args:
            task: The failed task.
            error: The error.
            error_analysis: Analysis of the error.
        """
        pattern_description = f"Error pattern: {error.error_type.value} - {error_analysis.get('root_cause', 'Unknown')}"

        pattern = LearningPattern(
            pattern_id=f"error_{error.error_id}",
            pattern_type="error",
            description=pattern_description,
            conditions=error.context,
            actions=error_analysis.get("prevention_strategies", []),
            success_rate=0.0,
            num_occurrences=1,
            confidence=0.7,
        )

        self.learning_patterns.append(pattern)
        logger.debug(f"Extracted error pattern: {pattern.pattern_id}")

    async def _identify_patterns(self) -> None:
        """Identify generalizable patterns from task history."""
        logger.info("Identifying generalizable patterns")

        # Group similar tasks
        task_groups = self._group_similar_tasks()

        # Analyze each group
        for group_id, tasks in task_groups.items():
            if len(tasks) >= 3:  # Only consider patterns with 3+ occurrences
                # Calculate success rate
                successful = sum(1 for t in tasks if t.success)
                success_rate = successful / len(tasks)

                # Create pattern
                pattern = LearningPattern(
                    pattern_id=f"generalized_{group_id}",
                    pattern_type="generalized",
                    description=f"Pattern for task group: {group_id}",
                    conditions=self._extract_common_conditions(tasks),
                    actions=self._extract_common_actions(tasks),
                    success_rate=success_rate,
                    num_occurrences=len(tasks),
                    confidence=min(success_rate, 0.9),
                )

                self.learning_patterns.append(pattern)
                logger.debug(f"Identified generalized pattern: {pattern.pattern_id}")

    async def _analyze_error(self, error: Error) -> dict[str, Any]:
        """Analyze an error to understand root cause.

        Args:
            error: The error to analyze.

        Returns:
            Error analysis.
        """
        analysis = {
            "error_type": error.error_type.value,
            "root_cause": "Unknown",
            "prevention_strategies": [],
            "recovery_strategies": [],
        }

        # Analyze based on error type
        if error.error_type == ErrorType.LOGIC_ERROR:
            analysis["root_cause"] = "Incorrect reasoning or logic"
            analysis["prevention_strategies"] = [
                "Add more validation checks",
                "Improve reasoning prompts",
                "Use chain-of-thought reasoning",
            ]
        elif error.error_type == ErrorType.CALCULATION_ERROR:
            analysis["root_cause"] = "Calculation mistake"
            analysis["prevention_strategies"] = [
                "Use calculator tools",
                "Verify calculations",
                "Use step-by-step computation",
            ]
        elif error.error_type == ErrorType.REASONING_ERROR:
            analysis["root_cause"] = "Flawed reasoning"
            analysis["prevention_strategies"] = [
                "Use tree-of-thought reasoning",
                "Add self-reflection",
                "Verify assumptions",
            ]
        elif error.error_type == ErrorType.TOOL_ERROR:
            analysis["root_cause"] = "Tool execution failure"
            analysis["prevention_strategies"] = [
                "Add error handling",
                "Retry with backoff",
                "Use alternative tools",
            ]
        elif error.error_type == ErrorType.TIMEOUT_ERROR:
            analysis["root_cause"] = "Operation timeout"
            analysis["prevention_strategies"] = [
                "Optimize operations",
                "Increase timeout",
                "Break into smaller tasks",
            ]

        return analysis

    async def _generate_recovery_strategies(self, error: Error) -> list[str]:
        """Generate recovery strategies for an error.

        Args:
            error: The error.

        Returns:
            List of recovery strategies.
        """
        strategies = []

        if error.error_type == ErrorType.LOGIC_ERROR:
            strategies = [
                "Re-analyze the problem with fresh perspective",
                "Use alternative reasoning approach",
                "Consult knowledge base for similar problems",
            ]
        elif error.error_type == ErrorType.CALCULATION_ERROR:
            strategies = [
                "Recalculate using different method",
                "Break calculation into smaller steps",
                "Use external calculator verification",
            ]
        elif error.error_type == ErrorType.TOOL_ERROR:
            strategies = [
                "Retry with same tool",
                "Try alternative tool",
                "Manually perform operation",
            ]
        elif error.error_type == ErrorType.TIMEOUT_ERROR:
            strategies = [
                "Simplify the task",
                "Break into smaller subtasks",
                "Increase resource allocation",
            ]

        return strategies

    def _find_similar_knowledge(self, knowledge: Knowledge) -> Knowledge | None:
        """Find similar knowledge in knowledge base.

        Args:
            knowledge: The knowledge to find similar items for.

        Returns:
            Similar knowledge if found, None otherwise.
        """
        for existing in self.knowledge_base:
            if (existing.category == knowledge.category and
                self._similarity_score(existing.content, knowledge.content) > 0.8):
                return existing
        return None

    async def _merge_knowledge(
        self,
        existing: Knowledge,
        new: Knowledge,
    ) -> None:
        """Merge new knowledge with existing knowledge.

        Args:
            existing: Existing knowledge.
            new: New knowledge to merge.
        """
        # Update confidence (average with weight towards higher confidence)
        existing.confidence = (existing.confidence + new.confidence) / 2

        # Merge related tasks
        existing.related_tasks = list(set(existing.related_tasks + new.related_tasks))

        # Update timestamp
        existing.timestamp = datetime.now()

        logger.debug(f"Merged knowledge: {existing.knowledge_id}")

    def _group_similar_tasks(self) -> dict[str, list[Task]]:
        """Group similar tasks from history.

        Args:
            Returns: Dictionary mapping group IDs to task lists.
        """
        groups = {}

        for task in self.task_history:
            # Extract task type from description
            task_type = task.description.split()[0] if task.description else "unknown"

            if task_type not in groups:
                groups[task_type] = []

            groups[task_type].append(task)

        return groups

    def _extract_common_conditions(self, tasks: list[Task]) -> dict[str, Any]:
        """Extract common conditions from tasks.

        Args:
            tasks: List of tasks.

        Returns:
            Common conditions.
        """
        # Placeholder: return first task's input as common conditions
        if tasks:
            return tasks[0].input_data
        return {}

    def _extract_common_actions(self, tasks: list[Task]) -> list[str]:
        """Extract common actions from tasks.

        Args:
            tasks: List of tasks.

        Returns:
            Common actions.
        """
        # Placeholder: return task descriptions
        return [t.description for t in tasks]

    def _similarity_score(self, text1: str, text2: str) -> float:
        """Calculate similarity score between two texts.

        Args:
            text1: First text.
            text2: Second text.

        Returns:
            Similarity score between 0 and 1.
        """
        # Simple word overlap similarity
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def _update_metrics(self) -> None:
        """Update learning metrics."""
        total = self.learning_metrics["total_tasks"]
        if total > 0:
            successful = self.learning_metrics["successful_tasks"]
            self.learning_metrics["average_success_rate"] = successful / total

        self.learning_metrics["knowledge_items"] = len(self.knowledge_base)
        self.learning_metrics["patterns_discovered"] = len(self.learning_patterns)

    def get_learning_metrics(self) -> dict[str, Any]:
        """Get current learning metrics.

        Returns:
            Learning metrics.
        """
        return self.learning_metrics.copy()

    def get_knowledge_base(self) -> list[Knowledge]:
        """Get knowledge base.

        Returns:
            List of knowledge items.
        """
        return self.knowledge_base.copy()

    def get_patterns(self) -> list[LearningPattern]:
        """Get discovered patterns.

        Returns:
            List of patterns.
        """
        return self.learning_patterns.copy()

    def get_high_confidence_patterns(self, threshold: float = 0.8) -> list[LearningPattern]:
        """Get high-confidence patterns.

        Args:
            threshold: Confidence threshold.

        Returns:
            List of high-confidence patterns.
        """
        return [p for p in self.learning_patterns if p.confidence >= threshold]
