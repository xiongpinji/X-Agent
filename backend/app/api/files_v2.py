"""
文件操作API端点 - 提供文档、图像和文件转换接口

SECURITY: 所有文件路径都通过 PathMapper 进行验证，防止路径遍历攻击
SECURITY: 所有错误信息都通过 SafeErrorResponse 进行处理，防止敏感信息泄露
"""

import logging
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from backend.app.core.error_handling import ErrorCategory, SafeErrorResponse
from backend.app.core.file_operations import (
    DocumentProcessor,
    FileConverter,
    ImageProcessor,
)
from backend.app.core.path_mapper import PathMapper
from backend.app.core.security import Principal
from backend.app.dependencies import enforce_scope, get_current_principal
from backend.app.settings import get_settings

router = APIRouter(prefix="/api/v1/files", tags=["files"])
PrincipalDependency = Annotated[Principal, Depends(get_current_principal)]
logger = logging.getLogger("xagent.files")

# 全局文件处理器
_document_processor = DocumentProcessor()
_image_processor = ImageProcessor()
_file_converter = FileConverter()

# 路径验证器
_settings = get_settings()
_path_mapper = PathMapper(Path(_settings.static_dir).parent / "workspace")


def _validate_and_resolve_path(file_path: str, user_id: str) -> Path:
    """验证并解析文件路径，防止路径遍历攻击。

    Args:
        file_path: 用户提供的文件路径
        user_id: 当前用户ID

    Returns:
        验证后的真实文件路径

    Raises:
        ValueError: 如果路径无效或超出允许范围
        PermissionError: 如果访问被拒绝
    """
    if not file_path:
        raise ValueError("file_path cannot be empty")

    try:
        # 使用 PathMapper 进行安全的路径解析
        resolved_path = _path_mapper.map_virtual_to_real(file_path, user_id)
        logger.debug(f"Path resolved: {file_path} -> {resolved_path}")
        return resolved_path
    except (ValueError, PermissionError) as e:
        logger.warning(f"Path validation failed for {file_path}: {e}")
        raise


@router.post("/process")
async def process_file(
    request: dict,
    principal: PrincipalDependency,
) -> dict:
    """处理文件

    SECURITY: 所有文件路径都通过 _validate_and_resolve_path 进行验证
    SECURITY: 所有错误都通过 SafeErrorResponse 进行处理

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
        # SECURITY: 验证并解析文件路径，防止路径遍历攻击
        resolved_path = _validate_and_resolve_path(file_path, principal.user_id)

        result = await _document_processor.process(
            str(resolved_path),
            operation,
            **request.get("params", {}),
        )
        return result

    except (ValueError, PermissionError) as e:
        logger.warning(f"File access denied for user {principal.user_id}: {e}")
        raise HTTPException(status_code=403, detail="Access denied to file")
    except Exception as e:
        # SECURITY: 使用 SafeErrorResponse 防止敏感信息泄露
        safe_response = SafeErrorResponse.get_safe_message(
            e,
            ErrorCategory.INTERNAL,
            "File processing failed"
        )
        SafeErrorResponse.log_error_details(e, user_id=principal.user_id)
        raise HTTPException(status_code=500, detail=safe_response)


@router.post("/image/process")
async def process_image(
    request: dict,
    principal: PrincipalDependency,
) -> dict:
    """处理图像

    SECURITY: 所有文件路径都通过 _validate_and_resolve_path 进行验证
    SECURITY: 所有错误都通过 SafeErrorResponse 进行处理

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
        # SECURITY: 验证并解析文件路径，防止路径遍历攻击
        resolved_path = _validate_and_resolve_path(image_path, principal.user_id)

        result = await _image_processor.process(
            str(resolved_path),
            operation,
            **request.get("params", {}),
        )
        return result

    except (ValueError, PermissionError) as e:
        logger.warning(f"Image access denied for user {principal.user_id}: {e}")
        raise HTTPException(status_code=403, detail="Access denied to image")
    except Exception as e:
        # SECURITY: 使用 SafeErrorResponse 防止敏感信息泄露
        safe_response = SafeErrorResponse.get_safe_message(
            e,
            ErrorCategory.INTERNAL,
            "Image processing failed"
        )
        SafeErrorResponse.log_error_details(e, user_id=principal.user_id)
        raise HTTPException(status_code=500, detail=safe_response)


