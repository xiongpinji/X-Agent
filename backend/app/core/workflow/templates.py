"""Workflow Templates and Template Library

Implements workflow templates:
- Template definitions and parameters
- Template inheritance
- Template registry
- Common workflow templates
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class TemplateCategory(StrEnum):
    DATA_PROCESSING = "data_processing"
    WEB_SCRAPING = "web_scraping"
    REPORT_GENERATION = "report_generation"
    API_INTEGRATION = "api_integration"
    NOTIFICATION = "notification"
    APPROVAL = "approval"
    BATCH_PROCESSING = "batch_processing"
    CUSTOM = "custom"


@dataclass
class TemplateParameter:
    """Template parameter definition"""
    name: str
    type: str = "string"  # string, number, boolean, object, array
    description: str = ""
    default: Any = None
    required: bool = False
    enum_values: list[Any] = field(default_factory=list)
    validation_pattern: str | None = None


@dataclass
class WorkflowTemplate:
    """Workflow template definition"""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    category: TemplateCategory = TemplateCategory.CUSTOM
    version: str = "1.0.0"
    parameters: list[TemplateParameter] = field(default_factory=list)
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    parent_template_id: str | None = None
    tags: list[str] = field(default_factory=list)
    author: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    usage_count: int = 0
    rating: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def instantiate(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Instantiate template with parameters"""
        # Validate parameters
        self._validate_parameters(parameters)

        # Create workflow definition
        workflow = {
            "id": str(uuid4()),
            "name": self.name,
            "description": self.description,
            "template_id": self.id,
            "template_version": self.version,
            "nodes": self._substitute_nodes(parameters),
            "edges": self._substitute_edges(parameters),
            "parameters": parameters,
            "created_at": datetime.now(UTC).isoformat(),
        }
        return workflow

    def _validate_parameters(self, parameters: dict[str, Any]) -> None:
        """Validate parameters against template definition"""
        for param in self.parameters:
            if param.required and param.name not in parameters:
                raise ValueError(f"Required parameter missing: {param.name}")

            if param.name in parameters:
                value = parameters[param.name]
                self._validate_parameter_value(param, value)

    def _validate_parameter_value(self, param: TemplateParameter, value: Any) -> None:
        """Validate single parameter value"""
        if param.type == "number":
            if not isinstance(value, (int, float)):
                raise ValueError(f"Parameter {param.name} must be a number")
        elif param.type == "boolean":
            if not isinstance(value, bool):
                raise ValueError(f"Parameter {param.name} must be a boolean")
        elif param.type == "array":
            if not isinstance(value, list):
                raise ValueError(f"Parameter {param.name} must be an array")
        elif param.type == "object":
            if not isinstance(value, dict):
                raise ValueError(f"Parameter {param.name} must be an object")

        if param.enum_values and value not in param.enum_values:
            raise ValueError(f"Parameter {param.name} has invalid value: {value}")

    def _substitute_nodes(self, parameters: dict[str, Any]) -> list[dict[str, Any]]:
        """Substitute parameters in nodes"""
        import json
        result = []
        for node in self.nodes:
            node_str = json.dumps(node)
            for param_name, param_value in parameters.items():
                placeholder = f"${{{param_name}}}"
                node_str = node_str.replace(placeholder, json.dumps(param_value))
            result.append(json.loads(node_str))
        return result

    def _substitute_edges(self, parameters: dict[str, Any]) -> list[dict[str, Any]]:
        """Substitute parameters in edges"""
        import json
        result = []
        for edge in self.edges:
            edge_str = json.dumps(edge)
            for param_name, param_value in parameters.items():
                placeholder = f"${{{param_name}}}"
                edge_str = edge_str.replace(placeholder, json.dumps(param_value))
            result.append(json.loads(edge_str))
        return result

    def to_dict(self) -> dict[str, Any]:
        """Convert template to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "version": self.version,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "default": p.default,
                    "required": p.required,
                }
                for p in self.parameters
            ],
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "tags": self.tags,
            "author": self.author,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "usage_count": self.usage_count,
            "rating": self.rating,
        }


class TemplateRegistry:
    """Registry for workflow templates"""

    def __init__(self):
        self.templates: dict[str, WorkflowTemplate] = {}
        self.categories: dict[TemplateCategory, list[str]] = {
            cat: [] for cat in TemplateCategory
        }

    def register(self, template: WorkflowTemplate) -> None:
        """Register a template"""
        self.templates[template.id] = template
        self.categories[template.category].append(template.id)

    def get(self, template_id: str) -> WorkflowTemplate | None:
        """Get template by ID"""
        return self.templates.get(template_id)

    def list_by_category(self, category: TemplateCategory) -> list[WorkflowTemplate]:
        """List templates by category"""
        template_ids = self.categories.get(category, [])
        return [self.templates[tid] for tid in template_ids if tid in self.templates]

    def search(self, query: str) -> list[WorkflowTemplate]:
        """Search templates by name or description"""
        query_lower = query.lower()
        results = []
        for template in self.templates.values():
            if (query_lower in template.name.lower() or
                query_lower in template.description.lower() or
                any(query_lower in tag.lower() for tag in template.tags)):
                results.append(template)
        return results

    def get_popular(self, limit: int = 10) -> list[WorkflowTemplate]:
        """Get most popular templates"""
        templates = sorted(
            self.templates.values(),
            key=lambda t: (t.usage_count, t.rating),
            reverse=True,
        )
        return templates[:limit]

    def get_recent(self, limit: int = 10) -> list[WorkflowTemplate]:
        """Get recently updated templates"""
        templates = sorted(
            self.templates.values(),
            key=lambda t: t.updated_at,
            reverse=True,
        )
        return templates[:limit]


class TemplateLibrary:
    """Built-in template library"""

    @staticmethod
    def create_data_processing_template() -> WorkflowTemplate:
        """Create data processing template"""
        return WorkflowTemplate(
            name="Data Processing Pipeline",
            description="Process and transform data through multiple stages",
            category=TemplateCategory.DATA_PROCESSING,
            parameters=[
                TemplateParameter(
                    name="input_source",
                    type="string",
                    description="Input data source",
                    required=True,
                ),
                TemplateParameter(
                    name="transformations",
                    type="array",
                    description="List of transformations to apply",
                    required=True,
                ),
                TemplateParameter(
                    name="output_format",
                    type="string",
                    description="Output format",
                    default="json",
                    enum_values=["json", "csv", "parquet"],
                ),
            ],
            nodes=[
                {
                    "id": "input",
                    "type": "input",
                    "config": {"source": "${input_source}"},
                },
                {
                    "id": "transform",
                    "type": "transform",
                    "config": {"transformations": "${transformations}"},
                },
                {
                    "id": "output",
                    "type": "output",
                    "config": {"format": "${output_format}"},
                },
            ],
            edges=[
                {"source": "input", "target": "transform"},
                {"source": "transform", "target": "output"},
            ],
            tags=["data", "processing", "etl"],
        )

    @staticmethod
    def create_web_scraping_template() -> WorkflowTemplate:
        """Create web scraping template"""
        return WorkflowTemplate(
            name="Web Scraping Pipeline",
            description="Scrape and process web content",
            category=TemplateCategory.WEB_SCRAPING,
            parameters=[
                TemplateParameter(
                    name="urls",
                    type="array",
                    description="URLs to scrape",
                    required=True,
                ),
                TemplateParameter(
                    name="selectors",
                    type="object",
                    description="CSS selectors for extraction",
                    required=True,
                ),
                TemplateParameter(
                    name="parallel_requests",
                    type="number",
                    description="Number of parallel requests",
                    default=5,
                ),
            ],
            nodes=[
                {
                    "id": "fetch",
                    "type": "tool",
                    "config": {"tool_name": "fetch_url", "urls": "${urls}"},
                },
                {
                    "id": "extract",
                    "type": "transform",
                    "config": {"selectors": "${selectors}"},
                },
                {
                    "id": "output",
                    "type": "output",
                    "config": {"format": "json"},
                },
            ],
            edges=[
                {"source": "fetch", "target": "extract"},
                {"source": "extract", "target": "output"},
            ],
            tags=["web", "scraping", "extraction"],
        )

    @staticmethod
    def create_approval_workflow_template() -> WorkflowTemplate:
        """Create approval workflow template"""
        return WorkflowTemplate(
            name="Approval Workflow",
            description="Multi-step approval process",
            category=TemplateCategory.APPROVAL,
            parameters=[
                TemplateParameter(
                    name="request_description",
                    type="string",
                    description="Description of request",
                    required=True,
                ),
                TemplateParameter(
                    name="approvers",
                    type="array",
                    description="List of approvers",
                    required=True,
                ),
                TemplateParameter(
                    name="timeout_hours",
                    type="number",
                    description="Approval timeout in hours",
                    default=24,
                ),
            ],
            nodes=[
                {
                    "id": "request",
                    "type": "input",
                    "config": {"description": "${request_description}"},
                },
                {
                    "id": "approval",
                    "type": "approval",
                    "config": {
                        "approvers": "${approvers}",
                        "timeout_hours": "${timeout_hours}",
                    },
                },
                {
                    "id": "approved",
                    "type": "output",
                    "config": {"status": "approved"},
                },
                {
                    "id": "rejected",
                    "type": "output",
                    "config": {"status": "rejected"},
                },
            ],
            edges=[
                {"source": "request", "target": "approval"},
                {"source": "approval", "target": "approved", "condition": "approved"},
                {"source": "approval", "target": "rejected", "condition": "rejected"},
            ],
            tags=["approval", "workflow", "governance"],
        )

    @staticmethod
    def create_notification_template() -> WorkflowTemplate:
        """Create notification template"""
        return WorkflowTemplate(
            name="Notification Pipeline",
            description="Send notifications through multiple channels",
            category=TemplateCategory.NOTIFICATION,
            parameters=[
                TemplateParameter(
                    name="message",
                    type="string",
                    description="Notification message",
                    required=True,
                ),
                TemplateParameter(
                    name="channels",
                    type="array",
                    description="Notification channels",
                    required=True,
                    enum_values=["email", "slack", "webhook"],
                ),
                TemplateParameter(
                    name="recipients",
                    type="array",
                    description="Message recipients",
                    required=True,
                ),
            ],
            nodes=[
                {
                    "id": "prepare",
                    "type": "transform",
                    "config": {"message": "${message}"},
                },
                {
                    "id": "send",
                    "type": "tool",
                    "config": {
                        "tool_name": "send_notification",
                        "channels": "${channels}",
                        "recipients": "${recipients}",
                    },
                },
                {
                    "id": "confirm",
                    "type": "output",
                    "config": {"status": "sent"},
                },
            ],
            edges=[
                {"source": "prepare", "target": "send"},
                {"source": "send", "target": "confirm"},
            ],
            tags=["notification", "communication"],
        )

    @staticmethod
    def create_batch_processing_template() -> WorkflowTemplate:
        """Create batch processing template"""
        return WorkflowTemplate(
            name="Batch Processing Pipeline",
            description="Process items in batches",
            category=TemplateCategory.BATCH_PROCESSING,
            parameters=[
                TemplateParameter(
                    name="items",
                    type="array",
                    description="Items to process",
                    required=True,
                ),
                TemplateParameter(
                    name="batch_size",
                    type="number",
                    description="Batch size",
                    default=10,
                ),
                TemplateParameter(
                    name="processor",
                    type="string",
                    description="Processor tool name",
                    required=True,
                ),
            ],
            nodes=[
                {
                    "id": "input",
                    "type": "input",
                    "config": {"items": "${items}"},
                },
                {
                    "id": "batch_loop",
                    "type": "for_loop",
                    "config": {
                        "iterable": "${items}",
                        "batch_size": "${batch_size}",
                    },
                },
                {
                    "id": "process",
                    "type": "tool",
                    "config": {"tool_name": "${processor}"},
                },
                {
                    "id": "output",
                    "type": "output",
                    "config": {"format": "json"},
                },
            ],
            edges=[
                {"source": "input", "target": "batch_loop"},
                {"source": "batch_loop", "target": "process"},
                {"source": "process", "target": "output"},
            ],
            tags=["batch", "processing", "loop"],
        )

    @staticmethod
    def get_all_templates() -> list[WorkflowTemplate]:
        """Get all built-in templates"""
        return [
            TemplateLibrary.create_data_processing_template(),
            TemplateLibrary.create_web_scraping_template(),
            TemplateLibrary.create_approval_workflow_template(),
            TemplateLibrary.create_notification_template(),
            TemplateLibrary.create_batch_processing_template(),
        ]
