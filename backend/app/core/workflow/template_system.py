"""Advanced Template System for X-Agent

Implements:
- Template definitions with versioning
- Template parameters and validation
- Template inheritance and composition
- Template preview and rendering
- Template storage and retrieval
- Template search and filtering
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Optional
from uuid import uuid4


class TemplateCategory(StrEnum):
    """Template categories"""
    # Workflow templates
    DATA_PROCESSING = "data_processing"
    WEB_SCRAPING = "web_scraping"
    REPORT_GENERATION = "report_generation"
    API_INTEGRATION = "api_integration"
    NOTIFICATION = "notification"
    APPROVAL = "approval"
    BATCH_PROCESSING = "batch_processing"

    # Agent templates
    CODE_REVIEW = "code_review"
    DOCUMENTATION = "documentation"
    BUG_FIXING = "bug_fixing"
    TESTING = "testing"
    REFACTORING = "refactoring"

    # Tool templates
    DATABASE_QUERY = "database_query"
    FILE_OPERATION = "file_operation"
    API_CALL = "api_call"
    DATA_TRANSFORMATION = "data_transformation"

    # Integration templates
    GITHUB_INTEGRATION = "github_integration"
    SLACK_INTEGRATION = "slack_integration"
    JIRA_INTEGRATION = "jira_integration"
    JENKINS_INTEGRATION = "jenkins_integration"

    CUSTOM = "custom"


class TemplateStatus(StrEnum):
    """Template status"""
    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


@dataclass
class TemplateParameter:
    """Template parameter definition"""
    name: str
    type: str = "string"  # string, number, boolean, object, array, select, multiselect
    description: str = ""
    default: Any = None
    required: bool = False
    enum_values: list[Any] = field(default_factory=list)
    validation_pattern: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    placeholder: str = ""
    help_text: str = ""

    def validate(self, value: Any) -> tuple[bool, Optional[str]]:
        """Validate parameter value"""
        # 缺失值处理:None 或空字符串都视为"未提供"
        # 必填项遇到空字符串应判为非法,可选项遇到空字符串放行
        if value is None or (isinstance(value, str) and value == ""):
            if self.required:
                return False, f"Parameter '{self.name}' is required"
            return True, None

        # Type validation
        if self.type == "number":
            if not isinstance(value, (int, float)):
                return False, f"Parameter '{self.name}' must be a number"
            if self.min_value is not None and value < self.min_value:
                return False, f"Parameter '{self.name}' must be >= {self.min_value}"
            if self.max_value is not None and value > self.max_value:
                return False, f"Parameter '{self.name}' must be <= {self.max_value}"

        elif self.type == "string":
            if not isinstance(value, str):
                return False, f"Parameter '{self.name}' must be a string"
            if self.min_length is not None and len(value) < self.min_length:
                return False, f"Parameter '{self.name}' must be at least {self.min_length} characters"
            if self.max_length is not None and len(value) > self.max_length:
                return False, f"Parameter '{self.name}' must be at most {self.max_length} characters"
            if self.validation_pattern and not re.match(self.validation_pattern, value):
                return False, f"Parameter '{self.name}' does not match required pattern"

        elif self.type == "boolean":
            if not isinstance(value, bool):
                return False, f"Parameter '{self.name}' must be a boolean"

        elif self.type in ("array", "multiselect"):
            if not isinstance(value, list):
                return False, f"Parameter '{self.name}' must be an array"

        elif self.type == "object":
            if not isinstance(value, dict):
                return False, f"Parameter '{self.name}' must be an object"

        # Enum validation
        if self.enum_values and value not in self.enum_values:
            return False, f"Parameter '{self.name}' has invalid value: {value}"

        return True, None


@dataclass
class TemplateNode:
    """Template node definition"""
    id: str
    type: str  # input, output, transform, tool, agent, condition, wait, approval
    name: str = ""
    description: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    position: dict[str, float] = field(default_factory=lambda: {"x": 0, "y": 0})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TemplateEdge:
    """Template edge definition"""
    source: str
    target: str
    condition: Optional[str] = None
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WorkflowTemplate:
    """Workflow template definition"""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    category: TemplateCategory = TemplateCategory.CUSTOM
    version: str = "1.0.0"
    status: TemplateStatus = TemplateStatus.DRAFT

    # Parameters
    parameters: list[TemplateParameter] = field(default_factory=list)

    # Structure
    nodes: list[TemplateNode] = field(default_factory=list)
    edges: list[TemplateEdge] = field(default_factory=list)

    # Metadata
    parent_template_id: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    author: str = ""
    author_id: str = ""

    # Statistics
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    usage_count: int = 0
    rating: float = 0.0
    review_count: int = 0

    # Additional metadata
    icon: str = ""
    thumbnail: str = ""
    documentation_url: str = ""
    example_inputs: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate_parameters(self, parameters: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate parameters against template definition"""
        errors = []

        for param in self.parameters:
            valid, error = param.validate(parameters.get(param.name))
            if not valid:
                errors.append(error)

        # Check for unknown parameters
        known_params = {p.name for p in self.parameters}
        for param_name in parameters:
            if param_name not in known_params:
                errors.append(f"Unknown parameter: {param_name}")

        return len(errors) == 0, errors

    def instantiate(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Instantiate template with parameters"""
        # Validate parameters
        valid, errors = self.validate_parameters(parameters)
        if not valid:
            raise ValueError(f"Parameter validation failed: {'; '.join(errors)}")

        # Substitute parameters in nodes and edges
        substituted_nodes = self._substitute_nodes(parameters)
        substituted_edges = self._substitute_edges(parameters)

        # Create workflow definition
        workflow = {
            "id": str(uuid4()),
            "name": self.name,
            "description": self.description,
            "template_id": self.id,
            "template_version": self.version,
            "nodes": substituted_nodes,
            "edges": substituted_edges,
            "parameters": parameters,
            "created_at": datetime.now(UTC).isoformat(),
        }
        return workflow

    def _substitute_value(self, value: Any, parameters: dict[str, Any]) -> Any:
        """递归替换单个值中的 ${param} 占位符。

        - 整值占位(如 "${count}")保留参数原始类型(数字、对象、数组等)
        - 内嵌占位(如 "Hello ${name}")做字符串插值
        - dict / list 递归处理
        """
        if isinstance(value, str):
            # 整值占位:整个字符串恰好是单个 ${param},直接返回原始类型值
            full_match = re.fullmatch(r"\$\{(\w+)\}", value)
            if full_match:
                param_name = full_match.group(1)
                if param_name in parameters:
                    return parameters[param_name]
                return value

            # 内嵌占位:逐个替换为字符串形式
            def _repl(match: re.Match) -> str:
                param_name = match.group(1)
                if param_name in parameters:
                    return str(parameters[param_name])
                return match.group(0)

            return re.sub(r"\$\{(\w+)\}", _repl, value)

        if isinstance(value, dict):
            return {k: self._substitute_value(v, parameters) for k, v in value.items()}

        if isinstance(value, list):
            return [self._substitute_value(item, parameters) for item in value]

        return value

    def _substitute_nodes(self, parameters: dict[str, Any]) -> list[dict[str, Any]]:
        """Substitute parameters in nodes"""
        result = []
        for node in self.nodes:
            node_dict = node.to_dict()
            result.append(self._substitute_value(node_dict, parameters))
        return result

    def _substitute_edges(self, parameters: dict[str, Any]) -> list[dict[str, Any]]:
        """Substitute parameters in edges"""
        result = []
        for edge in self.edges:
            edge_dict = edge.to_dict()
            result.append(self._substitute_value(edge_dict, parameters))
        return result

    def to_dict(self) -> dict[str, Any]:
        """Convert template to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "version": self.version,
            "status": self.status.value,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "default": p.default,
                    "required": p.required,
                    "enum_values": p.enum_values,
                    "validation_pattern": p.validation_pattern,
                    "min_value": p.min_value,
                    "max_value": p.max_value,
                    "min_length": p.min_length,
                    "max_length": p.max_length,
                    "placeholder": p.placeholder,
                    "help_text": p.help_text,
                }
                for p in self.parameters
            ],
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "tags": self.tags,
            "author": self.author,
            "author_id": self.author_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "usage_count": self.usage_count,
            "rating": self.rating,
            "review_count": self.review_count,
            "icon": self.icon,
            "thumbnail": self.thumbnail,
            "documentation_url": self.documentation_url,
            "example_inputs": self.example_inputs,
        }


