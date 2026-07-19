"""Template System Integration Tests

Tests for:
- Template creation and validation
- Parameter validation
- Template instantiation
- Template search and filtering
- Template registry operations
"""

import pytest
from datetime import UTC, datetime
from backend.app.core.workflow.template_system import (
    WorkflowTemplate,
    TemplateParameter,
    TemplateNode,
    TemplateEdge,
    TemplateCategory,
    TemplateStatus,
    TemplateRegistry,
    get_template_registry,
)


class TestTemplateParameter:
    """Test TemplateParameter validation"""

    def test_string_parameter_validation(self):
        """Test string parameter validation"""
        param = TemplateParameter(
            name="test",
            type="string",
            required=True,
            min_length=3,
            max_length=10,
        )

        # Valid
        valid, error = param.validate("hello")
        assert valid
        assert error is None

        # Too short
        valid, error = param.validate("ab")
        assert not valid
        assert "at least 3 characters" in error

        # Too long
        valid, error = param.validate("hello world!")
        assert not valid
        assert "at most 10 characters" in error

    def test_number_parameter_validation(self):
        """Test number parameter validation"""
        param = TemplateParameter(
            name="count",
            type="number",
            required=True,
            min_value=1,
            max_value=100,
        )

        # Valid
        valid, error = param.validate(50)
        assert valid

        # Too small
        valid, error = param.validate(0)
        assert not valid

        # Too large
        valid, error = param.validate(101)
        assert not valid

    def test_enum_parameter_validation(self):
        """Test enum parameter validation"""
        param = TemplateParameter(
            name="format",
            type="select",
            enum_values=["json", "csv", "xml"],
        )

        # Valid
        valid, error = param.validate("json")
        assert valid

        # Invalid
        valid, error = param.validate("yaml")
        assert not valid

    def test_required_parameter_validation(self):
        """Test required parameter validation"""
        param = TemplateParameter(
            name="required_field",
            type="string",
            required=True,
        )

        # Missing
        valid, error = param.validate(None)
        assert not valid
        assert "required" in error.lower()

        # Empty string
        valid, error = param.validate("")
        assert not valid


class TestWorkflowTemplate:
    """Test WorkflowTemplate operations"""

    def test_template_creation(self):
        """Test template creation"""
        template = WorkflowTemplate(
            name="Test Template",
            description="A test template",
            category=TemplateCategory.CUSTOM,
        )

        assert template.name == "Test Template"
        assert template.category == TemplateCategory.CUSTOM
        assert template.status == TemplateStatus.DRAFT

    def test_template_parameter_validation(self):
        """Test template parameter validation"""
        template = WorkflowTemplate(
            name="Test",
            parameters=[
                TemplateParameter(
                    name="input",
                    type="string",
                    required=True,
                ),
                TemplateParameter(
                    name="count",
                    type="number",
                    default=10,
                ),
            ],
        )

        # Valid
        valid, errors = template.validate_parameters({
            "input": "test",
            "count": 5,
        })
        assert valid
        assert len(errors) == 0

        # Missing required
        valid, errors = template.validate_parameters({
            "count": 5,
        })
        assert not valid
        assert len(errors) > 0

    def test_template_instantiation(self):
        """Test template instantiation"""
        template = WorkflowTemplate(
            name="Test",
            parameters=[
                TemplateParameter(
                    name="source",
                    type="string",
                    required=True,
                ),
            ],
            nodes=[
                TemplateNode(
                    id="input",
                    type="input",
                    config={"source": "${source}"},
                ),
            ],
        )

        workflow = template.instantiate({
            "source": "test_data",
        })

        assert workflow["template_id"] == template.id
        assert workflow["nodes"][0]["config"]["source"] == "test_data"

    def test_template_to_dict(self):
        """Test template serialization"""
        template = WorkflowTemplate(
            name="Test",
            description="Test template",
            category=TemplateCategory.DATA_PROCESSING,
            version="1.0.0",
        )

        data = template.to_dict()

        assert data["name"] == "Test"
        assert data["category"] == "data_processing"
        assert data["version"] == "1.0.0"


