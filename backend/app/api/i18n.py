"""
国际化API端点
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.app.core.i18n import (
    Language,
    Locale,
    LocalizationConfig,
    Region,
    i18n,
)

router = APIRouter(prefix="/api/i18n", tags=["i18n"])


class LocaleRequest(BaseModel):
    language: str
    region: str


class LocaleResponse(BaseModel):
    language: str
    region: str
    timezone: str
    currency: str
    dateFormat: str
    timeFormat: str


class TranslationResponse(BaseModel):
    language: str
    translations: dict[str, Any]


class SupportedLanguageResponse(BaseModel):
    code: str
    name: str


class SupportedRegionResponse(BaseModel):
    code: str
    name: str


@router.get("/supported-languages", response_model=list[SupportedLanguageResponse])
async def get_supported_languages():
    """获取支持的语言列表"""
    return [
        {"code": "en", "name": "English"},
        {"code": "zh", "name": "中文"},
        {"code": "ja", "name": "日本語"},
        {"code": "ko", "name": "한국어"},
        {"code": "es", "name": "Español"},
    ]


@router.get("/supported-regions", response_model=list[SupportedRegionResponse])
async def get_supported_regions():
    """获取支持的地区列表"""
    return [
        {"code": "US", "name": "United States"},
        {"code": "CN", "name": "China"},
        {"code": "JP", "name": "Japan"},
        {"code": "KR", "name": "Korea"},
        {"code": "ES", "name": "Spain"},
        {"code": "GB", "name": "United Kingdom"},
        {"code": "DE", "name": "Germany"},
        {"code": "FR", "name": "France"},
    ]


@router.post("/set-locale")
async def set_locale(request: LocaleRequest):
    """设置用户地区"""
    try:
        language = Language(request.language)
        region = Region(request.region)
        i18n.set_locale(language, region)
        return {"status": "success", "locale": str(Locale(language, region))}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid language or region: {e!s}")


@router.get("/locale", response_model=LocaleResponse)
async def get_locale():
    """获取当前地区配置"""
    locale = i18n.current_locale
    return {
        "language": locale.language.value,
        "region": locale.region.value,
        "timezone": LocalizationConfig.get_timezone(locale.region),
        "currency": LocalizationConfig.get_currency(locale.region),
        "dateFormat": LocalizationConfig.get_date_format(locale.region),
        "timeFormat": LocalizationConfig.get_time_format(locale.region),
    }


@router.get("/translations/{language}", response_model=TranslationResponse)
async def get_translations(language: str):
    """获取指定语言的所有翻译"""
    try:
        lang = Language(language)
        translations = i18n.translation_manager.get_translations(lang)
        return {
            "language": language,
            "translations": translations,
        }
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unsupported language: {language}")


@router.get("/translation")
async def get_translation(
    language: str = Query(...),
    key: str = Query(...),
    default: str = Query(None)
):
    """获取单个翻译"""
    try:
        lang = Language(language)
        translation = i18n.translation_manager.get_translation(lang, key, default)
        return {
            "language": language,
            "key": key,
            "value": translation,
        }
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unsupported language: {language}")


@router.get("/localization-config/{region}")
async def get_localization_config(region: str):
    """获取地区化配置"""
    try:
        reg = Region(region)
        return {
            "region": region,
            "timezone": LocalizationConfig.get_timezone(reg),
            "currency": LocalizationConfig.get_currency(reg),
            "dateFormat": LocalizationConfig.get_date_format(reg),
            "timeFormat": LocalizationConfig.get_time_format(reg),
            "numberFormat": LocalizationConfig.get_number_format(reg),
            "currencyFormat": LocalizationConfig.get_currency_format(reg),
        }
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unsupported region: {region}")


@router.post("/format-date")
async def format_date(
    language: str = Query(...),
    region: str = Query(...),
    timestamp: float = Query(...),
    format_str: str = Query(None)
):
    """格式化日期"""
    try:
        from datetime import datetime

        import pytz

        lang = Language(language)
        reg = Region(region)
        locale = Locale(lang, reg)
        context = i18n.get_context(locale)

        dt = datetime.fromtimestamp(timestamp, tz=pytz.UTC)
        formatted = context.format_date(dt, format_str)

        return {
            "formatted": formatted,
            "timezone": context.get_timezone(),
        }
    except (ValueError, Exception) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/format-currency")
async def format_currency(
    language: str = Query(...),
    region: str = Query(...),
    amount: float = Query(...),
    currency: str = Query(None)
):
    """格式化货币"""
    try:
        lang = Language(language)
        reg = Region(region)
        locale = Locale(lang, reg)
        context = i18n.get_context(locale)

        formatted = context.format_currency(amount, currency)

        return {
            "formatted": formatted,
            "currency": context.get_currency(),
        }
    except (ValueError, Exception) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/format-number")
async def format_number(
    region: str = Query(...),
    number: float = Query(...),
    decimal_places: int = Query(2)
):
    """格式化数字"""
    try:
        reg = Region(region)
        locale = Locale(Language.ENGLISH, reg)
        context = i18n.get_context(locale)

        formatted = context.format_number(number, decimal_places)

        return {
            "formatted": formatted,
            "numberFormat": LocalizationConfig.get_number_format(reg),
        }
    except (ValueError, Exception) as e:
        raise HTTPException(status_code=400, detail=str(e))
