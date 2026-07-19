"""
国际化功能测试
"""

import pytest
from datetime import datetime
import pytz

from backend.app.core.i18n import (
    Language, Region, Locale, LocalizationConfig,
    TranslationManager, I18nFormatter, I18nContext, I18nManager
)


class TestLanguageAndRegion:
    """测试语言和地区"""

    def test_language_enum(self):
        assert Language.ENGLISH.value == "en"
        assert Language.CHINESE.value == "zh"
        assert Language.JAPANESE.value == "ja"
        assert Language.KOREAN.value == "ko"
        assert Language.SPANISH.value == "es"

    def test_region_enum(self):
        assert Region.US.value == "US"
        assert Region.CN.value == "CN"
        assert Region.JP.value == "JP"

    def test_locale_creation(self):
        locale = Locale(Language.ENGLISH, Region.US)
        assert locale.language == Language.ENGLISH
        assert locale.region == Region.US
        assert locale.code == "en_US"

    def test_locale_equality(self):
        locale1 = Locale(Language.ENGLISH, Region.US)
        locale2 = Locale(Language.ENGLISH, Region.US)
        assert locale1 == locale2

    def test_locale_hash(self):
        locale1 = Locale(Language.ENGLISH, Region.US)
        locale2 = Locale(Language.ENGLISH, Region.US)
        assert hash(locale1) == hash(locale2)


class TestLocalizationConfig:
    """测试地区化配置"""

    def test_get_timezone(self):
        assert LocalizationConfig.get_timezone(Region.US) == "America/New_York"
        assert LocalizationConfig.get_timezone(Region.CN) == "Asia/Shanghai"
        assert LocalizationConfig.get_timezone(Region.JP) == "Asia/Tokyo"

    def test_get_currency(self):
        assert LocalizationConfig.get_currency(Region.US) == "USD"
        assert LocalizationConfig.get_currency(Region.CN) == "CNY"
        assert LocalizationConfig.get_currency(Region.JP) == "JPY"

    def test_get_date_format(self):
        assert LocalizationConfig.get_date_format(Region.US) == "MM/DD/YYYY"
        assert LocalizationConfig.get_date_format(Region.CN) == "YYYY-MM-DD"
        assert LocalizationConfig.get_date_format(Region.JP) == "YYYY年MM月DD日"

    def test_get_time_format(self):
        assert LocalizationConfig.get_time_format(Region.US) == "hh:mm:ss A"
        assert LocalizationConfig.get_time_format(Region.CN) == "HH:mm:ss"

    def test_get_number_format(self):
        us_format = LocalizationConfig.get_number_format(Region.US)
        assert us_format["decimal"] == "."
        assert us_format["thousands"] == ","

        es_format = LocalizationConfig.get_number_format(Region.ES)
        assert es_format["decimal"] == ","
        assert es_format["thousands"] == "."

    def test_get_currency_format(self):
        us_format = LocalizationConfig.get_currency_format(Region.US)
        assert us_format["symbol"] == "$"
        assert us_format["position"] == "prefix"

        kr_format = LocalizationConfig.get_currency_format(Region.KR)
        assert kr_format["symbol"] == "₩"
        assert kr_format["position"] == "suffix"


