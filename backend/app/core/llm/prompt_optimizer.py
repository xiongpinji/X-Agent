"""Prompt optimization and template management."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
from datetime import datetime
import re


@dataclass
class PromptTemplate:
    """A reusable prompt template."""

    name: str
    template: str
    variables: list[str] = field(default_factory=list)
    description: str = ""
    task_type: str = "general"
    model_optimized_for: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    usage_count: int = 0
    average_quality_score: float = 0.0

    def render(self, **kwargs) -> str:
        """Render template with variables."""
        result = self.template
        for var in self.variables:
            if var in kwargs:
                result = result.replace(f"{{{{{var}}}}}", str(kwargs[var]))
        return result

    def validate_variables(self, **kwargs) -> tuple[bool, list[str]]:
        """Validate that all required variables are provided."""
        missing = [v for v in self.variables if v not in kwargs]
        return len(missing) == 0, missing


class PromptOptimizer:
    """Optimize prompts for better LLM performance and cost."""

    def __init__(self):
        """Initialize prompt optimizer."""
        self.templates: dict[str, PromptTemplate] = {}
        self._initialize_default_templates()
        self._optimization_history: list[dict[str, Any]] = []

    def _initialize_default_templates(self) -> None:
        """Initialize default prompt templates."""
        # Simple QA template
        self.register_template(PromptTemplate(
            name="simple_qa",
            template="Answer the following question concisely:\n\n{question}",
            variables=["question"],
            description="Simple question answering",
            task_type="simple_qa",
        ))

        # Code generation template
        self.register_template(PromptTemplate(
            name="code_generation",
            template="""Generate {language} code for the following task:

Task: {task}

Requirements:
- Include error handling
- Add comments for clarity
- Follow best practices

Code:""",
            variables=["language", "task"],
            description="Code generation with requirements",
            task_type="code_generation",
        ))

        # Analysis template
        self.register_template(PromptTemplate(
            name="analysis",
            template="""Analyze the following data and provide insights:

Data:
{data}

Focus on:
{focus_areas}

Provide:
1. Key findings
2. Patterns identified
3. Recommendations

Analysis:""",
            variables=["data", "focus_areas"],
            description="Data analysis template",
            task_type="analysis",
        ))

        # Summarization template
        self.register_template(PromptTemplate(
            name="summarization",
            template="""Summarize the following text in {length} sentences:

Text:
{text}

Summary:""",
            variables=["text", "length"],
            description="Text summarization",
            task_type="summarization",
        ))

        # Creative writing template
        self.register_template(PromptTemplate(
            name="creative_writing",
            template="""Write a {style} piece about {topic}:

Requirements:
- Length: {length}
- Tone: {tone}
- Include: {elements}

