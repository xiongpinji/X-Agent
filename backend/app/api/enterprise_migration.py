"""
企业级迁移管理API路由
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from backend.app.api.rbac_enforcement import require_admin
from backend.app.core.enterprise_migration import (
    ConfigurationTransformer,
    DataExporter,
    DataImporter,
    HermesMigrator,
    MigrationType,
    OpenClawMigrator,
    SourceSystem,
    TargetSystem,
)

logger = logging.getLogger(__name__)

# SECURITY P1-03: enterprise migration endpoints require admin role.
router = APIRouter(
    prefix="/api/v1/enterprise/migration",
    tags=["enterprise-migration"],
    dependencies=[require_admin],
)

# 初始化管理器
openclaw_migrator = OpenClawMigrator()
hermes_migrator = HermesMigrator()
data_exporter = DataExporter()
data_importer = DataImporter()


class MigrationPlanRequest(BaseModel):
    """迁移计划请求"""
    source_system_type: str
    target_system_type: str = "xagent_v2"
    migration_type: str = "full"


class SourceSystemRequest(BaseModel):
    """源系统请求"""
    system_type: str
    system_name: str
    host: str
    port: int
    database: str
    username: str
    password: str


class TargetSystemRequest(BaseModel):
    """目标系统请求"""
    system_type: str = "xagent_v2"
    system_name: str
    host: str
    port: int
    database: str
    username: str
    password: str


class DataExportRequest(BaseModel):
    """数据导出请求"""
    format: str  # "json", "csv", "parquet"
    data: list[dict[str, Any]]


class DataImportRequest(BaseModel):
    """数据导入请求"""
    format: str  # "json", "csv"
    data: str


class ConfigTransformRequest(BaseModel):
    """配置转换请求"""
    source_format: str  # "xagent_v1", "openclaw", "hermes"
    target_format: str = "xagent_v2"
    config: dict[str, Any]


@router.post("/plan", response_model=dict[str, Any])
async def create_migration_plan(request: MigrationPlanRequest) -> dict[str, Any]:
    """创建迁移计划"""
    try:
        source = SourceSystem(
            system_type=request.source_system_type,
            system_name=f"Source {request.source_system_type}",
            connection_string="",
            host="localhost",
            port=5432,
            database="source_db",
        )
        target = TargetSystem(
            system_type=request.target_system_type,
            system_name="Target X-Agent",
            connection_string="",
            host="localhost",
            port=5432,
            database="xagent",
        )

        plan = openclaw_migrator.create_migration_plan(
            source,
            target,
            MigrationType(request.migration_type),
        )

        return {
            "status": "success",
            "plan_id": plan.plan_id,
            "message": "Migration plan created successfully",
        }
    except Exception as e:
        logger.error(f"Failed to create migration plan: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{plan_id}/validate", response_model=dict[str, Any])
async def validate_migration_plan(plan_id: str) -> dict[str, Any]:
    """验证迁移计划"""
    try:
        validation_results = openclaw_migrator.validate_source_data(plan_id)
        return {
            "status": "success",
            "validation": validation_results,
        }
    except Exception as e:
        logger.error(f"Failed to validate migration plan: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{plan_id}/start", response_model=dict[str, Any])
async def start_migration(plan_id: str, dry_run: bool = False) -> dict[str, Any]:
    """启动迁移"""
    try:
        job = openclaw_migrator.start_migration(plan_id, dry_run)

        return {
            "status": "success",
            "job_id": job.job_id,
            "message": "Migration started successfully",
        }
    except Exception as e:
        logger.error(f"Failed to start migration: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{job_id}/status", response_model=dict[str, Any])
async def get_migration_status(job_id: str) -> dict[str, Any]:
    """获取迁移状态"""
    try:
        job = openclaw_migrator.get_migration_status(job_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

        return {
            "status": "success",
            "job": job.dict(),
        }
    except Exception as e:
        logger.error(f"Failed to get migration status: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{job_id}/pause", response_model=dict[str, Any])
async def pause_migration(job_id: str) -> dict[str, Any]:
    """暂停迁移"""
    try:
        if openclaw_migrator.pause_migration(job_id):
            return {"status": "success", "message": "Migration paused"}
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot pause migration")
    except Exception as e:
        logger.error(f"Failed to pause migration: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{job_id}/resume", response_model=dict[str, Any])
async def resume_migration(job_id: str) -> dict[str, Any]:
    """恢复迁移"""
    try:
        if openclaw_migrator.resume_migration(job_id):
            return {"status": "success", "message": "Migration resumed"}
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot resume migration")
    except Exception as e:
        logger.error(f"Failed to resume migration: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{job_id}/rollback", response_model=dict[str, Any])
async def rollback_migration(job_id: str) -> dict[str, Any]:
    """回滚迁移"""
    try:
        if openclaw_migrator.rollback_migration(job_id):
            return {"status": "success", "message": "Migration rolled back"}
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot rollback migration")
    except Exception as e:
        logger.error(f"Failed to rollback migration: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{job_id}/validate", response_model=dict[str, Any])
async def validate_migrated_data(job_id: str) -> dict[str, Any]:
    """验证迁移后的数据"""
    try:
        validation = openclaw_migrator.validate_migrated_data(job_id)
        return {
            "status": "success",
            "validation": validation.dict(),
        }
    except Exception as e:
        logger.error(f"Failed to validate migrated data: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/export", response_model=dict[str, Any])
async def export_data(request: DataExportRequest) -> dict[str, Any]:
    """导出数据"""
    try:
        if request.format == "json":
            export_id = data_exporter.export_to_json(request.data)
        elif request.format == "csv":
            export_id = data_exporter.export_to_csv(request.data)
        elif request.format == "parquet":
            export_id = data_exporter.export_to_parquet(request.data)
        else:
            raise ValueError(f"Unsupported format: {request.format}")

        return {
            "status": "success",
            "export_id": export_id,
            "message": f"Data exported to {request.format}",
        }
    except Exception as e:
        logger.error(f"Failed to export data: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/import", response_model=dict[str, Any])
async def import_data(request: DataImportRequest) -> dict[str, Any]:
    """导入数据"""
    try:
        if request.format == "json":
            import_id = data_importer.import_from_json(request.data)
        elif request.format == "csv":
            import_id = data_importer.import_from_csv(request.data)
        else:
            raise ValueError(f"Unsupported format: {request.format}")

        return {
            "status": "success",
            "import_id": import_id,
            "message": f"Data imported from {request.format}",
        }
    except Exception as e:
        logger.error(f"Failed to import data: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/config/transform", response_model=dict[str, Any])
async def transform_config(request: ConfigTransformRequest) -> dict[str, Any]:
    """转换配置"""
    try:
        if request.source_format == "xagent_v1" and request.target_format == "xagent_v2":
            transformed = ConfigurationTransformer.transform_xagent_v1_to_v2(request.config)
        elif request.source_format == "openclaw" and request.target_format == "xagent_v2":
            transformed = ConfigurationTransformer.transform_openclaw_to_xagent(request.config)
        elif request.source_format == "hermes" and request.target_format == "xagent_v2":
            transformed = ConfigurationTransformer.transform_hermes_to_xagent(request.config)
        else:
            raise ValueError(f"Unsupported transformation: {request.source_format} -> {request.target_format}")

        return {
            "status": "success",
            "config": transformed,
            "message": "Configuration transformed successfully",
        }
    except Exception as e:
        logger.error(f"Failed to transform config: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
