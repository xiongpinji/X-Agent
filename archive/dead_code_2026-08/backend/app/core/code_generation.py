"""
Advanced code generation engine with context-aware generation, prompt engineering, and template support.

This module provides intelligent code generation capabilities including:
- Context-aware code generation based on project structure
- Prompt engineering and optimization
- Code template library and management
- Incremental code generation
- Style-aware code generation matching project conventions
- Multi-language support
"""

from __future__ import annotations

import contextlib
import json
import logging
import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class GenerationMode(StrEnum):
    """Code generation modes."""
    COMPLETE = "complete"  # Generate complete code
    INCREMENTAL = "incremental"  # Generate code incrementally
    SNIPPET = "snippet"  # Generate code snippet
    COMPLETION = "completion"  # Auto-complete code
    REFACTOR = "refactor"  # Refactor existing code


class CodeStyle(StrEnum):
    """Code style conventions."""
    GOOGLE = "google"
    PEP8 = "pep8"
    AIRBNB = "airbnb"
    STANDARD = "standard"
    CUSTOM = "custom"


@dataclass
class CodeTemplate:
    """Code template for generation."""
    name: str
    language: str
    category: str  # "class", "function", "test", "api", etc.
    template: str
    description: str | None = None
    parameters: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def render(self, **kwargs) -> str:
        """Render template with parameters."""
        result = self.template
        for key, value in kwargs.items():
            result = result.replace(f"{{{{{key}}}}}", str(value))
        return result


@dataclass
class GenerationContext:
    """Context for code generation."""
    project_root: str
    file_path: str
    language: str
    style: CodeStyle = CodeStyle.PEP8
    existing_code: str | None = None
    related_files: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    conventions: dict[str, Any] = field(default_factory=dict)
    test_framework: str | None = None
    documentation_style: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "project_root": self.project_root,
            "file_path": self.file_path,
            "language": self.language,
            "style": self.style,
            "existing_code": self.existing_code,
            "related_files": self.related_files,
            "imports": self.imports,
            "dependencies": self.dependencies,
            "conventions": self.conventions,
            "test_framework": self.test_framework,
            "documentation_style": self.documentation_style,
        }


@dataclass
class GenerationRequest:
    """Request for code generation."""
    description: str
    context: GenerationContext
    mode: GenerationMode = GenerationMode.COMPLETE
    temperature: float = 0.7
    max_tokens: int = 2048
    examples: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    request_id: str = field(default_factory=lambda: str(uuid4()))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "description": self.description,
            "context": self.context.to_dict(),
            "mode": self.mode,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "examples": self.examples,
            "constraints": self.constraints,
            "request_id": self.request_id,
        }


@dataclass
class GeneratedCode:
    """Generated code result."""
    code: str
    language: str
    mode: GenerationMode
    confidence: float = 0.8
    explanation: str | None = None
    imports_needed: list[str] = field(default_factory=list)
    dependencies_needed: list[str] = field(default_factory=list)
    tests_suggested: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    generation_id: str = field(default_factory=lambda: str(uuid4()))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "code": self.code,
            "language": self.language,
            "mode": self.mode,
            "confidence": self.confidence,
            "explanation": self.explanation,
            "imports_needed": self.imports_needed,
            "dependencies_needed": self.dependencies_needed,
            "tests_suggested": self.tests_suggested,
            "issues": self.issues,
            "generation_id": self.generation_id,
        }