class TemplateRegistry:
    """Registry for workflow templates"""

    def __init__(self):
        self.templates: dict[str, WorkflowTemplate] = {}
        self.categories: dict[TemplateCategory, list[str]] = {
            cat: [] for cat in TemplateCategory
        }
        self.tags_index: dict[str, list[str]] = {}

    def register(self, template: WorkflowTemplate) -> None:
        """Register a template"""
        self.templates[template.id] = template
        self.categories[template.category].append(template.id)

        # Index tags
        for tag in template.tags:
            if tag not in self.tags_index:
                self.tags_index[tag] = []
            self.tags_index[tag].append(template.id)

    def unregister(self, template_id: str) -> bool:
        """Unregister a template"""
        template = self.templates.get(template_id)
        if not template:
            return False

        # Remove from categories
        if template.category in self.categories:
            self.categories[template.category].remove(template_id)

        # Remove from tags index
        for tag in template.tags:
            if tag in self.tags_index:
                self.tags_index[tag].remove(template_id)

        del self.templates[template_id]
        return True

    def get(self, template_id: str) -> Optional[WorkflowTemplate]:
        """Get template by ID"""
        return self.templates.get(template_id)

    def list_all(self) -> list[WorkflowTemplate]:
        """List all templates"""
        return list(self.templates.values())

    def list_by_category(self, category: TemplateCategory) -> list[WorkflowTemplate]:
        """List templates by category"""
        template_ids = self.categories.get(category, [])
        return [self.templates[tid] for tid in template_ids if tid in self.templates]

    def list_by_status(self, status: TemplateStatus) -> list[WorkflowTemplate]:
        """List templates by status"""
        return [t for t in self.templates.values() if t.status == status]

    def list_by_tag(self, tag: str) -> list[WorkflowTemplate]:
        """List templates by tag"""
        template_ids = self.tags_index.get(tag, [])
        return [self.templates[tid] for tid in template_ids if tid in self.templates]

    def search(self, query: str, category: Optional[TemplateCategory] = None) -> list[WorkflowTemplate]:
        """Search templates by name, description, or tags"""
        query_lower = query.lower()
        results = []

        for template in self.templates.values():
            # Filter by category if specified
            if category and template.category != category:
                continue

            # Match query
            if (query_lower in template.name.lower() or
                query_lower in template.description.lower() or
                any(query_lower in tag.lower() for tag in template.tags)):
                results.append(template)

        return results

    def get_popular(self, limit: int = 10, category: Optional[TemplateCategory] = None) -> list[WorkflowTemplate]:
        """Get most popular templates"""
        templates = [t for t in self.templates.values() if t.status == TemplateStatus.PUBLISHED]

        if category:
            templates = [t for t in templates if t.category == category]

        templates = sorted(
            templates,
            key=lambda t: (t.usage_count, t.rating),
            reverse=True,
        )
        return templates[:limit]

    def get_recent(self, limit: int = 10, category: Optional[TemplateCategory] = None) -> list[WorkflowTemplate]:
        """Get recently updated templates"""
        templates = [t for t in self.templates.values() if t.status == TemplateStatus.PUBLISHED]

        if category:
            templates = [t for t in templates if t.category == category]

        templates = sorted(
            templates,
            key=lambda t: t.updated_at,
            reverse=True,
        )
        return templates[:limit]

    def get_top_rated(self, limit: int = 10, category: Optional[TemplateCategory] = None) -> list[WorkflowTemplate]:
        """Get top rated templates"""
        templates = [t for t in self.templates.values() if t.status == TemplateStatus.PUBLISHED and t.review_count > 0]

        if category:
            templates = [t for t in templates if t.category == category]

        templates = sorted(
            templates,
            key=lambda t: t.rating,
            reverse=True,
        )
        return templates[:limit]

    def get_statistics(self) -> dict[str, Any]:
        """Get registry statistics"""
        templates = list(self.templates.values())
        published = [t for t in templates if t.status == TemplateStatus.PUBLISHED]

        return {
            "total_templates": len(templates),
            "published_templates": len(published),
            "draft_templates": len([t for t in templates if t.status == TemplateStatus.DRAFT]),
            "deprecated_templates": len([t for t in templates if t.status == TemplateStatus.DEPRECATED]),
            "total_usage": sum(t.usage_count for t in templates),
            "average_rating": sum(t.rating for t in published) / len(published) if published else 0,
            "categories": {cat.value: len(self.categories[cat]) for cat in TemplateCategory},
        }


# Global template registry instance
_template_registry: Optional[TemplateRegistry] = None


def get_template_registry() -> TemplateRegistry:
    """Get or create global template registry"""
    global _template_registry
    if _template_registry is None:
        _template_registry = TemplateRegistry()
    return _template_registry
