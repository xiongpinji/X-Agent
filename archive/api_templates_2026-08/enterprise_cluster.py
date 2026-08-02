"""
企业级集群管理API路由
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from backend.app.core.enterprise_cluster import (
    ClusterConfig,
    ClusterManager,
    ClusterType,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/enterprise/cluster", tags=["enterprise-cluster"])

# 初始化管理器
cluster_manager = ClusterManager()


class ClusterConfigRequest(BaseModel):
    """集群配置请求"""
    cluster_name: str
    cluster_type: str
    region: str
    api_endpoint: str
    environment: str = "production"


class ServiceDeploymentRequest(BaseModel):
    """服务部署请求"""
    service_name: str
    cluster_id: str
    replicas: int = 3
    image: str
    port: int
    target_port: int


@router.post("/register", response_model=dict[str, Any])
async def register_cluster(request: ClusterConfigRequest) -> dict[str, Any]:
    """注册集群"""
    try:
        config = ClusterConfig(
            cluster_name=request.cluster_name,
            cluster_type=ClusterType(request.cluster_type),
            region=request.region,
            api_endpoint=request.api_endpoint,
            environment=request.environment,
        )
        cluster_manager.register_cluster(config)

        return {
            "status": "success",
            "cluster_id": config.cluster_id,
            "message": "Cluster registered successfully",
        }
    except Exception as e:
        logger.error(f"Failed to register cluster: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/list", response_model=dict[str, Any])
async def list_clusters() -> dict[str, Any]:
    """列出所有集群"""
    try:
        clusters = cluster_manager.list_clusters()
        return {
            "status": "success",
            "clusters": [c.dict() for c in clusters],
        }
    except Exception as e:
        logger.error(f"Failed to list clusters: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{cluster_id}", response_model=dict[str, Any])
async def get_cluster(cluster_id: str) -> dict[str, Any]:
    """获取集群配置"""
    try:
        cluster = cluster_manager.get_cluster(cluster_id)
        if not cluster:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cluster not found")

        return {
            "status": "success",
            "cluster": cluster.dict(),
        }
    except Exception as e:
        logger.error(f"Failed to get cluster: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{cluster_id}/health", response_model=dict[str, Any])
async def get_cluster_health(cluster_id: str) -> dict[str, Any]:
    """获取集群健康状态"""
    try:
        health = cluster_manager.get_cluster_health(cluster_id)
        return {
            "status": "success",
            "health": health,
        }
    except Exception as e:
        logger.error(f"Failed to get cluster health: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{cluster_id}/nodes", response_model=dict[str, Any])
async def get_cluster_nodes(cluster_id: str) -> dict[str, Any]:
    """获取集群节点"""
    try:
        nodes = cluster_manager.get_cluster_nodes(cluster_id)
        return {
            "status": "success",
            "nodes": [n.dict() for n in nodes],
        }
    except Exception as e:
        logger.error(f"Failed to get cluster nodes: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{cluster_id}/deployments", response_model=dict[str, Any])
async def get_cluster_deployments(cluster_id: str) -> dict[str, Any]:
    """获取集群部署"""
    try:
        deployments = cluster_manager.list_deployments(cluster_id)
        return {
            "status": "success",
            "deployments": [d.dict() for d in deployments],
        }
    except Exception as e:
        logger.error(f"Failed to get cluster deployments: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{cluster_id}/deploy", response_model=dict[str, Any])
async def deploy_service(cluster_id: str, request: ServiceDeploymentRequest) -> dict[str, Any]:
    """部署服务"""
    try:
        from backend.app.core.enterprise_cluster import ServiceDeployment

        deployment = ServiceDeployment(
            service_name=request.service_name,
            cluster_id=cluster_id,
            replicas=request.replicas,
            image=request.image,
            port=request.port,
            target_port=request.target_port,
        )
        cluster_manager.deploy_service(deployment)

        return {
            "status": "success",
            "deployment_id": deployment.deployment_id,
            "message": "Service deployed successfully",
        }
    except Exception as e:
        logger.error(f"Failed to deploy service: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