class PromptEngineer:
    """Prompt engineering for code generation."""

    @staticmethod
    def build_system_prompt(context: GenerationContext) -> str:
        """Build system prompt for code generation."""
        prompt = f"""You are an expert code generator specializing in {context.language} development.

Your task is to generate high-quality, production-ready code that:
1. Follows {context.style} style conventions
2. Integrates seamlessly with the existing project
3. Includes comprehensive documentation
4. Handles errors gracefully
5. Is fully tested and verified

Project Context:
- Root: {context.project_root}
- Language: {context.language}
- Style: {context.style}
- Test Framework: {context.test_framework or 'Not specified'}
- Documentation Style: {context.documentation_style or 'Docstrings'}

Existing Conventions:
{json.dumps(context.conventions, indent=2)}

When generating code:
1. Match the existing code style and patterns
2. Include type hints where applicable
3. Add comprehensive docstrings
4. Handle edge cases and errors
5. Suggest relevant imports and dependencies
6. Provide test cases if applicable
"""
        return prompt

    @staticmethod
    def build_user_prompt(request: GenerationRequest) -> str:
        """Build user prompt for code generation."""
        prompt = f"""Generate {request.mode} code for the following:

Description: {request.description}

Mode: {request.mode}
Temperature: {request.temperature}
Max Tokens: {request.max_tokens}

Context:
- File: {request.context.file_path}
- Language: {request.context.language}
- Related Files: {', '.join(request.context.related_files) if request.context.related_files else 'None'}
- Imports: {', '.join(request.context.imports) if request.context.imports else 'None'}
- Dependencies: {', '.join(request.context.dependencies) if request.context.dependencies else 'None'}

"""
        if request.context.existing_code:
            prompt += f"""Existing Code:
```{request.context.language}
{request.context.existing_code}
```

"""
        if request.examples:
            prompt += f"""Examples:
{chr(10).join(f'- {ex}' for ex in request.examples)}

"""
        if request.constraints:
            prompt += f"""Constraints:
{chr(10).join(f'- {c}' for c in request.constraints)}

"""
        prompt += """Please generate the code and provide:
1. The generated code
2. Explanation of the implementation
3. Required imports
4. Required dependencies
5. Suggested test cases
6. Any potential issues or considerations
"""
        return prompt


class CodeTemplateLibrary:
    """Library of code templates."""

    def __init__(self):
        self.templates: dict[str, list[CodeTemplate]] = {}
        self._initialize_templates()

    def _initialize_templates(self) -> None:
        """Initialize built-in templates."""
        # Python templates
        python_templates = [
            CodeTemplate(
                name="class_basic",
                language="python",
                category="class",
                template="""class {{class_name}}:
    \"\"\"{{description}}\"\"\"

    def __init__(self{{init_params}}):
        {{init_body}}

    def __repr__(self) -> str:
        return f"{{class_name}}(...)"
""",
                description="Basic class template",
                parameters=["class_name", "description", "init_params", "init_body"],
            ),
            CodeTemplate(
                name="function_basic",
                language="python",
                category="function",
                template="""def {{function_name}}({{params}}) -> {{return_type}}:
    \"\"\"{{description}}

    Args:
        {{args_doc}}

    Returns:
        {{return_doc}}
    \"\"\"
    {{body}}
""",
                description="Basic function template",
                parameters=["function_name", "params", "return_type", "description", "args_doc", "return_doc", "body"],
            ),
            CodeTemplate(
                name="test_basic",
                language="python",
                category="test",
                template="""import pytest
from {{module}} import {{class_or_function}}


class Test{{class_or_function}}:
    \"\"\"Tests for {{class_or_function}}.\"\"\"

    def test_basic(self):
        \"\"\"Test basic functionality.\"\"\"
        {{test_body}}

    def test_edge_cases(self):
        \"\"\"Test edge cases.\"\"\"
        {{edge_case_body}}
""",
                description="Basic test template",
                parameters=["module", "class_or_function", "test_body", "edge_case_body"],
            ),
        ]

        # JavaScript templates
        js_templates = [
            CodeTemplate(
                name="class_basic",
                language="javascript",
                category="class",
                template="""class {{ClassName}} {
  /**
   * {{description}}
   */
  constructor({{params}}) {
    {{init_body}}
  }

  {{methods}}
}

export default {{ClassName}};
""",
                description="Basic JavaScript class template",
                parameters=["ClassName", "description", "params", "init_body", "methods"],
            ),
            CodeTemplate(
                name="function_basic",
                language="javascript",
                category="function",
                template="""/**
 * {{description}}
 * @param {{{param_types}}} {{param_names}}
 * @returns {{{return_type}}} {{return_description}}
 */
export function {{functionName}}({{params}}) {
  {{body}}
}
""",
                description="Basic JavaScript function template",
                parameters=["description", "param_types", "param_names", "return_type", "return_description", "functionName", "params", "body"],
            ),
        ]

        self.templates["python"] = python_templates
        self.templates["javascript"] = js_templates

    def get_template(self, language: str, category: str) -> CodeTemplate | None:
        """Get template by language and category."""
        templates = self.templates.get(language, [])
        for template in templates:
            if template.category == category:
                return template
        return None

    def list_templates(self, language: str | None = None) -> list[CodeTemplate]:
        """List available templates."""
        if language:
            return self.templates.get(language, [])
        result = []
        for templates in self.templates.values():
            result.extend(templates)
        return result

    def add_template(self, template: CodeTemplate) -> None:
        """Add custom template."""
        if template.language not in self.templates:
            self.templates[template.language] = []
        self.templates[template.language].append(template)


