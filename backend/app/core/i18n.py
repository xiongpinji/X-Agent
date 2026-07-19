"""
Internationalization (i18n) support for X-Agent.
Provides multi-language support for UI, documentation, and prompts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Dict
import locale


class Language(str, Enum):
    """Supported languages."""
    ENGLISH = "en"
    CHINESE = "zh"
    SPANISH = "es"
    FRENCH = "fr"
    GERMAN = "de"
    JAPANESE = "ja"
    KOREAN = "ko"


@dataclass
class TranslationKey:
    """Translation key with context."""
    key: str
    context: Optional[str] = None
    plural: bool = False

    def __str__(self) -> str:
        if self.context:
            return f"{self.context}.{self.key}"
        return self.key


class LanguageDetector:
    """Detects system language."""

    @staticmethod
    def detect_language() -> Language:
        """Detect system language."""
        try:
            system_locale = locale.getdefaultlocale()[0]
            if system_locale:
                lang_code = system_locale.split('_')[0]
                for lang in Language:
                    if lang.value == lang_code:
                        return lang
        except Exception:
            pass

        return Language.ENGLISH

    @staticmethod
    def get_language_from_code(code: str) -> Optional[Language]:
        """Get language from code."""
        for lang in Language:
            if lang.value == code:
                return lang
        return None


class TranslationStore:
    """Stores and manages translations."""

    def __init__(self):
        self.translations: Dict[Language, Dict[str, str]] = {}
        self._load_default_translations()

    def _load_default_translations(self) -> None:
        """Load default translations."""
        # English translations
        self.translations[Language.ENGLISH] = {
            # UI
            "ui.welcome": "Welcome to X-Agent",
            "ui.goodbye": "Goodbye!",
            "ui.error": "Error",
            "ui.success": "Success",
            "ui.loading": "Loading...",
            "ui.cancel": "Cancel",
            "ui.confirm": "Confirm",
            "ui.yes": "Yes",
            "ui.no": "No",

            # Commands
            "cmd.run": "Run a task",
            "cmd.chat": "Start interactive chat",
            "cmd.tools": "Manage tools",
            "cmd.config": "Manage configuration",
            "cmd.logs": "View logs",
            "cmd.status": "Show system status",

            # Messages
            "msg.task_started": "Task started: {task}",
            "msg.task_completed": "Task completed successfully",
            "msg.task_failed": "Task failed: {error}",
            "msg.tool_installed": "Tool installed: {tool}",
            "msg.tool_uninstalled": "Tool uninstalled: {tool}",
            "msg.config_updated": "Configuration updated: {key} = {value}",

            # Errors
            "err.task_not_found": "Task not found: {task}",
            "err.tool_not_found": "Tool not found: {tool}",
            "err.invalid_config": "Invalid configuration: {reason}",
            "err.connection_failed": "Connection failed: {error}",
        }

        # Chinese translations
        self.translations[Language.CHINESE] = {
            # UI
            "ui.welcome": "欢迎使用 X-Agent",
            "ui.goodbye": "再见！",
            "ui.error": "错误",
            "ui.success": "成功",
            "ui.loading": "加载中...",
            "ui.cancel": "取消",
            "ui.confirm": "确认",
            "ui.yes": "是",
            "ui.no": "否",

            # Commands
            "cmd.run": "运行任务",
            "cmd.chat": "启动交互式聊天",
            "cmd.tools": "管理工具",
            "cmd.config": "管理配置",
            "cmd.logs": "查看日志",
            "cmd.status": "显示系统状态",

            # Messages
            "msg.task_started": "任务已启动: {task}",
            "msg.task_completed": "任务完成成功",
            "msg.task_failed": "任务失败: {error}",
            "msg.tool_installed": "工具已安装: {tool}",
            "msg.tool_uninstalled": "工具已卸载: {tool}",
            "msg.config_updated": "配置已更新: {key} = {value}",

            # Errors
            "err.task_not_found": "任务未找到: {task}",
            "err.tool_not_found": "工具未找到: {tool}",
            "err.invalid_config": "无效的配置: {reason}",
            "err.connection_failed": "连接失败: {error}",
        }

        # Spanish translations
        self.translations[Language.SPANISH] = {
            "ui.welcome": "Bienvenido a X-Agent",
            "ui.goodbye": "¡Adiós!",
            "ui.error": "Error",
            "ui.success": "Éxito",
            "cmd.run": "Ejecutar una tarea",
            "cmd.chat": "Iniciar chat interactivo",
            "msg.task_started": "Tarea iniciada: {task}",
            "msg.task_completed": "Tarea completada exitosamente",
        }

        # French translations
        self.translations[Language.FRENCH] = {
            "ui.welcome": "Bienvenue dans X-Agent",
            "ui.goodbye": "Au revoir!",
            "ui.error": "Erreur",
            "ui.success": "Succès",
            "cmd.run": "Exécuter une tâche",
            "cmd.chat": "Démarrer le chat interactif",
            "msg.task_started": "Tâche démarrée: {task}",
            "msg.task_completed": "Tâche complétée avec succès",
        }

    def add_translation(self, language: Language, key: str, value: str) -> None:
        """Add translation."""
        if language not in self.translations:
            self.translations[language] = {}
        self.translations[language][key] = value

    def get_translation(self, language: Language, key: str) -> Optional[str]:
        """Get translation."""
        if language not in self.translations:
            return None
        return self.translations[language].get(key)

    def load_from_file(self, language: Language, file_path: Path) -> bool:
        """Load translations from JSON file."""
        try:
            data = json.loads(file_path.read_text(encoding='utf-8'))
            self.translations[language] = data
            return True
        except Exception:
            return False

    def save_to_file(self, language: Language, file_path: Path) -> bool:
        """Save translations to JSON file."""
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            data = self.translations.get(language, {})
            file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            return True
        except Exception:
            return False


class Translator:
    """Main translation interface."""

    def __init__(self, default_language: Language = Language.ENGLISH):
        self.current_language = default_language
        self.store = TranslationStore()

    def set_language(self, language: Language) -> None:
        """Set current language."""
        self.current_language = language

    def set_language_by_code(self, code: str) -> bool:
        """Set language by code."""
        lang = LanguageDetector.get_language_from_code(code)
        if lang:
            self.set_language(lang)
            return True
        return False

    def auto_detect_language(self) -> None:
        """Auto-detect and set language."""
        self.current_language = LanguageDetector.detect_language()

    def translate(self, key: str, **kwargs) -> str:
        """Translate key with optional formatting."""
        translation = self.store.get_translation(self.current_language, key)

        if translation is None:
            # Fallback to English
            translation = self.store.get_translation(Language.ENGLISH, key)

        if translation is None:
            # Return key if no translation found
            return key

        # Format with provided arguments
        if kwargs:
            try:
                return translation.format(**kwargs)
            except KeyError:
                return translation

        return translation

    def t(self, key: str, **kwargs) -> str:
        """Shorthand for translate."""
        return self.translate(key, **kwargs)

    def get_available_languages(self) -> list[Language]:
        """Get available languages."""
        return list(self.store.translations.keys())

    def get_current_language(self) -> Language:
        """Get current language."""
        return self.current_language


class PromptTranslator:
    """Translates LLM prompts."""

    def __init__(self, translator: Translator):
        self.translator = translator
        self.prompt_templates = {
            Language.ENGLISH: {
                "system": "You are a helpful AI assistant.",
                "task_instruction": "Please complete the following task: {task}",
                "tool_description": "Tool: {name}\nDescription: {description}",
            },
            Language.CHINESE: {
                "system": "你是一个有帮助的AI助手。",
                "task_instruction": "请完成以下任务: {task}",
                "tool_description": "工具: {name}\n描述: {description}",
            },
        }

    def translate_prompt(self, template_key: str, **kwargs) -> str:
        """Translate prompt template."""
        templates = self.prompt_templates.get(self.translator.current_language)
        if not templates:
            templates = self.prompt_templates[Language.ENGLISH]

        template = templates.get(template_key, "")
        if kwargs:
            try:
                return template.format(**kwargs)
            except KeyError:
                return template

        return template

    def add_prompt_template(
        self,
        language: Language,
        template_key: str,
        template: str
    ) -> None:
        """Add prompt template."""
        if language not in self.prompt_templates:
            self.prompt_templates[language] = {}
        self.prompt_templates[language][template_key] = template


class LocalizationManager:
    """Manages all localization aspects."""

    def __init__(self):
        self.translator = Translator()
        self.prompt_translator = PromptTranslator(self.translator)

    def initialize(self, language: Optional[Language] = None) -> None:
        """Initialize localization."""
        if language:
            self.translator.set_language(language)
        else:
            self.translator.auto_detect_language()

    def translate(self, key: str, **kwargs) -> str:
        """Translate UI text."""
        return self.translator.translate(key, **kwargs)

    def translate_prompt(self, template_key: str, **kwargs) -> str:
        """Translate LLM prompt."""
        return self.prompt_translator.translate_prompt(template_key, **kwargs)

    def set_language(self, language: Language) -> None:
        """Set language."""
        self.translator.set_language(language)

    def get_current_language(self) -> Language:
        """Get current language."""
        return self.translator.get_current_language()

    def load_translations(self, language: Language, file_path: Path) -> bool:
        """Load translations from file."""
        return self.translator.store.load_from_file(language, file_path)

    def save_translations(self, language: Language, file_path: Path) -> bool:
        """Save translations to file."""
        return self.translator.store.save_to_file(language, file_path)


# Global localization manager instance
_localization_manager: Optional[LocalizationManager] = None


def get_localization_manager() -> LocalizationManager:
    """Get global localization manager."""
    global _localization_manager
    if _localization_manager is None:
        _localization_manager = LocalizationManager()
        _localization_manager.initialize()
    return _localization_manager


def t(key: str, **kwargs) -> str:
    """Translate text."""
    return get_localization_manager().translate(key, **kwargs)


def set_language(language: Language) -> None:
    """Set language."""
    get_localization_manager().set_language(language)


# ============================================================================
# Region / Locale / formatting layer
# ============================================================================


class Region(str, Enum):
    """Supported regions (ISO 3166-1 alpha-2)."""
    US = "US"  # United States
    CN = "CN"  # China
    JP = "JP"  # Japan
    KR = "KR"  # South Korea
    ES = "ES"  # Spain
    FR = "FR"  # France
    DE = "DE"  # Germany
    GB = "GB"  # United Kingdom


@dataclass(frozen=True)
class Locale:
    """A language + region pairing, e.g. en_US."""
    language: Language
    region: Region

    @property
    def code(self) -> str:
        return f"{self.language.value}_{self.region.value}"

    def __str__(self) -> str:
        return self.code


class LocalizationConfig:
    """Per-region localization defaults (timezone, currency, formats)."""

    _TIMEZONES: Dict[Region, str] = {
        Region.US: "America/New_York",
        Region.CN: "Asia/Shanghai",
        Region.JP: "Asia/Tokyo",
        Region.KR: "Asia/Seoul",
        Region.ES: "Europe/Madrid",
        Region.FR: "Europe/Paris",
        Region.DE: "Europe/Berlin",
        Region.GB: "Europe/London",
    }

    _CURRENCIES: Dict[Region, str] = {
        Region.US: "USD",
        Region.CN: "CNY",
        Region.JP: "JPY",
        Region.KR: "KRW",
        Region.ES: "EUR",
        Region.FR: "EUR",
        Region.DE: "EUR",
        Region.GB: "GBP",
    }

    _DATE_FORMATS: Dict[Region, str] = {
        Region.US: "MM/DD/YYYY",
        Region.CN: "YYYY-MM-DD",
        Region.JP: "YYYY年MM月DD日",
        Region.KR: "YYYY-MM-DD",
        Region.ES: "DD/MM/YYYY",
        Region.FR: "DD/MM/YYYY",
        Region.DE: "DD.MM.YYYY",
        Region.GB: "DD/MM/YYYY",
    }

    _TIME_FORMATS: Dict[Region, str] = {
        Region.US: "hh:mm:ss A",
        Region.CN: "HH:mm:ss",
        Region.JP: "HH:mm:ss",
        Region.KR: "HH:mm:ss",
        Region.ES: "HH:mm:ss",
        Region.FR: "HH:mm:ss",
        Region.DE: "HH:mm:ss",
        Region.GB: "HH:mm:ss",
    }

    # Regions that use comma as decimal separator and dot as thousands separator
    _COMMA_DECIMAL_REGIONS = {Region.ES, Region.FR, Region.DE}

    _CURRENCY_FORMATS: Dict[Region, Dict[str, str]] = {
        Region.US: {"symbol": "$", "position": "prefix"},
        Region.CN: {"symbol": "¥", "position": "prefix"},
        Region.JP: {"symbol": "¥", "position": "prefix"},
        Region.KR: {"symbol": "₩", "position": "suffix"},
        Region.ES: {"symbol": "€", "position": "suffix"},
        Region.FR: {"symbol": "€", "position": "suffix"},
        Region.DE: {"symbol": "€", "position": "suffix"},
        Region.GB: {"symbol": "£", "position": "prefix"},
    }

    @classmethod
    def get_timezone(cls, region: Region) -> str:
        return cls._TIMEZONES.get(region, "UTC")

    @classmethod
    def get_currency(cls, region: Region) -> str:
        return cls._CURRENCIES.get(region, "USD")

    @classmethod
    def get_date_format(cls, region: Region) -> str:
        return cls._DATE_FORMATS.get(region, "YYYY-MM-DD")

    @classmethod
    def get_time_format(cls, region: Region) -> str:
        return cls._TIME_FORMATS.get(region, "HH:mm:ss")

    @classmethod
    def get_number_format(cls, region: Region) -> Dict[str, str]:
        if region in cls._COMMA_DECIMAL_REGIONS:
            return {"decimal": ",", "thousands": "."}
        return {"decimal": ".", "thousands": ","}

    @classmethod
    def get_currency_format(cls, region: Region) -> Dict[str, str]:
        return cls._CURRENCY_FORMATS.get(
            region, {"symbol": "$", "position": "prefix"}
        )


class TranslationManager:
    """Translation lookup with key-fallback and per-language stores."""

    def __init__(self) -> None:
        self._store = TranslationStore()

    def add_translation(self, language: Language, key: str, value: str) -> None:
        self._store.add_translation(language, key, value)

    def get_translation(self, language: Language, key: str) -> str:
        value = self._store.get_translation(language, key)
        if value is None:
            value = self._store.get_translation(Language.ENGLISH, key)
        # Fallback to the key itself when no translation exists
        return value if value is not None else key

    def get_translations(self, language: Language) -> Dict[str, str]:
        return dict(self._store.translations.get(language, {}))


class I18nFormatter:
    """Formats dates, numbers, currencies and percentages for a locale."""

    def __init__(self, locale: Locale) -> None:
        self.locale = locale
        self.region = locale.region

    def format_date(self, dt: datetime) -> str:
        fmt = LocalizationConfig.get_date_format(self.region)
        return (
            fmt.replace("YYYY", f"{dt.year:04d}")
            .replace("MM", f"{dt.month:02d}")
            .replace("DD", f"{dt.day:02d}")
        )

    def format_time(self, dt: datetime) -> str:
        fmt = LocalizationConfig.get_time_format(self.region)
        hour24 = dt.hour
        if "A" in fmt:  # 12-hour clock with AM/PM
            meridiem = "AM" if hour24 < 12 else "PM"
            hour12 = hour24 % 12 or 12
            return (
                fmt.replace("hh", f"{hour12:02d}")
                .replace("mm", f"{dt.minute:02d}")
                .replace("ss", f"{dt.second:02d}")
                .replace("A", meridiem)
            )
        return (
            fmt.replace("HH", f"{hour24:02d}")
            .replace("mm", f"{dt.minute:02d}")
            .replace("ss", f"{dt.second:02d}")
        )

    def format_number(self, value: float, decimals: int = 2) -> str:
        fmt = LocalizationConfig.get_number_format(self.region)
        # Build with neutral separators first, then swap to locale separators.
        base = f"{value:,.{decimals}f}"  # e.g. "1,234.56"
        return (
            base.replace(",", "\x00")
            .replace(".", fmt["decimal"])
            .replace("\x00", fmt["thousands"])
        )

    def format_currency(self, value: float, decimals: int = 2) -> str:
        cfg = LocalizationConfig.get_currency_format(self.region)
        number = self.format_number(value, decimals)
        if cfg["position"] == "suffix":
            return f"{number}{cfg['symbol']}"
        return f"{cfg['symbol']}{number}"

    def format_percentage(self, ratio: float, decimals: int = 0) -> str:
        return f"{ratio * 100:.{decimals}f}%"


class I18nContext:
    """Bundles a locale + translation manager with convenience formatters."""

    def __init__(self, locale: Locale, manager: TranslationManager) -> None:
        self.locale = locale
        self.manager = manager
        self.formatter = I18nFormatter(locale)

    def get_timezone(self) -> str:
        return LocalizationConfig.get_timezone(self.locale.region)

    def get_currency(self) -> str:
        return LocalizationConfig.get_currency(self.locale.region)

    def translate(self, key: str) -> str:
        return self.manager.get_translation(self.locale.language, key)

    def format_date(self, dt: datetime) -> str:
        return self.formatter.format_date(dt)

    def format_time(self, dt: datetime) -> str:
        return self.formatter.format_time(dt)

    def format_number(self, value: float, decimals: int = 2) -> str:
        return self.formatter.format_number(value, decimals)

    def format_currency(self, value: float, decimals: int = 2) -> str:
        return self.formatter.format_currency(value, decimals)

    def format_percentage(self, ratio: float, decimals: int = 0) -> str:
        return self.formatter.format_percentage(ratio, decimals)


class I18nManager:
    """Singleton i18n manager: holds current locale + supported metadata."""

    _instance: Optional["I18nManager"] = None

    _SUPPORTED_LANGUAGES = [
        ("en", "English"),
        ("zh", "中文"),
        ("ja", "日本語"),
        ("ko", "한국어"),
        ("es", "Español"),
    ]

    _SUPPORTED_REGIONS = [
        ("US", "United States"),
        ("CN", "China"),
        ("JP", "Japan"),
        ("KR", "South Korea"),
        ("ES", "Spain"),
        ("FR", "France"),
        ("DE", "Germany"),
        ("GB", "United Kingdom"),
    ]

    def __new__(cls) -> "I18nManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self.current_locale = Locale(Language.ENGLISH, Region.US)
        self.translation_manager = TranslationManager()
        self._initialized = True

    def set_locale(self, language: Language, region: Region) -> None:
        self.current_locale = Locale(language, region)

    def get_context(self) -> I18nContext:
        return I18nContext(self.current_locale, self.translation_manager)

    def get_supported_languages(self) -> list[tuple[str, str]]:
        return list(self._SUPPORTED_LANGUAGES)

    def get_supported_regions(self) -> list[tuple[str, str]]:
        return list(self._SUPPORTED_REGIONS)
