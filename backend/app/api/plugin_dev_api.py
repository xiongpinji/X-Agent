"""Plugin Development Tools API - Scaffolding, testing, packaging, publishing"""

from __future__ import annotations

from typing import Annotated, Optional
from pathlib import Path

from fastapi import APIRouter, Depends, Query, HTTPException, File, UploadFile
from pydantic import BaseModel, Field

from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal
from backend.app.api.errors import api_error
from backend.app.core.plugin_dev_tools import (
    PluginScaffold,
    PluginPackager,
    PluginTester,
    PluginPublisher,
    PluginDocGenerator,
)

router = APIRouter(prefix="/api/v1/plugin-dev", tags=["plugin-dev"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


# ==================== Request/Response Models ====================

class ScaffoldRequest(BaseModel):
    """Request to generate plugin scaffold"""
    plugin_name: str = Field(..., description="Plugin name")
    author: str = Field(..., description="Author name")
    description: str = Field(..., description="Plugin description")
    category: str = Field(default="development", description="Plugin category")


class ScaffoldResponse(BaseModel):
    """Scaffold generation response"""
    plugin_name: str
    output_dir: str
    files_created: list[str]
    message: str


class TestResultResponse(BaseModel):
    """Test execution result"""
    success: bool
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    return_code: Optional[int] = None
    error: Optional[str] = None


class QualityCheckResponse(BaseModel):
    """Code quality check result"""
    quality_score: int
    issues: list[str]
    ready_for_publishing: bool


class PackageInfoResponse(BaseModel):
    """Package information"""
    filename: str
    size: int
    hash: str
    created_at: str


class PublishPrepareResponse(BaseModel):
    """Publish preparation response"""
    manifest: dict
    package: PackageInfoResponse
    quality: QualityCheckResponse
    ready: bool


class PublishRequestResponse(BaseModel):
    """Publish request response"""
    manifest: dict
    category: str
    package: PackageInfoResponse
    package_path: str


# ==================== Scaffolding ====================

@router.post("/scaffold", response_model=ScaffoldResponse)
async def generate_scaffold(
    request: ScaffoldRequest,
    principal: PrincipalDependency,
) -> ScaffoldResponse:
    """Generate plugin project scaffold"""
    enforce_scope(principal, "plugin:develop")

    try:
        output_dir = PluginScaffold.generate(
            plugin_name=request.plugin_name,
            author=request.author,
            description=request.description,
            category=request.category,
        )

        # List created files
        files_created = [
            str(f.relative_to(output_dir))
            for f in output_dir.rglob("*")
            if f.is_file()
        ]

        return ScaffoldResponse(
            plugin_name=request.plugin_name,
            output_dir=str(output_dir),
            files_created=files_created,
            message=f"Plugin scaffold generated successfully at {output_dir}",
        )
    except Exception as e:
        raise api_error(400, "SCAFFOLD_GENERATION_FAILED", str(e))


# ==================== Testing ====================

@router.post("/test", response_model=TestResultResponse)
async def run_plugin_tests(
    plugin_dir: str = Query(..., description="Plugin directory path"),
    *,
    principal: PrincipalDependency,
) -> TestResultResponse:
    """Run plugin tests"""
    enforce_scope(principal, "plugin:develop")

    try:
        plugin_path = Path(plugin_dir)
        if not plugin_path.exists():
            raise api_error(404, "PLUGIN_DIR_NOT_FOUND", "Plugin directory not found")

        result = PluginTester.run_tests(plugin_path)
        return TestResultResponse(**result)
    except Exception as e:
        raise api_error(400, "TEST_EXECUTION_FAILED", str(e))


@router.post("/quality-check", response_model=QualityCheckResponse)
async def check_code_quality(
    plugin_dir: str = Query(..., description="Plugin directory path"),
    *,
    principal: PrincipalDependency,
) -> QualityCheckResponse:
    """Check plugin code quality"""
    enforce_scope(principal, "plugin:develop")

    try:
        plugin_path = Path(plugin_dir)
        if not plugin_path.exists():
            raise api_error(404, "PLUGIN_DIR_NOT_FOUND", "Plugin directory not found")

        quality = PluginTester.check_code_quality(plugin_path)
        return QualityCheckResponse(
            quality_score=quality["quality_score"],
            issues=quality["issues"],
            ready_for_publishing=quality["quality_score"] >= 80,
        )
    except Exception as e:
        raise api_error(400, "QUALITY_CHECK_FAILED", str(e))


# ==================== Packaging ====================

@router.post("/build", response_model=PackageInfoResponse)
async def build_plugin(
    plugin_dir: str = Query(..., description="Plugin directory path"),
    *,
    principal: PrincipalDependency,
) -> PackageInfoResponse:
    """Build plugin package"""
    enforce_scope(principal, "plugin:develop")

    try:
        plugin_path = Path(plugin_dir)
        if not plugin_path.exists():
            raise api_error(404, "PLUGIN_DIR_NOT_FOUND", "Plugin directory not found")

        package_path = PluginPackager.build(plugin_path)
        package_info = PluginPackager.get_package_info(package_path)

        return PackageInfoResponse(**package_info)
    except Exception as e:
        raise api_error(400, "BUILD_FAILED", str(e))


@router.get("/package-info", response_model=PackageInfoResponse)
async def get_package_info(
    package_path: str = Query(..., description="Package file path"),
    *,
    principal: PrincipalDependency,
) -> PackageInfoResponse:
    """Get package information"""
    enforce_scope(principal, "plugin:develop")

    try:
        path = Path(package_path)
        if not path.exists():
            raise api_error(404, "PACKAGE_NOT_FOUND", "Package file not found")

        info = PluginPackager.get_package_info(path)
        return PackageInfoResponse(**info)
    except Exception as e:
        raise api_error(400, "GET_PACKAGE_INFO_FAILED", str(e))


# ==================== Publishing ====================

@router.post("/prepare-publish", response_model=PublishPrepareResponse)
async def prepare_for_publishing(
    plugin_dir: str = Query(..., description="Plugin directory path"),
    *,
    principal: PrincipalDependency,
) -> PublishPrepareResponse:
    """Prepare plugin for publishing"""
    enforce_scope(principal, "plugin:publish")

    try:
        plugin_path = Path(plugin_dir)
        if not plugin_path.exists():
            raise api_error(404, "PLUGIN_DIR_NOT_FOUND", "Plugin directory not found")

        prep = PluginPublisher.prepare_for_publishing(plugin_path)

        return PublishPrepareResponse(
            manifest=prep["manifest"],
            package=PackageInfoResponse(**prep["package"]),
            quality=QualityCheckResponse(
                quality_score=prep["quality"]["quality_score"],
                issues=prep["quality"]["issues"],
                ready_for_publishing=prep["quality"]["quality_score"] >= 80,
            ),
            ready=prep["ready"],
        )
    except Exception as e:
        raise api_error(400, "PREPARE_PUBLISH_FAILED", str(e))


@router.post("/create-publish-request", response_model=PublishRequestResponse)
async def create_publish_request(
    plugin_dir: str = Query(..., description="Plugin directory path"),
    category: str = Query(..., description="Plugin category"),
    *,
    principal: PrincipalDependency,
) -> PublishRequestResponse:
    """Create plugin publish request"""
    enforce_scope(principal, "plugin:publish")

    try:
        plugin_path = Path(plugin_dir)
        if not plugin_path.exists():
            raise api_error(404, "PLUGIN_DIR_NOT_FOUND", "Plugin directory not found")

        req = PluginPublisher.create_publish_request(plugin_path, category)

        return PublishRequestResponse(
            manifest=req["manifest"],
            category=req["category"],
            package=PackageInfoResponse(**req["package"]),
            package_path=req["package_path"],
        )
    except Exception as e:
        raise api_error(400, "CREATE_PUBLISH_REQUEST_FAILED", str(e))


# ==================== Documentation ====================

@router.get("/api-docs")
async def generate_api_docs(
    plugin_dir: str = Query(..., description="Plugin directory path"),
    *,
    principal: PrincipalDependency,
) -> dict:
    """Generate API documentation"""
    enforce_scope(principal, "plugin:develop")

    try:
        plugin_path = Path(plugin_dir)
        if not plugin_path.exists():
            raise api_error(404, "PLUGIN_DIR_NOT_FOUND", "Plugin directory not found")

        docs = PluginDocGenerator.generate_api_docs(plugin_path)
        return {"documentation": docs}
    except Exception as e:
        raise api_error(400, "GENERATE_DOCS_FAILED", str(e))


@router.get("/user-guide")
async def generate_user_guide(
    plugin_dir: str = Query(..., description="Plugin directory path"),
    *,
    principal: PrincipalDependency,
) -> dict:
    """Generate user guide"""
    enforce_scope(principal, "plugin:develop")

    try:
        plugin_path = Path(plugin_dir)
        if not plugin_path.exists():
            raise api_error(404, "PLUGIN_DIR_NOT_FOUND", "Plugin directory not found")

        guide = PluginDocGenerator.generate_user_guide(plugin_path)
        return {"guide": guide}
    except Exception as e:
        raise api_error(400, "GENERATE_GUIDE_FAILED", str(e))