class StyleAnalyzer:
    """Analyze and extract code style conventions."""

    @staticmethod
    def analyze_style(code_samples: list[str], language: str) -> dict[str, Any]:
        """Analyze code style from samples."""
        conventions = {
            "indentation": StyleAnalyzer._detect_indentation(code_samples),
            "naming_convention": StyleAnalyzer._detect_naming_convention(code_samples, language),
            "line_length": StyleAnalyzer._detect_line_length(code_samples),
            "import_style": StyleAnalyzer._detect_import_style(code_samples, language),
            "comment_style": StyleAnalyzer._detect_comment_style(code_samples),
            "bracket_style": StyleAnalyzer._detect_bracket_style(code_samples),
        }
        return conventions

    @staticmethod
    def _detect_indentation(code_samples: list[str]) -> str:
        """Detect indentation style."""
        for sample in code_samples:
            if "\t" in sample:
                return "tabs"
            if "    " in sample:
                return "spaces_4"
            if "  " in sample:
                return "spaces_2"
        return "spaces_4"

    @staticmethod
    def _detect_naming_convention(code_samples: list[str], language: str) -> str:
        """Detect naming convention."""
        if language == "python":
            if any(re.search(r"_[a-z_]+", sample) for sample in code_samples):
                return "snake_case"
        elif language in ["javascript", "typescript"]:
            if any(re.search(r"[a-z][a-zA-Z0-9]*", sample) for sample in code_samples):
                return "camelCase"
        return "snake_case"

    @staticmethod
    def _detect_line_length(code_samples: list[str]) -> int:
        """Detect preferred line length."""
        lengths = []
        for sample in code_samples:
            for line in sample.split("\n"):
                if line.strip():
                    lengths.append(len(line))
        if lengths:
            return int(sum(lengths) / len(lengths))
        return 80

    @staticmethod
    def _detect_import_style(code_samples: list[str], language: str) -> str:
        """Detect import style."""
        if language == "python":
            for sample in code_samples:
                if "from" in sample and "import" in sample:
                    return "from_import"
            return "import"
        return "import"

    @staticmethod
    def _detect_comment_style(code_samples: list[str]) -> str:
        """Detect comment style."""
        for sample in code_samples:
            if "/**" in sample or "/*" in sample:
                return "block_comment"
            if "//" in sample:
                return "line_comment"
            if "#" in sample:
                return "hash_comment"
        return "hash_comment"

    @staticmethod
    def _detect_bracket_style(code_samples: list[str]) -> str:
        """Detect bracket style."""
        for sample in code_samples:
            if re.search(r"\{\s*$", sample, re.MULTILINE):
                return "same_line"
            if re.search(r"\{\s*\n", sample):
                return "next_line"
        return "same_line"


