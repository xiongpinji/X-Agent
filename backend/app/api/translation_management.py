"""
翻译管理API端点
"""

import json
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from backend.app.core.i18n import Language, TranslationManager
from backend.app.core.translation_quality import TranslationQualityChecker, check_all_translations

router = APIRouter(prefix="/api/translations", tags=["translations"])


class TranslationUpdateRequest(BaseModel):
    language: str
    key: str
    value: str


class BulkTranslationUpdateRequest(BaseModel):
    language: str
    translations: dict[str, Any]


class TranslationExportRequest(BaseModel):
    language: str


@router.post("/update")
async def update_translation(request: TranslationUpdateRequest):
    """更新单个翻译"""
    try:
        lang = Language(request.language)
        manager = TranslationManager()
        manager.add_translation(lang, request.key, request.value)
        manager.save_translations(lang)
        return {
            "status": "success",
            "language": request.language,
            "key": request.key,
            "value": request.value,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid language: {e!s}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bulk-update")
async def bulk_update_translations(request: BulkTranslationUpdateRequest):
    """批量更新翻译"""
    try:
        lang = Language(request.language)
        manager = TranslationManager()

        def update_nested(obj: dict, prefix: str = ""):
            for key, value in obj.items():
                full_key = f"{prefix}.{key}" if prefix else key
                if isinstance(value, dict):
                    update_nested(value, full_key)
                else:
                    manager.add_translation(lang, full_key, str(value))

        update_nested(request.translations)
        manager.save_translations(lang)

        return {
            "status": "success",
            "language": request.language,
            "updated_count": len(request.translations),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid language: {e!s}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload")
async def upload_translation(language: str, file: UploadFile = File(...)):
    """上传翻译文件"""
    try:
        lang = Language(language)
        content = await file.read()
        translations = json.loads(content.decode('utf-8'))

        manager = TranslationManager()
        manager.translations[lang.value] = translations
        manager.save_translations(lang)

        return {
            "status": "success",
            "language": language,
            "filename": file.filename,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid language: {e!s}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/{language}")
async def export_translation(language: str):
    """导出翻译文件"""
    try:
        lang = Language(language)
        manager = TranslationManager()
        translations = manager.get_translations(lang)

        return {
            "language": language,
            "translations": translations,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid language: {e!s}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quality-report")
async def get_quality_report():
    """获取翻译质量报告"""
    try:
        report = check_all_translations()
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/completeness")
async def get_completeness():
    """获取翻译完整性"""
    try:
        checker = TranslationQualityChecker()
        completeness = checker.check_completeness()
        return {
            "completeness": completeness,
            "overall": sum(completeness.values()) / len(completeness) if completeness else 0,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/missing-keys/{language}")
async def get_missing_keys(language: str):
    """获取缺失的翻译键"""
    try:
        Language(language)
        checker = TranslationQualityChecker()
        missing = checker.check_missing_keys()
        return {
            "language": language,
            "missing_keys": missing.get(language, []),
            "count": len(missing.get(language, [])),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid language: {e!s}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/extra-keys/{language}")
async def get_extra_keys(language: str):
    """获取多余的翻译键"""
    try:
        Language(language)
        checker = TranslationQualityChecker()
        extra = checker.check_extra_keys()
        return {
            "language": language,
            "extra_keys": extra.get(language, []),
            "count": len(extra.get(language, [])),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid language: {e!s}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/empty-values/{language}")
async def get_empty_values(language: str):
    """获取空值"""
    try:
        Language(language)
        checker = TranslationQualityChecker()
        empty = checker.check_empty_values()
        return {
            "language": language,
            "empty_values": empty.get(language, []),
            "count": len(empty.get(language, [])),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid language: {e!s}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/parameter-consistency/{language}")
async def get_parameter_consistency(language: str):
    """获取参数一致性检查"""
    try:
        Language(language)
        checker = TranslationQualityChecker()
        inconsistencies = checker.check_parameter_consistency()
        return {
            "language": language,
            "inconsistencies": inconsistencies.get(language, []),
            "count": len(inconsistencies.get(language, [])),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid language: {e!s}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/length-consistency/{language}")
async def get_length_consistency(language: str):
    """获取长度一致性检查"""
    try:
        Language(language)
        checker = TranslationQualityChecker()
        length_issues = checker.check_length_consistency()
        return {
            "language": language,
            "length_issues": length_issues.get(language, []),
            "count": len(length_issues.get(language, [])),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid language: {e!s}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate/{language}")
async def validate_translation(language: str):
    """验证翻译文件"""
    try:
        from pathlib import Path

        from backend.app.core.translation_quality import TranslationValidator

        Language(language)
        lang_file = Path("locales") / f"{language}.json"

        if not lang_file.exists():
            raise HTTPException(status_code=404, detail=f"Translation file not found for {language}")

        syntax_valid, syntax_msg = TranslationValidator.validate_json_syntax(lang_file)
        encoding_valid, encoding_msg = TranslationValidator.validate_encoding(lang_file)

        return {
            "language": language,
            "syntax": {"valid": syntax_valid, "message": syntax_msg},
            "encoding": {"valid": encoding_valid, "message": encoding_msg},
            "overall_valid": syntax_valid and encoding_valid,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid language: {e!s}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