Content:""",
            variables=["style", "topic", "length", "tone", "elements"],
            description="Creative writing template",
            task_type="creative",
        ))

    def register_template(self, template: PromptTemplate) -> None:
        """Register a new prompt template."""
        self.templates[template.name] = template

    def get_template(self, name: str) -> Optional[PromptTemplate]:
        """Get a template by name."""
        return self.templates.get(name)

    def compress_prompt(self, prompt: str, target_tokens: int = 100) -> str:
        """Compress a prompt to reduce token usage."""
        # Remove extra whitespace
        compressed = " ".join(prompt.split())

        # Remove common filler words
        filler_words = [
            "please", "kindly", "thank you", "thanks",
            "could you", "would you", "can you",
            "i would like", "i would appreciate",
        ]

        for word in filler_words:
            compressed = re.sub(rf"\b{word}\b", "", compressed, flags=re.IGNORECASE)

        # Remove extra punctuation
        compressed = re.sub(r"[.!?]{2,}", ".", compressed)

        # Truncate if still too long
        words = compressed.split()
        if len(words) > target_tokens:
            compressed = " ".join(words[:target_tokens]) + "..."

        return compressed.strip()

    def optimize_for_model(self, prompt: str, model: str) -> str:
        """Optimize prompt for a specific model."""
        optimizations = {
            "gpt-4o": self._optimize_for_gpt4,
            "gpt-4o-mini": self._optimize_for_gpt4_mini,
            "deepseek-chat": self._optimize_for_deepseek,
            "deepseek-coder": self._optimize_for_deepseek_coder,
        }

        optimizer = optimizations.get(model, lambda x: x)
        return optimizer(prompt)

    def _optimize_for_gpt4(self, prompt: str) -> str:
        """Optimize for GPT-4."""
        # GPT-4 handles complex reasoning well
        # Add structure and clarity
        if "think step by step" not in prompt.lower():
            prompt = "Think step by step.\n\n" + prompt
        return prompt

    def _optimize_for_gpt4_mini(self, prompt: str) -> str:
        """Optimize for GPT-4 Mini."""
        # GPT-4 Mini is more cost-effective for simpler tasks
        # Keep it concise
        return self.compress_prompt(prompt, target_tokens=150)

    def _optimize_for_deepseek(self, prompt: str) -> str:
        """Optimize for DeepSeek."""
        # DeepSeek handles reasoning well
        if "analyze" not in prompt.lower():
            prompt = prompt + "\n\nProvide detailed analysis."
        return prompt

    def _optimize_for_deepseek_coder(self, prompt: str) -> str:
        """Optimize for DeepSeek Coder."""
        # DeepSeek Coder is specialized for code
        if "code" not in prompt.lower():
            prompt = "Generate code:\n\n" + prompt
        return prompt

    def estimate_tokens(self, prompt: str) -> int:
        """Estimate token count for a prompt."""
        # Rough estimate: 1 token ≈ 4 characters
        return max(1, len(prompt) // 4)

    def add_few_shot_examples(
        self,
        prompt: str,
        examples: list[dict[str, str]],
        max_examples: int = 3,
    ) -> str:
        """Add few-shot examples to a prompt."""
        if not examples:
            return prompt

        # Limit examples
        examples = examples[:max_examples]

        examples_text = "\n\nExamples:\n"
        for i, example in enumerate(examples, 1):
            examples_text += f"\nExample {i}:\n"
            examples_text += f"Input: {example.get('input', '')}\n"
            examples_text += f"Output: {example.get('output', '')}\n"

        return prompt + examples_text

    def extract_variables(self, template_str: str) -> list[str]:
        """Extract variable names from a template string."""
        pattern = r"\{\{(\w+)\}\}"
        return re.findall(pattern, template_str)

    def get_optimization_recommendations(self, prompt: str) -> list[dict[str, Any]]:
        """Get recommendations for prompt optimization."""
        recommendations = []

        # Check length
        token_count = self.estimate_tokens(prompt)
        if token_count > 500:
            recommendations.append({
                "type": "length",
                "description": f"Prompt is {token_count} tokens, consider compressing",
                "action": "compress_prompt",
            })

        # Check for filler words
        filler_words = ["please", "kindly", "thank you"]
        found_fillers = [w for w in filler_words if w.lower() in prompt.lower()]
        if found_fillers:
            recommendations.append({
                "type": "filler_words",
                "description": f"Found filler words: {', '.join(found_fillers)}",
                "action": "remove_filler_words",
            })

        # Check for clarity
        if len(prompt.split("\n")) < 2:
            recommendations.append({
                "type": "structure",
                "description": "Prompt lacks structure, consider adding sections",
                "action": "add_structure",
            })

        # Check for specificity
        if "specific" not in prompt.lower() and "example" not in prompt.lower():
            recommendations.append({
                "type": "specificity",
                "description": "Prompt could be more specific with examples",
                "action": "add_examples",
            })

        return recommendations

    def record_optimization(
        self,
        original_prompt: str,
        optimized_prompt: str,
        model: str,
        quality_score: float,
    ) -> None:
        """Record an optimization for learning."""
        record = {
            "timestamp": datetime.now(),
            "original_length": len(original_prompt),
            "optimized_length": len(optimized_prompt),
            "model": model,
            "quality_score": quality_score,
            "compression_ratio": len(optimized_prompt) / len(original_prompt),
        }
        self._optimization_history.append(record)

        # Keep only last 1000 records
        if len(self._optimization_history) > 1000:
            self._optimization_history = self._optimization_history[-1000:]

    def get_optimization_stats(self) -> dict[str, Any]:
        """Get statistics about optimizations."""
        if not self._optimization_history:
            return {}

        avg_compression = sum(r["compression_ratio"] for r in self._optimization_history) / len(
            self._optimization_history
        )
        avg_quality = sum(r["quality_score"] for r in self._optimization_history) / len(
            self._optimization_history
        )

        return {
            "total_optimizations": len(self._optimization_history),
            "average_compression_ratio": avg_compression,
            "average_quality_score": avg_quality,
        }
