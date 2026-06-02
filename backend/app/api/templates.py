"""Template Management API

Endpoints for:
- Template CRUD operations
- Template search and filtering
- Template instantiation
- Template versioning
- Template marketplace
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status

from backend.app.core.security import Principal
from backend.app.core.workflows.template_system import (
    WorkflowTemplate,
    TemplateRegistry,
    TemplateCategory,
    TemplateStatus,
    TemplateParameter,
    TemplateNode,
    TemplateEdge,
    get_template_registry,
)
from backend.app.dependencies import get_current_principal

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


# Template CRUD Operations

@router.post("")
async def create_template(
    payload: dict[str, Any],
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """Create a new template"""
    registry = get_template_registry()

    # Parse template data
    template = WorkflowTemplate(
        name=payload.get("name", ""),
        description=payload.get("description", ""),
        category=TemplateCategory(payload.get("category", "custom")),
        version=payload.get("version", "1.0.0"),
        status=TemplateStatus.DRAFT,
        author=principal.user_id,
        author_id=principal.user_id,
    )

    # Parse parameters
    if "parameters" in payload:
        for param_data in payload["parameters"]:
            template.parameters.append(TemplateParameter(
                name=param_data.get("name", ""),
                type=param_data.get("type", "string"),
                description=param_data.get("description", ""),
                default=param_data.get("default"),
                required=param_data.get("required", False),
                enum_values=param_data.get("enum_values", []),
                validation_pattern=param_data.get("validation_pattern"),
                min_value=param_data.get("min_value"),
                max_value=param_data.get("max_value"),
                min_length=param_data.get("min_length"),
                max_length=param_data.get("max_length"),
                placeholder=param_data.get("placeholder", ""),
                help_text=param_data.get("help_text", ""),
            ))

    # Parse nodes
    if "nodes" in payload:
        for node_data in payload["nodes"]:
            template.nodes.append(TemplateNode(
                id=node_data.get("id", ""),
                type=node_data.get("type", ""),
                name=node_data.get("name", ""),
                description=node_data.get("description", ""),
                config=node_data.get("config", {}),
                position=node_data.get("position", {"x": 0, "y": 0}),
            ))

    # Parse edges
    if "edges" in payload:
        for edge_data in payload["edges"]:
            template.edges.append(TemplateEdge(
                source=edge_data.get("source", ""),
                target=edge_data.get("target", ""),
                condition=edge_data.get("condition"),
                label=edge_data.get("label", ""),
            ))

    # Additional metadata
    template.tags = payload.get("tags", [])
    template.icon = payload.get("icon", "")
    template.thumbnail = payload.get("thumbnail", "")
    template.documentation_url = payload.get("documentation_url", "")
    template.example_inputs = payload.get("example_inputs", {})

    # Register template
    registry.register(template)

    return {
        "id": template.id,
        "name": template.name,
        "status": template.status.value,
        "created_at": template.created_at.isoformat(),
        "message": "Template created successfully",
    }


@router.get("")
async def list_templates(
    principal: PrincipalDependency,
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List templates with filtering"""
    registry = get_template_registry()

    # Get templates
    templates = registry.list_all()

    # Filter by category
    if category:
        try:
            cat = TemplateCategory(category)
            templates = [t for t in templates if t.category == cat]
        except ValueError:
            pass

    # Filter by status
    if status:
        try:
            st = TemplateStatus(status)
            templates = [t for t in templates if t.status == st]
        except ValueError:
            pass

    # Filter by tag
    if tag:
        templates = [t for t in templates if tag in t.tags]

    # Apply pagination
    total = len(templates)
    templates = templates[offset:offset + limit]

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "templates": [t.to_dict() for t in templates],
    }


