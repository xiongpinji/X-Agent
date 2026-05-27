"""
代码执行API端点 - 提供Python和Node.js代码执行接口
"""

from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException

from backend.app.core.execution import ExecutionManager
from backend.app.dependencies import get_current_principal, enforce_scope
from backend.app.core.security import Principal

router = APIRouter(prefix="/api/v1/execution", tags=["execution"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

# 全局执行管理器
_execution_manager = ExecutionManager(timeout=30)


@router.post("/python")
async def execute_python(
    request: dict,
    principal: PrincipalDependency,
) -> dict:
    """
    执行Python代码

    Args:
        request: 执行请求，包含code、context和allowed_imports

    Returns:
        dict: 执行结果
    """
    enforce_scope(principal, "execution:python")

    code = request.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="code is required")

    try:
        result = await _execution_manager.execute_python(
            code,
            context=request.get("context"),
            allowed_imports=request.get("allowed_imports"),
        )
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/nodejs")
async def execute_nodejs(
    request: dict,
    principal: PrincipalDependency,
) -> dict:
    """
    执行Node.js代码

    Args:
        request: 执行请求，包含code和modules

    Returns:
        dict: 执行结果
    """
    enforce_scope(principal, "execution:nodejs")

    code = request.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="code is required")

    try:
        result = await _execution_manager.execute_nodejs(
            code,
            modules=request.get("modules"),
        )
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{execution_id}")
async def get_execution_result(
    execution_id: str,
    principal: PrincipalDependency,
) -> dict:
    """
    获取执行结果

    Args:
        execution_id: 执行ID

    Returns:
        dict: 执行结果
    """
    enforce_scope(principal, "execution:read")

    result = _execution_manager.get_execution_history(execution_id)
    if not result:
        raise HTTPException(status_code=404, detail="Execution not found")

    return result


@router.get("")
async def list_executions(
    limit: int = 100,
    principal: PrincipalDependency = None,
) -> dict:
    """
    列出执行历史

    Args:
        limit: 返回的最大记录数

    Returns:
        dict: 执行历史列表
    """
    enforce_scope(principal, "execution:read")

    executions = _execution_manager.list_executions(limit=limit)
    return {
        "total": len(executions),
        "executions": executions,
    }


@router.post("/batch")
async def batch_execute(
    request: dict,
    principal: PrincipalDependency,
) -> dict:
    """
    批量执行代码

    Args:
        request: 批量执行请求

    Returns:
        dict: 执行结果列表
    """
    enforce_scope(principal, "execution:python")

    tasks = request.get("tasks", [])
    if not tasks:
        raise HTTPException(status_code=400, detail="tasks is required")

    results = []
    for task in tasks:
        try:
            language = task.get("language", "python")
            code = task.get("code")

            if not code:
                results.append({
                    "task_id": task.get("id"),
                    "error": "code is required",
                })
                continue

            result = await _execution_manager.execute(
                code,
                language=language,
                context=task.get("context"),
                allowed_imports=task.get("allowed_imports"),
            )

            results.append({
                "task_id": task.get("id"),
                "result": result,
            })

        except Exception as e:
            results.append({
                "task_id": task.get("id"),
                "error": str(e),
            })

    return {
        "total": len(tasks),
        "completed": len([r for r in results if "result" in r]),
        "failed": len([r for r in results if "error" in r]),
        "results": results,
    }


@router.delete("/history")
async def clear_execution_history(
    principal: PrincipalDependency,
) -> dict:
    """
    清空执行历史

    Returns:
        dict: 清空结果
    """
    enforce_scope(principal, "execution:manage")

    _execution_manager.clear_history()
    return {
        "success": True,
        "message": "Execution history cleared",
    }