class TestI18nFormatter:
    """测试国际化格式化器"""

    def test_format_date_us(self):
        locale = Locale(Language.ENGLISH, Region.US)
        formatter = I18nFormatter(locale)
        dt = datetime(2026, 5, 29, 12, 30, 45)
        formatted = formatter.format_date(dt)
        assert "05" in formatted or "5" in formatted
        assert "29" in formatted

    def test_format_date_cn(self):
        locale = Locale(Language.CHINESE, Region.CN)
        formatter = I18nFormatter(locale)
        dt = datetime(2026, 5, 29, 12, 30, 45)
        formatted = formatter.format_date(dt)
        assert "2026" in formatted
        assert "05" in formatted or "5" in formatted
        assert "29" in formatted

    def test_format_number_us(self):
        locale = Locale(Language.ENGLISH, Region.US)
        formatter = I18nFormatter(locale)
        formatted = formatter.format_number(1234.56)
        assert formatted == "1,234.56"

    def test_format_number_es(self):
        locale = Locale(Language.SPANISH, Region.ES)
        formatter = I18nFormatter(locale)
        formatted = formatter.format_number(1234.56)
        assert formatted == "1.234,56"

    def test_format_currency_us(self):
        locale = Locale(Language.ENGLISH, Region.US)
        formatter = I18nFormatter(locale)
        formatted = formatter.format_currency(1234.56)
        assert formatted == "$1,234.56"

    def test_format_currency_cn(self):
        locale = Locale(Language.CHINESE, Region.CN)
        formatter = I18nFormatter(locale)
        formatted = formatter.format_currency(1234.56)
        assert formatted == "¥1,234.56"

    def test_format_currency_kr(self):
        locale = Locale(Language.KOREAN, Region.KR)
        formatter = I18nFormatter(locale)
        formatted = formatter.format_currency(1234.56)
        assert "₩" in formatted
        assert "1,234.56" in formatted

    def test_format_percentage(self):
        locale = Locale(Language.ENGLISH, Region.US)
        formatter = I18nFormatter(locale)
        formatted = formatter.format_percentage(0.5)
        assert "50" in formatted
        assert "%" in formatted


class TestI18nContext:
    """测试国际化上下文"""

    def test_get_timezone(self):
        locale = Locale(Language.ENGLISH, Region.CN)
        manager = TranslationManager()
        context = I18nContext(locale, manager)
        assert context.get_timezone() == "Asia/Shanghai"

    def test_get_currency(self):
        locale = Locale(Language.ENGLISH, Region.US)
        manager = TranslationManager()
        context = I18nContext(locale, manager)
        assert context.get_currency() == "USD"

    def test_format_methods(self):
        locale = Locale(Language.ENGLISH, Region.US)
        manager = TranslationManager()
        context = I18nContext(locale, manager)

        dt = datetime(2026, 5, 29, 12, 30, 45)
        formatted_date = context.format_date(dt)
        assert formatted_date is not None

        formatted_currency = context.format_currency(100)
        assert "$" in formatted_currency

        formatted_number = context.format_number(1000.5)
        assert "1,000.50" == formatted_number


class TestI18nManager:
    """测试国际化管理器"""

    def test_singleton(self):
        manager1 = I18nManager()
        manager2 = I18nManager()
        assert manager1 is manager2

    def test_set_locale(self):
        manager = I18nManager()
        manager.set_locale(Language.CHINESE, Region.CN)
        assert manager.current_locale.language == Language.CHINESE
        assert manager.current_locale.region == Region.CN

    def test_get_context(self):
        manager = I18nManager()
        context = manager.get_context()
        assert context is not None
        assert isinstance(context, I18nContext)

    def test_get_supported_languages(self):
        manager = I18nManager()
        languages = manager.get_supported_languages()
        assert len(languages) == 5
        assert ("en", "English") in languages
        assert ("zh", "中文") in languages

    def test_get_supported_regions(self):
        manager = I18nManager()
        regions = manager.get_supported_regions()
        assert len(regions) == 8
        assert ("US", "United States") in regions
        assert ("CN", "China") in regions


class TestTranslationManager:
    """测试翻译管理器"""

    def test_get_translation_fallback(self):
        manager = TranslationManager()
        # 如果翻译不存在，应该返回键本身
        translation = manager.get_translation(Language.ENGLISH, "nonexistent.key")
        assert translation == "nonexistent.key"

    def test_add_translation(self):
        manager = TranslationManager()
        manager.add_translation(Language.ENGLISH, "test.key", "Test Value")
        translation = manager.get_translation(Language.ENGLISH, "test.key")
        assert translation == "Test Value"

    def test_get_translations(self):
        manager = TranslationManager()
        translations = manager.get_translations(Language.ENGLISH)
        assert isinstance(translations, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
