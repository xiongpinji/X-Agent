"""P2-F Part 2: HTTP API for the model fine-tuning pipeline.

Exposes training-data statistics, job submission/listing/status, deployment and
rollback.  Collection is opt-in; see
:mod:`backend.app.core.model_finetuning`.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.app.core.model_finetuning import (
    DatasetFormat,
    FineTuneConfig,
    JobBackend,
    get_finetuning_pipeline,
)
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal

router = APIRouter(prefix="/api/v1/finetuning", tags=["finetuning"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]


@router.get("/data/stats")
async def training_data_stats(principal: PrincipalDependency = None) -> dict[str, Any]:
    """P2-F: Training data collection statistics."""
    enforce_scope(principal, "agent:run")
    pipeline = get_finetuning_pipeline()
    stats = pipeline.collector.stats()
    stats["deployment"] = pipeline.deployment_status()
    return stats


@router.post("/data/collect")
async def toggle_collection(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """P2-F: Enable/disable opt-in training data collection."""
    enforce_scope(principal, "agent:run")
    body = await request.json()
    enabled = bool(body.get("enabled", False))
    pipeline = get_finetuning_pipeline()
    if enabled:
        pipeline.collector.enable()
        pipeline.config.collection_enabled = True
    else:
        pipeline.collector.disable()
        pipeline.config.collection_enabled = False
    return {"collection_enabled": pipeline.collector.enabled, "stats": pipeline.collector.stats()}


@router.post("/jobs")
async def submit_job(
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """P2-F: Submit a fine-tuning job (with cost estimation)."""
    enforce_scope(principal, "agent:run")
    body = await request.json()
    pipeline = get_finetuning_pipeline()

    config = FineTuneConfig(
        base_model=body.get("base_model", pipeline.config.base_model),
        epochs=int(body.get("epochs", pipeline.config.epochs)),
        learning_rate=float(body.get("learning_rate", pipeline.config.learning_rate)),
        batch_size=int(body.get("batch_size", pipeline.config.batch_size)),
        format=DatasetFormat(body.get("format", pipeline.config.format)),
        backend=JobBackend(body.get("backend", pipeline.config.backend)),
        lora_rank=int(body.get("lora_rank", pipeline.config.lora_rank)),
        lora_alpha=int(body.get("lora_alpha", pipeline.config.lora_alpha)),
        suffix=body.get("suffix", pipeline.config.suffix),
    )

    # Dry-run: return only the cost estimate without submitting.
    if bool(body.get("estimate_only", False)):
        return {"estimate": pipeline.estimate_cost(), "config": config.to_dict()}

    job = await pipeline.submit_finetune_job(config)
    return job.to_dict()


@router.get("/jobs")
async def list_jobs(principal: PrincipalDependency = None) -> dict[str, Any]:
    """P2-F: List all fine-tuning jobs."""
    enforce_scope(principal, "agent:run")
    pipeline = get_finetuning_pipeline()
    jobs = pipeline.list_jobs()
    return {"jobs": jobs, "total": len(jobs)}


@router.get("/jobs/{job_id}")
async def job_status(job_id: str, principal: PrincipalDependency = None) -> dict[str, Any]:
    """P2-F: Get the status of a specific fine-tuning job."""
    enforce_scope(principal, "agent:run")
    pipeline = get_finetuning_pipeline()
    job = pipeline.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return job


@router.post("/jobs/{job_id}/evaluate")
async def evaluate_job(
    job_id: str,
    request: Request,
    principal: PrincipalDependency = None,
) -> dict[str, Any]:
    """P2-F: Evaluate a fine-tuned model vs its base model."""
    enforce_scope(principal, "agent:run")
    body = await request.json() if request.headers.get("content-length") not in (None, "0") else {}
    pipeline = get_finetuning_pipeline()
    if pipeline.get_job(job_id) is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return await pipeline.evaluate_model(job_id, body.get("metrics"))


@router.post("/deploy/{model_id:path}")
async def deploy_model(model_id: str, principal: PrincipalDependency = None) -> dict[str, Any]:
    """P2-F: Deploy a fine-tuned model to the router."""
    enforce_scope(principal, "agent:run")
    pipeline = get_finetuning_pipeline()
    return pipeline.deploy_model(model_id)


@router.post("/rollback")
async def rollback(principal: PrincipalDependency = None) -> dict[str, Any]:
    """P2-F: Rollback to the previously deployed model."""
    enforce_scope(principal, "agent:run")
    pipeline = get_finetuning_pipeline()
    result = pipeline.rollback()
    if not result.get("rolled_back"):
        raise HTTPException(status_code=409, detail=result.get("error", "Rollback failed"))
    return result
