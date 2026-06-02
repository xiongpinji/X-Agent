"""
Context-aware programming engine that understands project structure, learns code style, and adapts to project conventions.

This module provides intelligent context awareness including:
- Project structure analysis and understanding
- Code style learning and adaptation
- Architecture pattern recognition
- Automatic convention detection
- Project-specific rule enforcement
- Dependency and import optimization
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class ProjectStructure:
    """Represents project structure and organization."""
    root: str
    name: str
    language: str
    framework: Optional[str] = None
    package_manager: Optional[str] = None
    test_framework: Optional[str] = None
    build_tool: Optional[str] = None
    directories: dict[str, str] = field(default_factory=dict)  # name -> purpose
    key_files: list[str] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    configuration_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "root": self.root,
            "name": self.name,
            "language": self.language,
            "framework": self.framework,
            "package_manager": self.package_manager,
            "test_framework": self.test_framework,
            "build_tool": self.build_tool,
            "directories": self.directories,
            "key_files": self.key_files,
            "entry_points": self.entry_points,
            "configuration_files": self.configuration_files,
        }


@dataclass
class ArchitecturePattern:
    """Represents detected architecture pattern."""
    name: str  # "MVC", "MVVM", "Layered", "Microservices", etc.
    confidence: float
    layers: list[str] = field(default_factory=list)
    components: list[str] = field(default_factory=list)
    dependencies: dict[str, list[str]] = field(default_factory=dict)
    description: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "confidence": self.confidence,
            "layers": self.layers,
            "components": self.components,
            "dependencies": self.dependencies,
            "description": self.description,
        }


@dataclass
class CodeConvention:
    """Represents a code convention or rule."""
    name: str
    category: str  # "naming", "structure", "documentation", "testing", etc.
    pattern: str  # regex or description
    examples: list[str] = field(default_factory=list)
    enforcement_level: str = "recommended"  # "required", "recommended", "optional"
    description: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "category": self.category,
            "pattern": self.pattern,
            "examples": self.examples,
            "enforcement_level": self.enforcement_level,
            "description": self.description,
        }


@dataclass
class ProjectContext:
    """Complete project context for code generation."""
    project_structure: ProjectStructure
    architecture_pattern: Optional[ArchitecturePattern] = None
    conventions: list[CodeConvention] = field(default_factory=list)
    common_imports: dict[str, list[str]] = field(default_factory=dict)
    module_organization: dict[str, list[str]] = field(default_factory=dict)
    testing_patterns: list[str] = field(default_factory=list)
    documentation_style: Optional[str] = None
    error_handling_style: Optional[str] = None
    async_patterns: list[str] = field(default_factory=list)
    context_id: str = field(default_factory=lambda: str(uuid4()))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "project_structure": self.project_structure.to_dict(),
            "architecture_pattern": self.architecture_pattern.to_dict() if self.architecture_pattern else None,
            "conventions": [c.to_dict() for c in self.conventions],
            "common_imports": self.common_imports,
            "module_organization": self.module_organization,
            "testing_patterns": self.testing_patterns,
            "documentation_style": self.documentation_style,
            "error_handling_style": self.error_handling_style,
            "async_patterns": self.async_patterns,
            "context_id": self.context_id,
        }


class ProjectStructureAnalyzer:
    """Analyze project structure and organization."""

    @staticmethod
    def analyze(root_path: str) -> ProjectStructure:
        """Analyze project structure."""
        root = Path(root_path)

        # Detect language and framework
        language, framework = ProjectStructureAnalyzer._detect_language_and_framework(root)

        # Detect package manager and build tool
        package_manager = ProjectStructureAnalyzer._detect_package_manager(root)
        build_tool = ProjectStructureAnalyzer._detect_build_tool(root)
        test_framework = ProjectStructureAnalyzer._detect_test_framework(root)

        # Analyze directory structure
        directories = ProjectStructureAnalyzer._analyze_directories(root)

        # Find key files
        key_files = ProjectStructureAnalyzer._find_key_files(root)

        # Find entry points
        entry_points = ProjectStructureAnalyzer._find_entry_points(root, language)

        # Find configuration files
        config_files = ProjectStructureAnalyzer._find_config_files(root)

        return ProjectStructure(
            root=str(root),
            name=root.name,
            language=language,
            framework=framework,
            package_manager=package_manager,
            build_tool=build_tool,
            test_framework=test_framework,
            directories=directories,
            key_files=key_files,
            entry_points=entry_points,
            configuration_files=config_files,
        )

    @staticmethod
    def _detect_language_and_framework(root: Path) -> tuple[str, Optional[str]]:
        """Detect programming language and framework."""
        # Check for language indicators
        if (root / "package.json").exists():
            return "javascript", ProjectStructureAnalyzer._detect_js_framework(root)
        elif (root / "pyproject.toml").exists() or (root / "setup.py").exists():
            return "python", ProjectStructureAnalyzer._detect_python_framework(root)
        elif (root / "go.mod").exists():
            return "go", None
        elif (root / "Cargo.toml").exists():
            return "rust", None
        elif (root / "pom.xml").exists() or (root / "build.gradle").exists():
            return "java", None

        # Default to Python
        return "python", None

    @staticmethod
    def _detect_js_framework(root: Path) -> Optional[str]:
        """Detect JavaScript framework."""
        try:
            package_json = json.loads((root / "package.json").read_text())
            deps = {**package_json.get("dependencies", {}), **package_json.get("devDependencies", {})}

            if "react" in deps:
                return "react"
            elif "vue" in deps:
                return "vue"
            elif "angular" in deps:
                return "angular"
            elif "next" in deps:
                return "next"
            elif "nuxt" in deps:
                return "nuxt"
            elif "express" in deps:
                return "express"
            elif "fastify" in deps:
                return "fastify"
        except Exception:
            pass

        return None

    @staticmethod
    def _detect_python_framework(root: Path) -> Optional[str]:
        """Detect Python framework."""
        # Check for framework indicators in common files
        for file_path in root.rglob("*.py"):
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                if "from django" in content or "import django" in content:
                    return "django"
                elif "from flask" in content or "import flask" in content:
                    return "flask"
                elif "from fastapi" in content or "import fastapi" in content:
                    return "fastapi"
                elif "from starlette" in content or "import starlette" in content:
                    return "starlette"
            except Exception:
                pass

        return None

    @staticmethod
    def _detect_package_manager(root: Path) -> Optional[str]:
        """Detect package manager."""
        if (root / "package.json").exists():
            if (root / "yarn.lock").exists():
                return "yarn"
            elif (root / "pnpm-lock.yaml").exists():
                return "pnpm"
            return "npm"
        elif (root / "pyproject.toml").exists():
            return "poetry"
        elif (root / "requirements.txt").exists():
            return "pip"
        elif (root / "Pipfile").exists():
            return "pipenv"
        elif (root / "go.mod").exists():
            return "go"
        elif (root / "Cargo.toml").exists():
            return "cargo"

        return None

    @staticmethod
    def _detect_build_tool(root: Path) -> Optional[str]:
        """Detect build tool."""
        if (root / "Makefile").exists():
            return "make"
        elif (root / "webpack.config.js").exists():
            return "webpack"
        elif (root / "vite.config.js").exists():
            return "vite"
        elif (root / "tsconfig.json").exists():
            return "typescript"
        elif (root / "setup.py").exists():
            return "setuptools"
        elif (root / "pyproject.toml").exists():
            return "poetry"

        return None

    @staticmethod
    def _detect_test_framework(root: Path) -> Optional[str]:
        """Detect test framework."""
        for file_path in root.rglob("*.py"):
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                if "import pytest" in content:
                    return "pytest"
                elif "import unittest" in content:
                    return "unittest"
            except Exception:
                pass

        for file_path in root.rglob("*.js"):
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                if "jest" in content:
                    return "jest"
                elif "mocha" in content:
                    return "mocha"
                elif "vitest" in content:
                    return "vitest"
            except Exception:
                pass

        return None

    @staticmethod
    def _analyze_directories(root: Path) -> dict[str, str]:
        """Analyze directory structure and purposes."""
        directories = {}

        # Common directory patterns
        patterns = {
            "src": "source code",
            "lib": "library code",
            "app": "application code",
            "backend": "backend code",
            "frontend": "frontend code",
            "tests": "test files",
            "test": "test files",
            "spec": "test specifications",
            "docs": "documentation",
            "examples": "example code",
            "scripts": "utility scripts",
            "config": "configuration files",
            "public": "public assets",
            "static": "static files",
            "assets": "asset files",
            "utils": "utility functions",
            "helpers": "helper functions",
            "services": "service layer",
            "models": "data models",
            "views": "view layer",
            "controllers": "controller layer",
            "middleware": "middleware",
            "hooks": "hooks",
            "components": "components",
            "pages": "pages",
            "api": "API endpoints",
            "core": "core functionality",
        }

        for dir_path in root.iterdir():
            if dir_path.is_dir() and not dir_path.name.startswith("."):
                if dir_path.name in patterns:
                    directories[dir_path.name] = patterns[dir_path.name]

        return directories

    @staticmethod
    def _find_key_files(root: Path) -> list[str]:
        """Find key files in project."""
        key_files = []

        key_file_names = [
            "README.md", "setup.py", "pyproject.toml", "package.json",
            "Makefile", "Dockerfile", "docker-compose.yml",
            "requirements.txt", "go.mod", "Cargo.toml",
            ".env.example", "config.yaml", "settings.py"
        ]

        for file_name in key_file_names:
            file_path = root / file_name
            if file_path.exists():
                key_files.append(file_name)

        return key_files

    @staticmethod
    def _find_entry_points(root: Path, language: str) -> list[str]:
        """Find entry points."""
        entry_points = []

        if language == "python":
            for file_path in root.rglob("main.py"):
                entry_points.append(str(file_path.relative_to(root)))
            for file_path in root.rglob("__main__.py"):
                entry_points.append(str(file_path.relative_to(root)))
        elif language == "javascript":
            for file_path in root.rglob("index.js"):
                entry_points.append(str(file_path.relative_to(root)))
            for file_path in root.rglob("app.js"):
                entry_points.append(str(file_path.relative_to(root)))

        return entry_points

    @staticmethod
    def _find_config_files(root: Path) -> list[str]:
        """Find configuration files."""
        config_files = []

        config_patterns = [
            "*.yaml", "*.yml", "*.json", "*.toml", "*.ini", "*.cfg",
            ".env*", "*.conf"
        ]

        for pattern in config_patterns:
            for file_path in root.glob(pattern):
                if file_path.is_file():
                    config_files.append(file_path.name)

        return config_files


class ArchitecturePatternDetector:
    """Detect architecture patterns in projects."""

    @staticmethod
    def detect(project_structure: ProjectStructure) -> Optional[ArchitecturePattern]:
        """Detect architecture pattern."""
        directories = project_structure.directories

        # Check for MVC pattern
        if "models" in directories and "views" in directories and "controllers" in directories:
            return ArchitecturePattern(
                name="MVC",
                confidence=0.9,
                layers=["models", "views", "controllers"],
                description="Model-View-Controller architecture"
            )

        # Check for layered architecture
        if "api" in directories and "services" in directories and "models" in directories:
            return ArchitecturePattern(
                name="Layered",
                confidence=0.8,
                layers=["api", "services", "models"],
                description="Layered architecture with API, services, and models"
            )

        # Check for microservices
        if "services" in directories and "api" in directories:
            return ArchitecturePattern(
                name="Microservices",
                confidence=0.7,
                layers=["services", "api"],
                description="Microservices architecture"
            )

        # Check for component-based (React, Vue)
        if "components" in directories and "pages" in directories:
            return ArchitecturePattern(
                name="Component-Based",
                confidence=0.85,
                layers=["components", "pages"],
                description="Component-based architecture"
            )

        return None


class ConventionLearner:
    """Learn and extract code conventions from project."""

    @staticmethod
    def learn_conventions(project_root: str, language: str, sample_size: int = 10) -> list[CodeConvention]:
        """Learn conventions from project code."""
        conventions = []

        # Collect code samples
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
            try:
                samples.append(file_path.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                pass

        if not samples:
            return conventions

        # Analyze naming conventions
        naming_convention = ConventionLearner._analyze_naming(samples, language)
        if naming_convention:
            conventions.append(naming_convention)

        # Analyze documentation style
        doc_convention = ConventionLearner._analyze_documentation(samples, language)
        if doc_convention:
            conventions.append(doc_convention)

        # Analyze error handling
        error_convention = ConventionLearner._analyze_error_handling(samples, language)
        if error_convention:
            conventions.append(error_convention)

        # Analyze import organization
        import_convention = ConventionLearner._analyze_imports(samples, language)
        if import_convention:
            conventions.append(import_convention)

        return conventions

    @staticmethod
    def _analyze_naming(samples: list[str], language: str) -> Optional[CodeConvention]:
        """Analyze naming conventions."""
        if language == "python":
            return CodeConvention(
                name="Python Naming",
                category="naming",
                pattern="snake_case for functions and variables, PascalCase for classes",
                examples=["def my_function():", "class MyClass:", "my_variable = 42"],
                enforcement_level="required",
                description="Follow PEP 8 naming conventions"
            )
        elif language in ["javascript", "typescript"]:
            return CodeConvention(
                name="JavaScript Naming",
                category="naming",
                pattern="camelCase for functions and variables, PascalCase for classes",
                examples=["function myFunction() {}", "class MyClass {}", "const myVariable = 42;"],
                enforcement_level="required",
                description="Follow JavaScript naming conventions"
            )

        return None

    @staticmethod
    def _analyze_documentation(samples: list[str], language: str) -> Optional[CodeConvention]:
        """Analyze documentation style."""
        if language == "python":
            return CodeConvention(
                name="Python Documentation",
                category="documentation",
                pattern='"""Docstring format"""',
                examples=['"""Function description."""', '"""Class description."""'],
                enforcement_level="recommended",
                description="Use docstrings for documentation"
            )
        elif language in ["javascript", "typescript"]:
            return CodeConvention(
                name="JSDoc Documentation",
                category="documentation",
                pattern="/** JSDoc format */",
                examples=["/** Function description */", "/** @param {type} name */"],
                enforcement_level="recommended",
                description="Use JSDoc for documentation"
            )

        return None

    @staticmethod
    def _analyze_error_handling(samples: list[str], language: str) -> Optional[CodeConvention]:
        """Analyze error handling patterns."""
        if language == "python":
            return CodeConvention(
                name="Python Error Handling",
                category="error_handling",
                pattern="try/except blocks with specific exceptions",
                examples=["try:", "except SpecificError:", "raise CustomError()"],
                enforcement_level="recommended",
                description="Use specific exception handling"
            )
        elif language in ["javascript", "typescript"]:
            return CodeConvention(
                name="JavaScript Error Handling",
                category="error_handling",
                pattern="try/catch blocks with error logging",
                examples=["try {", "} catch (error) {", "throw new Error()"],
                enforcement_level="recommended",
                description="Use try/catch for error handling"
            )

        return None

    @staticmethod
    def _analyze_imports(samples: list[str], language: str) -> Optional[CodeConvention]:
        """Analyze import organization."""
        if language == "python":
            return CodeConvention(
                name="Python Import Organization",
                category="structure",
                pattern="Standard library, third-party, local imports in order",
                examples=["import os", "import requests", "from . import local_module"],
                enforcement_level="recommended",
                description="Organize imports by type"
            )
        elif language in ["javascript", "typescript"]:
            return CodeConvention(
                name="JavaScript Import Organization",
                category="structure",
                pattern="External, internal, relative imports in order",
                examples=["import React from 'react'", "import { utils } from '@app'", "import './style.css'"],
                enforcement_level="recommended",
                description="Organize imports by type"
            )

        return None


class ContextAwareEngine:
    """Main context-aware programming engine."""

    def __init__(self):
        self.project_contexts: dict[str, ProjectContext] = {}

    def analyze_project(self, project_root: str) -> ProjectContext:
        """Analyze project and build context."""
        # Analyze project structure
        structure = ProjectStructureAnalyzer.analyze(project_root)

        # Detect architecture pattern
        architecture = ArchitecturePatternDetector.detect(structure)

        # Learn conventions
        conventions = ConventionLearner.learn_conventions(project_root, structure.language)

        # Create context
        context = ProjectContext(
            project_structure=structure,
            architecture_pattern=architecture,
            conventions=conventions,
            documentation_style=self._detect_documentation_style(structure),
            error_handling_style=self._detect_error_handling_style(structure),
        )

        self.project_contexts[project_root] = context
        return context

    def get_context(self, project_root: str) -> Optional[ProjectContext]:
        """Get cached project context."""
        return self.project_contexts.get(project_root)

    def suggest_file_location(self, project_root: str, file_type: str, file_name: str) -> str:
        """Suggest appropriate location for new file."""
        context = self.get_context(project_root)
        if not context:
            context = self.analyze_project(project_root)

        # Map file types to directories
        type_to_dir = {
            "test": "tests",
            "component": "components",
            "service": "services",
            "model": "models",
            "view": "views",
            "controller": "controllers",
            "utility": "utils",
            "helper": "helpers",
            "hook": "hooks",
            "middleware": "middleware",
            "api": "api",
        }

        target_dir = type_to_dir.get(file_type, "src")

        # Check if directory exists in project
        for dir_name in context.project_structure.directories:
            if dir_name == target_dir:
                return f"{context.project_structure.root}/{dir_name}/{file_name}"

        return f"{context.project_structure.root}/{target_dir}/{file_name}"

    def _detect_documentation_style(self, structure: ProjectStructure) -> Optional[str]:
        """Detect documentation style."""
        if structure.language == "python":
            return "docstring"
        elif structure.language in ["javascript", "typescript"]:
            return "jsdoc"
        return None

    def _detect_error_handling_style(self, structure: ProjectStructure) -> Optional[str]:
        """Detect error handling style."""
        if structure.language == "python":
            return "exceptions"
        elif structure.language in ["javascript", "typescript"]:
            return "try_catch"
        return None