@router.post("/convert")
async def convert_file(
    request: dict,
    principal: PrincipalDependency,
) -> dict:
    """转换文件格式

    SECURITY: 所有文件路径都通过 _validate_and_resolve_path 进行验证
    SECURITY: 所有错误都通过 SafeErrorResponse 进行处理

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
        # SECURITY: 验证并解析文件路径，防止路径遍历攻击
        resolved_input = _validate_and_resolve_path(input_path, principal.user_id)

        result = await _file_converter.convert(
            str(resolved_input),
            output_format,
            **request.get("params", {}),
        )
        return result

    except (ValueError, PermissionError) as e:
        logger.warning(f"File conversion access denied for user {principal.user_id}: {e}")
        raise HTTPException(status_code=403, detail="Access denied to file")
    except Exception as e:
        # SECURITY: 使用 SafeErrorResponse 防止敏感信息泄露
        safe_response = SafeErrorResponse.get_safe_message(
            e,
            ErrorCategory.INTERNAL,
            "File conversion failed"
        )
        SafeErrorResponse.log_error_details(e, user_id=principal.user_id)
        raise HTTPException(status_code=500, detail=safe_response)


@router.get("/image/info")
async def get_image_info(
    image_path: str,
    principal: PrincipalDependency,
) -> dict:
    """获取图像信息

    SECURITY: 所有文件路径都通过 _validate_and_resolve_path 进行验证
    SECURITY: 所有错误都通过 SafeErrorResponse 进行处理

    Args:
        image_path: 图像文件路径

    Returns:
        dict: 图像信息
    """
    enforce_scope(principal, "files:read")

    try:
        # SECURITY: 验证并解析文件路径，防止路径遍历攻击
        resolved_path = _validate_and_resolve_path(image_path, principal.user_id)

        result = await _image_processor.process(str(resolved_path), "get_info")
        return result

    except (ValueError, PermissionError) as e:
        logger.warning(f"Image info access denied for user {principal.user_id}: {e}")
        raise HTTPException(status_code=403, detail="Access denied to image")
    except Exception as e:
        # SECURITY: 使用 SafeErrorResponse 防止敏感信息泄露
        safe_response = SafeErrorResponse.get_safe_message(
            e,
            ErrorCategory.INTERNAL,
            "Image info retrieval failed"
        )
        SafeErrorResponse.log_error_details(e, user_id=principal.user_id)
        raise HTTPException(status_code=500, detail=safe_response)


@router.post("/batch-process")
async def batch_process_files(
    request: dict,
    principal: PrincipalDependency,
) -> dict:
    """批量处理文件

    SECURITY: 所有文件路径都通过 _validate_and_resolve_path 进行验证
    SECURITY: 所有错误都通过 SafeErrorResponse 进行处理

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

            # SECURITY: 验证并解析文件路径，防止路径遍历攻击
            resolved_path = _validate_and_resolve_path(file_path, principal.user_id)

            result = await _document_processor.process(
                str(resolved_path),
                operation,
                **params,
            )
            results.append({
                "file": file_path,
                "result": result,
            })

        except (ValueError, PermissionError) as e:
            logger.warning(f"Batch processing access denied for {file_info.get('path')}: {e}")
            results.append({
                "file": file_info.get("path"),
                "error": "Access denied",
            })
        except Exception as e:
            # SECURITY: 使用 SafeErrorResponse 防止敏感信息泄露
            safe_response = SafeErrorResponse.get_safe_message(
                e,
                ErrorCategory.INTERNAL,
                "Processing failed"
            )
            SafeErrorResponse.log_error_details(e, user_id=principal.user_id)
            results.append({
                "file": file_info.get("path"),
                "error": safe_response,
            })

    return {
        "total": len(files),
        "processed": len([r for r in results if "result" in r]),
        "failed": len([r for r in results if "error" in r]),
        "results": results,
    }
