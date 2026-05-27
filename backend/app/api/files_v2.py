"""
文件操作API端点 - 提供文档、图像和文件转换接口
"""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException

from backend.app.core.file_operations import (
    DocumentProcessor,
    ImageProcessor,
    FileConverter,
)
from backend.app.dependencies import get_current_principal, enforce_scope
from backend.app.core.security import Principal

router = APIRouter(prefix="/api/v1/files", tags=["files"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]

# 全局文件处理器
_document_processor = DocumentProcessor()
_image_processor = ImageProcessor()
_file_converter = FileConverter()


@router.post("/process")
async def process_file(
    request: dict,
    principal: PrincipalDependency,
) -> dict:
    """
    处理文件

    Args:
        request: 处理请求，包含file_path、operation和参数

    Returns:
        dict: 处理结果
    """
    enforce_scope(principal, "files:read")

    file_path = request.get("file_path")
    operation = request.get("operation")

    if not file_path or not operation:
        raise HTTPException(
            status_code=400,
            detail="file_path and operation are required",
        )

    try:
        result = await _document_processor.process(
            file_path,
            operation,
            **request.get("params", {}),
        )
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/image/process")
async def process_image(
    request: dict,
    principal: PrincipalDependency,
) -> dict:
    """
    处理图像

    Args:
        request: 处理请求，包含image_path、operation和参数

    Returns:
        dict: 处理结果
    """
    enforce_scope(principal, "files:read")

    image_path = request.get("image_path")
    operation = request.get("operation")

    if not image_path or not operation:
        raise HTTPException(
            status_code=400,
            detail="image_path and operation are required",
        )

    try:
        result = await _image_processor.process(
            image_path,
            operation,
            **request.get("params", {}),
        )
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/convert")
async def convert_file(
    request: dict,
    principal: PrincipalDependency,
) -> dict:
    """
    转换文件格式

    Args:
        request: 转换请求，包含input_path、output_format和参数

    Returns:
        dict: 转换结果
    """
    enforce_scope(principal, "files:write")

    input_path = request.get("input_path")
    output_format = request.get("output_format")

    if not input_path or not output_format:
        raise HTTPException(
            status_code=400,
            detail="input_path and output_format are required",
        )

    try:
        result = await _file_converter.convert(
            input_path,
            output_format,
            **request.get("params", {}),
        )
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/image/info")
async def get_image_info(
    image_path: str,
    principal: PrincipalDependency,
) -> dict:
    """
    获取图像信息

    Args:
        image_path: 图像文件路径

    Returns:
        dict: 图像信息
    """
    enforce_scope(principal, "files:read")

    try:
        result = await _image_processor.process(image_path, "get_info")
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch-process")
async def batch_process_files(
    request: dict,
    principal: PrincipalDependency,
) -> dict:
    """
    批量处理文件

    Args:
        request: 批量处理请求

    Returns:
        dict: 处理结果列表
    """
    enforce_scope(principal, "files:read")

    files = request.get("files", [])
    operation = request.get("operation")

    if not files or not operation:
        raise HTTPException(
            status_code=400,
            detail="files and operation are required",
        )

    results = []
    for file_info in files:
        try:
            file_path = file_info.get("path")
            params = file_info.get("params", {})

            result = await _document_processor.process(
                file_path,
                operation,
                **params,
            )
            results.append({
                "file": file_path,
                "result": result,
            })

        except Exception as e:
            results.append({
                "file": file_info.get("path"),
                "error": str(e),
            })

    return {
        "total": len(files),
        "processed": len([r for r in results if "result" in r]),
        "failed": len([r for r in results if "error" in r]),
        "results": results,
    }