class CodeGenerationEngine:
    """Main code generation engine."""

    def __init__(self):
        self.template_library = CodeTemplateLibrary()
        self.prompt_engineer = PromptEngineer()
        self.style_analyzer = StyleAnalyzer()
        self.generation_history: list[GeneratedCode] = []

    def generate_code(self, request: GenerationRequest) -> GeneratedCode:
        """Generate code based on request."""
        # Build prompts
        system_prompt = self.prompt_engineer.build_system_prompt(request.context)
        user_prompt = self.prompt_engineer.build_user_prompt(request)

        # Try to use template if available
        template = self._find_matching_template(request)
        if template:
            code = self._generate_from_template(template, request)
        else:
            code = self._generate_from_llm(system_prompt, user_prompt, request)

        # Post-process generated code
        code = self._post_process_code(code, request.context)

        # Create result
        result = GeneratedCode(
            code=code,
            language=request.context.language,
            mode=request.mode,
            confidence=0.85,
        )

        self.generation_history.append(result)
        return result

    def generate_incremental(self, request: GenerationRequest, position: int) -> GeneratedCode:
        """Generate code incrementally at a specific position."""
        request.mode = GenerationMode.INCREMENTAL
        return self.generate_code(request)

    def generate_completion(self, request: GenerationRequest, prefix: str) -> GeneratedCode:
        """Generate code completion."""
        request.mode = GenerationMode.COMPLETION
        request.context.existing_code = prefix
        return self.generate_code(request)

    def analyze_project_style(self, project_root: str, language: str, sample_size: int = 5) -> dict[str, Any]:
        """Analyze project style conventions."""
        code_samples = self._collect_code_samples(project_root, language, sample_size)
        return self.style_analyzer.analyze_style(code_samples, language)

    def _find_matching_template(self, request: GenerationRequest) -> CodeTemplate | None:
        """Find matching template for request."""
        # Extract category from description
        description_lower = request.description.lower()
        if "class" in description_lower:
            return self.template_library.get_template(request.context.language, "class")
        elif "function" in description_lower or "method" in description_lower:
            return self.template_library.get_template(request.context.language, "function")
        elif "test" in description_lower:
            return self.template_library.get_template(request.context.language, "test")
        return None

    def _generate_from_template(self, template: CodeTemplate, request: GenerationRequest) -> str:
        """Generate code from template."""
        # Extract parameters from description
        params = self._extract_parameters(request.description, template.parameters)
        return template.render(**params)

    def _generate_from_llm(self, system_prompt: str, user_prompt: str, request: GenerationRequest) -> str:
        """Generate code from LLM."""
        # This would call the actual LLM API
        # For now, return a placeholder
        return f"# Generated code for: {request.description}\n# TODO: Implement"

    def _post_process_code(self, code: str, context: GenerationContext) -> str:
        """Post-process generated code."""
        # Apply style conventions
        if context.style == CodeStyle.PEP8:
            code = self._apply_pep8(code)
        elif context.style == CodeStyle.GOOGLE:
            code = self._apply_google_style(code)

        # Add imports if needed
        if context.imports:
            code = self._add_imports(code, context.imports, context.language)

        return code

    def _apply_pep8(self, code: str) -> str:
        """Apply PEP8 style."""
        # Simple PEP8 formatting
        lines = code.split("\n")
        formatted = []
        for line in lines:
            # Ensure proper indentation
            if line.strip():
                indent = len(line) - len(line.lstrip())
                if indent % 4 != 0:
                    indent = (indent // 4 + 1) * 4
                formatted.append(" " * indent + line.lstrip())
            else:
                formatted.append("")
        return "\n".join(formatted)

    def _apply_google_style(self, code: str) -> str:
        """Apply Google style."""
        # Google style formatting
        return code

    def _add_imports(self, code: str, imports: list[str], language: str) -> str:
        """Add imports to code."""
        if language == "python":
            import_lines = "\n".join(f"import {imp}" for imp in imports)
            return f"{import_lines}\n\n{code}"
        elif language in ["javascript", "typescript"]:
            import_lines = "\n".join(f"import {imp} from '...';" for imp in imports)
            return f"{import_lines}\n\n{code}"
        return code

    def _extract_parameters(self, description: str, template_params: list[str]) -> dict[str, str]:
        """Extract parameters from description."""
        params = {}
        for param in template_params:
            # Simple extraction - in real implementation would be more sophisticated
            params[param] = "{{param}}"
        return params

    def _collect_code_samples(self, project_root: str, language: str, sample_size: int) -> list[str]:
        """Collect code samples from project."""
        root = Path(project_root)
        ext_map = {
            "python": ".py",
            "javascript": ".js",
            "typescript": ".ts",
        }
        ext = ext_map.get(language, ".py")

        samples = []
        for file_path in root.rglob(f"*{ext}"):
            if len(samples) >= sample_size:
                break
            with contextlib.suppress(Exception):
                samples.append(file_path.read_text(encoding="utf-8", errors="ignore"))

        return samples