@router.get("/{template_id}")
async def get_template(
    template_id: str,
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """Get template by ID"""
    registry = get_template_registry()
    template = registry.get(template_id)

    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    return template.to_dict()


@router.put("/{template_id}")
async def update_template(
    template_id: str,
    payload: dict[str, Any],
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """Update template"""
    registry = get_template_registry()
    template = registry.get(template_id)

    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    # Update fields
    if "name" in payload:
        template.name = payload["name"]
    if "description" in payload:
        template.description = payload["description"]
    if "tags" in payload:
        template.tags = payload["tags"]
    if "status" in payload:
        try:
            template.status = TemplateStatus(payload["status"])
        except ValueError:
            pass

    template.updated_at = datetime.now(UTC)

    return {
        "id": template.id,
        "name": template.name,
        "status": template.status.value,
        "updated_at": template.updated_at.isoformat(),
        "message": "Template updated successfully",
    }


@router.delete("/{template_id}")
async def delete_template(
    template_id: str,
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """Delete template"""
    registry = get_template_registry()

    if not registry.unregister(template_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    return {"message": "Template deleted successfully"}


# Template Search and Discovery

@router.get("/search/query")
async def search_templates(
    q: str = Query(..., min_length=1),
    principal: PrincipalDependency = None,
    category: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """Search templates"""
    registry = get_template_registry()

    # Parse category
    cat = None
    if category:
        try:
            cat = TemplateCategory(category)
        except ValueError:
            pass

    # Search
    results = registry.search(q, cat)

    # Apply limit
    results = results[:limit]

    return {
        "query": q,
        "total": len(results),
        "templates": [t.to_dict() for t in results],
    }


@router.get("/discover/popular")
async def get_popular_templates(
    principal: PrincipalDependency,
    category: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
) -> dict[str, Any]:
    """Get popular templates"""
    registry = get_template_registry()

    # Parse category
    cat = None
    if category:
        try:
            cat = TemplateCategory(category)
        except ValueError:
            pass

    # Get popular
    templates = registry.get_popular(limit, cat)

    return {
        "category": category,
        "templates": [t.to_dict() for t in templates],
    }


@router.get("/discover/recent")
async def get_recent_templates(
    principal: PrincipalDependency,
    category: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
) -> dict[str, Any]:
    """Get recently updated templates"""
    registry = get_template_registry()

    # Parse category
    cat = None
    if category:
        try:
            cat = TemplateCategory(category)
        except ValueError:
            pass

    # Get recent
    templates = registry.get_recent(limit, cat)

    return {
        "category": category,
        "templates": [t.to_dict() for t in templates],
    }


@router.get("/discover/top-rated")
async def get_top_rated_templates(
    principal: PrincipalDependency,
    category: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
) -> dict[str, Any]:
    """Get top rated templates"""
    registry = get_template_registry()

    # Parse category
    cat = None
    if category:
        try:
            cat = TemplateCategory(category)
        except ValueError:
            pass

    # Get top rated
    templates = registry.get_top_rated(limit, cat)

    return {
        "category": category,
        "templates": [t.to_dict() for t in templates],
    }


# Template Instantiation

@router.post("/{template_id}/instantiate")
async def instantiate_template(
    template_id: str,
    payload: dict[str, Any],
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """Instantiate template with parameters"""
    registry = get_template_registry()
    template = registry.get(template_id)

    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    # Get parameters
    parameters = payload.get("parameters", {})

    # Validate parameters
    valid, errors = template.validate_parameters(parameters)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"errors": errors},
        )

    # Instantiate
    try:
        workflow = template.instantiate(parameters)
        template.usage_count += 1
        return {
            "workflow_id": workflow["id"],
            "template_id": template_id,
            "workflow": workflow,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


# Template Preview

@router.post("/{template_id}/preview")
async def preview_template(
    template_id: str,
    payload: dict[str, Any],
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """Preview template with parameters"""
    registry = get_template_registry()
    template = registry.get(template_id)

    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    # Get parameters
    parameters = payload.get("parameters", {})

    # Validate parameters
    valid, errors = template.validate_parameters(parameters)

    return {
        "template_id": template_id,
        "valid": valid,
        "errors": errors,
        "preview": template.to_dict() if valid else None,
    }


# Template Statistics

@router.get("/stats/overview")
async def get_template_statistics(
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """Get template registry statistics"""
    registry = get_template_registry()
    stats = registry.get_statistics()

    return {
        "statistics": stats,
    }


# Template Categories

@router.get("/categories/list")
async def list_categories(
    principal: PrincipalDependency,
) -> dict[str, Any]:
    """List all template categories"""
    categories = [
        {
            "id": cat.value,
            "name": cat.value.replace("_", " ").title(),
            "description": f"Templates for {cat.value.replace('_', ' ')}",
        }
        for cat in TemplateCategory
    ]

    return {
        "categories": categories,
    }