class TestTemplateRegistry:
    """Test TemplateRegistry operations"""

    def test_register_template(self):
        """Test template registration"""
        registry = TemplateRegistry()
        template = WorkflowTemplate(
            name="Test",
            category=TemplateCategory.CUSTOM,
        )

        registry.register(template)

        assert registry.get(template.id) == template

    def test_list_by_category(self):
        """Test listing templates by category"""
        registry = TemplateRegistry()

        t1 = WorkflowTemplate(
            name="Data Processing",
            category=TemplateCategory.DATA_PROCESSING,
        )
        t2 = WorkflowTemplate(
            name="Web Scraping",
            category=TemplateCategory.WEB_SCRAPING,
        )

        registry.register(t1)
        registry.register(t2)

        results = registry.list_by_category(TemplateCategory.DATA_PROCESSING)
        assert len(results) == 1
        assert results[0].name == "Data Processing"

    def test_search_templates(self):
        """Test template search"""
        registry = TemplateRegistry()

        t1 = WorkflowTemplate(
            name="Data Processing Pipeline",
            description="Process data",
            category=TemplateCategory.DATA_PROCESSING,
            tags=["data", "etl"],
        )
        t2 = WorkflowTemplate(
            name="Web Scraping",
            description="Scrape websites",
            category=TemplateCategory.WEB_SCRAPING,
            tags=["web"],
        )

        registry.register(t1)
        registry.register(t2)

        # Search by name
        results = registry.search("data")
        assert len(results) == 1
        assert results[0].name == "Data Processing Pipeline"

        # Search by tag
        results = registry.search("etl")
        assert len(results) == 1

    def test_get_popular_templates(self):
        """Test getting popular templates"""
        registry = TemplateRegistry()

        t1 = WorkflowTemplate(
            name="Popular",
            status=TemplateStatus.PUBLISHED,
            usage_count=100,
            rating=4.5,
        )
        t2 = WorkflowTemplate(
            name="Less Popular",
            status=TemplateStatus.PUBLISHED,
            usage_count=10,
            rating=3.0,
        )

        registry.register(t1)
        registry.register(t2)

        results = registry.get_popular(limit=10)
        assert len(results) == 2
        assert results[0].name == "Popular"

    def test_get_statistics(self):
        """Test registry statistics"""
        registry = TemplateRegistry()

        t1 = WorkflowTemplate(
            name="Template 1",
            status=TemplateStatus.PUBLISHED,
            usage_count=50,
            rating=4.0,
        )
        t2 = WorkflowTemplate(
            name="Template 2",
            status=TemplateStatus.DRAFT,
        )

        registry.register(t1)
        registry.register(t2)

        stats = registry.get_statistics()

        assert stats["total_templates"] == 2
        assert stats["published_templates"] == 1
        assert stats["draft_templates"] == 1
        assert stats["total_usage"] == 50

    def test_unregister_template(self):
        """Test template unregistration"""
        registry = TemplateRegistry()
        template = WorkflowTemplate(name="Test")

        registry.register(template)
        assert registry.get(template.id) is not None

        registry.unregister(template.id)
        assert registry.get(template.id) is None


class TestTemplateParameterSubstitution:
    """Test parameter substitution in templates"""

    def test_string_substitution(self):
        """Test string parameter substitution"""
        template = WorkflowTemplate(
            name="Test",
            parameters=[
                TemplateParameter(name="name", type="string", required=True),
            ],
            nodes=[
                TemplateNode(
                    id="node1",
                    type="transform",
                    config={"message": "Hello ${name}"},
                ),
            ],
        )

        workflow = template.instantiate({"name": "World"})
        assert workflow["nodes"][0]["config"]["message"] == "Hello World"

    def test_number_substitution(self):
        """Test number parameter substitution"""
        template = WorkflowTemplate(
            name="Test",
            parameters=[
                TemplateParameter(name="count", type="number", required=True),
            ],
            nodes=[
                TemplateNode(
                    id="node1",
                    type="transform",
                    config={"batch_size": "${count}"},
                ),
            ],
        )

        workflow = template.instantiate({"count": 100})
        assert workflow["nodes"][0]["config"]["batch_size"] == 100

    def test_object_substitution(self):
        """Test object parameter substitution"""
        template = WorkflowTemplate(
            name="Test",
            parameters=[
                TemplateParameter(name="config", type="object", required=True),
            ],
            nodes=[
                TemplateNode(
                    id="node1",
                    type="transform",
                    config={"settings": "${config}"},
                ),
            ],
        )

        config = {"key": "value", "nested": {"inner": "data"}}
        workflow = template.instantiate({"config": config})
        assert workflow["nodes"][0]["config"]["settings"] == config


class TestTemplateEdges:
    """Test template edge handling"""

    def test_edge_with_condition(self):
        """Test edge with condition"""
        edge = TemplateEdge(
            source="node1",
            target="node2",
            condition="status == 'success'",
            label="Success Path",
        )

        assert edge.source == "node1"
        assert edge.target == "node2"
        assert edge.condition == "status == 'success'"

    def test_edge_serialization(self):
        """Test edge serialization"""
        edge = TemplateEdge(
            source="node1",
            target="node2",
            condition="approved",
        )

        data = edge.to_dict()
        assert data["source"] == "node1"
        assert data["target"] == "node2"
        assert data["condition"] == "approved"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
