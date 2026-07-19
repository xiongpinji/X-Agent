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
    CODE_REVIEW = "code_review"
    CUSTOM = "custom"
    # Additional categories used by TemplateLibrary methods
    DOCUMENTATION = "documentation"
    BUG_FIXING = "bug_fixing"
    TESTING = "testing"
    REFACTORING = "refactoring"
    DATABASE_QUERY = "database_query"
    FILE_OPERATION = "file_operation"
    API_CALL = "api_call"
    DATA_TRANSFORMATION = "data_transformation"
    GITHUB_INTEGRATION = "github_integration"
    SLACK_INTEGRATION = "slack_integration"
    JIRA_INTEGRATION = "jira_integration"
    JENKINS_INTEGRATION = "jenkins_integration"


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
        return [self._substitute_value(node, parameters) for node in self.nodes]

    def _substitute_edges(self, parameters: dict[str, Any]) -> list[dict[str, Any]]:
        """Substitute parameters in edges"""
        return [self._substitute_value(edge, parameters) for edge in self.edges]

    def _substitute_value(self, value: Any, parameters: dict[str, Any]) -> Any:
        """Recursively substitute ${param} placeholders in a value.

        A placeholder that is the entire string (e.g. "${source}") is replaced
        with the parameter's typed value (preserving lists, numbers, dicts).
        A placeholder embedded within a larger string is replaced with the
        string form of the value (interpolation).
        """
        if isinstance(value, dict):
            return {k: self._substitute_value(v, parameters) for k, v in value.items()}
        if isinstance(value, list):
            return [self._substitute_value(item, parameters) for item in value]
        if isinstance(value, str):
            # Whole-value placeholder: preserve the parameter's native type.
            for param_name, param_value in parameters.items():
                if value == f"${{{param_name}}}":
                    return param_value
            # Embedded placeholder(s): interpolate as string.
            result = value
            for param_name, param_value in parameters.items():
                placeholder = f"${{{param_name}}}"
                if placeholder in result:
                    result = result.replace(placeholder, str(param_value))
            return result
        return value

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
    def create_code_review_template() -> WorkflowTemplate:
        """Create code review template"""
        return WorkflowTemplate(
            name="Code Review Pipeline",
            description="Automated code review and quality checks",
            category=TemplateCategory.CODE_REVIEW,
            parameters=[
                TemplateParameter(
                    name="repository_url",
                    type="string",
                    description="Repository URL",
                    required=True,
                ),
                TemplateParameter(
                    name="pull_request_id",
                    type="number",
                    description="Pull request ID",
                    required=True,
                ),
                TemplateParameter(
                    name="review_criteria",
                    type="array",
                    description="Review criteria",
                    default=["code_style", "security", "performance"],
                ),
            ],
            nodes=[
                {
                    "id": "fetch_pr",
                    "type": "tool",
                    "config": {"tool_name": "fetch_pull_request", "url": "${repository_url}", "pr_id": "${pull_request_id}"},
                },
                {
                    "id": "analyze",
                    "type": "agent",
                    "config": {"agent_type": "code_reviewer", "criteria": "${review_criteria}"},
                },
                {
                    "id": "report",
                    "type": "output",
                    "config": {"format": "markdown"},
                },
            ],
            edges=[
                {"source": "fetch_pr", "target": "analyze"},
                {"source": "analyze", "target": "report"},
            ],
            tags=["code", "review", "quality"],
        )

    @staticmethod
    def create_documentation_template() -> WorkflowTemplate:
        """Create documentation generation template"""
        return WorkflowTemplate(
            name="Documentation Generator",
            description="Generate documentation from code",
            category=TemplateCategory.DOCUMENTATION,
            parameters=[
                TemplateParameter(
                    name="source_path",
                    type="string",
                    description="Source code path",
                    required=True,
                ),
                TemplateParameter(
                    name="doc_format",
                    type="select",
                    description="Documentation format",
                    default="markdown",
                    enum_values=["markdown", "html", "pdf"],
                ),
            ],
            nodes=[
                {
                    "id": "read_code",
                    "type": "tool",
                    "config": {"tool_name": "read_files", "path": "${source_path}"},
                },
                {
                    "id": "generate_docs",
                    "type": "agent",
                    "config": {"agent_type": "doc_generator"},
                },
                {
                    "id": "format",
                    "type": "transform",
                    "config": {"format": "${doc_format}"},
                },
                {
                    "id": "output",
                    "type": "output",
                    "config": {"format": "${doc_format}"},
                },
            ],
            edges=[
                {"source": "read_code", "target": "generate_docs"},
                {"source": "generate_docs", "target": "format"},
                {"source": "format", "target": "output"},
            ],
            tags=["documentation", "generation", "code"],
        )

    @staticmethod
    def create_bug_fixing_template() -> WorkflowTemplate:
        """Create bug fixing template"""
        return WorkflowTemplate(
            name="Bug Fixing Pipeline",
            description="Automated bug detection and fixing",
            category=TemplateCategory.BUG_FIXING,
            parameters=[
                TemplateParameter(
                    name="bug_description",
                    type="string",
                    description="Bug description",
                    required=True,
                ),
                TemplateParameter(
                    name="file_path",
                    type="string",
                    description="File to fix",
                    required=True,
                ),
            ],
            nodes=[
                {
                    "id": "read_file",
                    "type": "tool",
                    "config": {"tool_name": "read_file", "path": "${file_path}"},
                },
                {
                    "id": "analyze_bug",
                    "type": "agent",
                    "config": {"agent_type": "bug_analyzer", "description": "${bug_description}"},
                },
                {
                    "id": "generate_fix",
                    "type": "agent",
                    "config": {"agent_type": "code_fixer"},
                },
                {
                    "id": "output",
                    "type": "output",
                    "config": {"format": "code"},
                },
            ],
            edges=[
                {"source": "read_file", "target": "analyze_bug"},
                {"source": "analyze_bug", "target": "generate_fix"},
                {"source": "generate_fix", "target": "output"},
            ],
            tags=["bug", "fixing", "debugging"],
        )

    @staticmethod
    def create_testing_template() -> WorkflowTemplate:
        """Create testing template"""
        return WorkflowTemplate(
            name="Automated Testing Pipeline",
            description="Run automated tests and generate reports",
            category=TemplateCategory.TESTING,
            parameters=[
                TemplateParameter(
                    name="test_path",
                    type="string",
                    description="Test directory path",
                    required=True,
                ),
                TemplateParameter(
                    name="test_framework",
                    type="select",
                    description="Test framework",
                    default="pytest",
                    enum_values=["pytest", "unittest", "jest", "mocha"],
                ),
            ],
            nodes=[
                {
                    "id": "discover_tests",
                    "type": "tool",
                    "config": {"tool_name": "discover_tests", "path": "${test_path}"},
                },
                {
                    "id": "run_tests",
                    "type": "tool",
                    "config": {"tool_name": "run_tests", "framework": "${test_framework}"},
                },
                {
                    "id": "generate_report",
                    "type": "transform",
                    "config": {"format": "html"},
                },
                {
                    "id": "output",
                    "type": "output",
                    "config": {"format": "html"},
                },
            ],
            edges=[
                {"source": "discover_tests", "target": "run_tests"},
                {"source": "run_tests", "target": "generate_report"},
                {"source": "generate_report", "target": "output"},
            ],
            tags=["testing", "automation", "quality"],
        )

    @staticmethod
    def create_refactoring_template() -> WorkflowTemplate:
        """Create refactoring template"""
        return WorkflowTemplate(
            name="Code Refactoring Pipeline",
            description="Refactor code for better quality",
            category=TemplateCategory.REFACTORING,
            parameters=[
                TemplateParameter(
                    name="source_code",
                    type="string",
                    description="Source code to refactor",
                    required=True,
                ),
                TemplateParameter(
                    name="refactoring_goals",
                    type="array",
                    description="Refactoring goals",
                    default=["readability", "performance"],
                ),
            ],
            nodes=[
                {
                    "id": "analyze_code",
                    "type": "agent",
                    "config": {"agent_type": "code_analyzer"},
                },
                {
                    "id": "plan_refactoring",
                    "type": "agent",
                    "config": {"agent_type": "refactoring_planner", "goals": "${refactoring_goals}"},
                },
                {
                    "id": "apply_refactoring",
                    "type": "agent",
                    "config": {"agent_type": "code_refactorer"},
                },
                {
                    "id": "output",
                    "type": "output",
                    "config": {"format": "code"},
                },
            ],
            edges=[
                {"source": "analyze_code", "target": "plan_refactoring"},
                {"source": "plan_refactoring", "target": "apply_refactoring"},
                {"source": "apply_refactoring", "target": "output"},
            ],
            tags=["refactoring", "code", "quality"],
        )

    @staticmethod
    def create_database_query_template() -> WorkflowTemplate:
        """Create database query template"""
        return WorkflowTemplate(
            name="Database Query Pipeline",
            description="Execute and optimize database queries",
            category=TemplateCategory.DATABASE_QUERY,
            parameters=[
                TemplateParameter(
                    name="database_url",
                    type="string",
                    description="Database connection URL",
                    required=True,
                ),
                TemplateParameter(
                    name="query",
                    type="string",
                    description="SQL query",
                    required=True,
                ),
            ],
            nodes=[
                {
                    "id": "connect",
                    "type": "tool",
                    "config": {"tool_name": "connect_database", "url": "${database_url}"},
                },
                {
                    "id": "execute",
                    "type": "tool",
                    "config": {"tool_name": "execute_query", "query": "${query}"},
                },
                {
                    "id": "format_results",
                    "type": "transform",
                    "config": {"format": "json"},
                },
                {
                    "id": "output",
                    "type": "output",
                    "config": {"format": "json"},
                },
            ],
            edges=[
                {"source": "connect", "target": "execute"},
                {"source": "execute", "target": "format_results"},
                {"source": "format_results", "target": "output"},
            ],
            tags=["database", "query", "sql"],
        )

    @staticmethod
    def create_file_operation_template() -> WorkflowTemplate:
        """Create file operation template"""
        return WorkflowTemplate(
            name="File Operation Pipeline",
            description="Perform file operations and transformations",
            category=TemplateCategory.FILE_OPERATION,
            parameters=[
                TemplateParameter(
                    name="source_path",
                    type="string",
                    description="Source file path",
                    required=True,
                ),
                TemplateParameter(
                    name="operation",
                    type="select",
                    description="Operation type",
                    default="read",
                    enum_values=["read", "write", "copy", "move", "delete"],
                ),
            ],
            nodes=[
                {
                    "id": "prepare",
                    "type": "transform",
                    "config": {"operation": "${operation}"},
                },
                {
                    "id": "execute",
                    "type": "tool",
                    "config": {"tool_name": "file_operation", "path": "${source_path}"},
                },
                {
                    "id": "output",
                    "type": "output",
                    "config": {"format": "json"},
                },
            ],
            edges=[
                {"source": "prepare", "target": "execute"},
                {"source": "execute", "target": "output"},
            ],
            tags=["file", "operation", "io"],
        )

    @staticmethod
    def create_api_call_template() -> WorkflowTemplate:
        """Create API call template"""
        return WorkflowTemplate(
            name="API Call Pipeline",
            description="Make and process API calls",
            category=TemplateCategory.API_CALL,
            parameters=[
                TemplateParameter(
                    name="api_url",
                    type="string",
                    description="API endpoint URL",
                    required=True,
                ),
                TemplateParameter(
                    name="method",
                    type="select",
                    description="HTTP method",
                    default="GET",
                    enum_values=["GET", "POST", "PUT", "DELETE", "PATCH"],
                ),
                TemplateParameter(
                    name="headers",
                    type="object",
                    description="Request headers",
                    default={},
                ),
            ],
            nodes=[
                {
                    "id": "prepare_request",
                    "type": "transform",
                    "config": {"method": "${method}", "headers": "${headers}"},
                },
                {
                    "id": "call_api",
                    "type": "tool",
                    "config": {"tool_name": "http_request", "url": "${api_url}"},
                },
                {
                    "id": "process_response",
                    "type": "transform",
                    "config": {"format": "json"},
                },
                {
                    "id": "output",
                    "type": "output",
                    "config": {"format": "json"},
                },
            ],
            edges=[
                {"source": "prepare_request", "target": "call_api"},
                {"source": "call_api", "target": "process_response"},
                {"source": "process_response", "target": "output"},
            ],
            tags=["api", "http", "integration"],
        )

    @staticmethod
    def create_data_transformation_template() -> WorkflowTemplate:
        """Create data transformation template"""
        return WorkflowTemplate(
            name="Data Transformation Pipeline",
            description="Transform and normalize data",
            category=TemplateCategory.DATA_TRANSFORMATION,
            parameters=[
                TemplateParameter(
                    name="input_format",
                    type="select",
                    description="Input data format",
                    default="json",
                    enum_values=["json", "csv", "xml", "parquet"],
                ),
                TemplateParameter(
                    name="output_format",
                    type="select",
                    description="Output data format",
                    default="json",
                    enum_values=["json", "csv", "xml", "parquet"],
                ),
            ],
            nodes=[
                {
                    "id": "parse_input",
                    "type": "transform",
                    "config": {"format": "${input_format}"},
                },
                {
                    "id": "normalize",
                    "type": "transform",
                    "config": {"operation": "normalize"},
                },
                {
                    "id": "format_output",
                    "type": "transform",
                    "config": {"format": "${output_format}"},
                },
                {
                    "id": "output",
                    "type": "output",
                    "config": {"format": "${output_format}"},
                },
            ],
            edges=[
                {"source": "parse_input", "target": "normalize"},
                {"source": "normalize", "target": "format_output"},
                {"source": "format_output", "target": "output"},
            ],
            tags=["data", "transformation", "etl"],
        )

    @staticmethod
    def create_github_integration_template() -> WorkflowTemplate:
        """Create GitHub integration template"""
        return WorkflowTemplate(
            name="GitHub Integration Pipeline",
            description="Integrate with GitHub repositories",
            category=TemplateCategory.GITHUB_INTEGRATION,
            parameters=[
                TemplateParameter(
                    name="github_token",
                    type="string",
                    description="GitHub API token",
                    required=True,
                ),
                TemplateParameter(
                    name="repository",
                    type="string",
                    description="Repository (owner/repo)",
                    required=True,
                ),
                TemplateParameter(
                    name="action",
                    type="select",
                    description="Action to perform",
                    default="list_issues",
                    enum_values=["list_issues", "create_issue", "list_prs", "create_pr"],
                ),
            ],
            nodes=[
                {
                    "id": "authenticate",
                    "type": "tool",
                    "config": {"tool_name": "github_auth", "token": "${github_token}"},
                },
                {
                    "id": "execute_action",
                    "type": "tool",
                    "config": {"tool_name": "github_action", "repo": "${repository}", "action": "${action}"},
                },
                {
                    "id": "output",
                    "type": "output",
                    "config": {"format": "json"},
                },
            ],
            edges=[
                {"source": "authenticate", "target": "execute_action"},
                {"source": "execute_action", "target": "output"},
            ],
            tags=["github", "integration", "vcs"],
        )

    @staticmethod
    def create_slack_integration_template() -> WorkflowTemplate:
        """Create Slack integration template"""
        return WorkflowTemplate(
            name="Slack Integration Pipeline",
            description="Send messages to Slack",
            category=TemplateCategory.SLACK_INTEGRATION,
            parameters=[
                TemplateParameter(
                    name="webhook_url",
                    type="string",
                    description="Slack webhook URL",
                    required=True,
                ),
                TemplateParameter(
                    name="message",
                    type="string",
                    description="Message to send",
                    required=True,
                ),
                TemplateParameter(
                    name="channel",
                    type="string",
                    description="Target channel",
                    default="#general",
                ),
            ],
            nodes=[
                {
                    "id": "prepare_message",
                    "type": "transform",
                    "config": {"message": "${message}", "channel": "${channel}"},
                },
                {
                    "id": "send",
                    "type": "tool",
                    "config": {"tool_name": "slack_send", "webhook": "${webhook_url}"},
                },
                {
                    "id": "output",
                    "type": "output",
                    "config": {"format": "json"},
                },
            ],
            edges=[
                {"source": "prepare_message", "target": "send"},
                {"source": "send", "target": "output"},
            ],
            tags=["slack", "notification", "integration"],
        )

    @staticmethod
    def create_jira_integration_template() -> WorkflowTemplate:
        """Create Jira integration template"""
        return WorkflowTemplate(
            name="Jira Integration Pipeline",
            description="Manage Jira issues",
            category=TemplateCategory.JIRA_INTEGRATION,
            parameters=[
                TemplateParameter(
                    name="jira_url",
                    type="string",
                    description="Jira instance URL",
                    required=True,
                ),
                TemplateParameter(
                    name="api_token",
                    type="string",
                    description="Jira API token",
                    required=True,
                ),
                TemplateParameter(
                    name="project_key",
                    type="string",
                    description="Project key",
                    required=True,
                ),
            ],
            nodes=[
                {
                    "id": "authenticate",
                    "type": "tool",
                    "config": {"tool_name": "jira_auth", "url": "${jira_url}", "token": "${api_token}"},
                },
                {
                    "id": "query_issues",
                    "type": "tool",
                    "config": {"tool_name": "jira_query", "project": "${project_key}"},
                },
                {
                    "id": "output",
                    "type": "output",
                    "config": {"format": "json"},
                },
            ],
            edges=[
                {"source": "authenticate", "target": "query_issues"},
                {"source": "query_issues", "target": "output"},
            ],
            tags=["jira", "issue_tracking", "integration"],
        )

    @staticmethod
    def create_jenkins_integration_template() -> WorkflowTemplate:
        """Create Jenkins integration template"""
        return WorkflowTemplate(
            name="Jenkins Integration Pipeline",
            description="Trigger and monitor Jenkins builds",
            category=TemplateCategory.JENKINS_INTEGRATION,
            parameters=[
                TemplateParameter(
                    name="jenkins_url",
                    type="string",
                    description="Jenkins instance URL",
                    required=True,
                ),
                TemplateParameter(
                    name="job_name",
                    type="string",
                    description="Job name",
                    required=True,
                ),
                TemplateParameter(
                    name="credentials",
                    type="object",
                    description="Jenkins credentials",
                    required=True,
                ),
            ],
            nodes=[
                {
                    "id": "authenticate",
                    "type": "tool",
                    "config": {"tool_name": "jenkins_auth", "url": "${jenkins_url}"},
                },
                {
                    "id": "trigger_build",
                    "type": "tool",
                    "config": {"tool_name": "jenkins_trigger", "job": "${job_name}"},
                },
                {
                    "id": "monitor",
                    "type": "wait",
                    "config": {"timeout": 3600},
                },
                {
                    "id": "output",
                    "type": "output",
                    "config": {"format": "json"},
                },
            ],
            edges=[
                {"source": "authenticate", "target": "trigger_build"},
                {"source": "trigger_build", "target": "monitor"},
                {"source": "monitor", "target": "output"},
            ],
            tags=["jenkins", "ci_cd", "integration"],
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
            TemplateLibrary.create_code_review_template(),
            TemplateLibrary.create_documentation_template(),
            TemplateLibrary.create_bug_fixing_template(),
            TemplateLibrary.create_testing_template(),
            TemplateLibrary.create_refactoring_template(),
            TemplateLibrary.create_database_query_template(),
            TemplateLibrary.create_file_operation_template(),
            TemplateLibrary.create_api_call_template(),
            TemplateLibrary.create_data_transformation_template(),
            TemplateLibrary.create_github_integration_template(),
            TemplateLibrary.create_slack_integration_template(),
            TemplateLibrary.create_jira_integration_template(),
            TemplateLibrary.create_jenkins_integration_template(),
        ]
