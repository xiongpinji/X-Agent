"""
翻译质量检查工具
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple
from backend.app.core.i18n import Language


class TranslationQualityChecker:
    """翻译质量检查器"""

    def __init__(self, locales_dir: str = "locales"):
        self.locales_dir = Path(locales_dir)
        self.translations: Dict[str, Dict] = {}
        self._load_translations()

    def _load_translations(self):
        """加载所有翻译文件"""
        for lang in Language:
            lang_file = self.locales_dir / f"{lang.value}.json"
            if lang_file.exists():
                with open(lang_file, 'r', encoding='utf-8') as f:
                    self.translations[lang.value] = json.load(f)

    def check_completeness(self) -> Dict[str, float]:
        """检查翻译完整性"""
        if not self.translations:
            return {}

        reference_keys = self._get_all_keys(self.translations.get('en', {}))
        completeness = {}

        for lang, translations in self.translations.items():
            lang_keys = self._get_all_keys(translations)
            missing_keys = reference_keys - lang_keys
            completeness[lang] = (len(reference_keys) - len(missing_keys)) / len(reference_keys) * 100 if reference_keys else 0

        return completeness

    def check_missing_keys(self) -> Dict[str, List[str]]:
        """检查缺失的翻译键"""
        if not self.translations:
            return {}

        reference_keys = self._get_all_keys(self.translations.get('en', {}))
        missing = {}

        for lang, translations in self.translations.items():
            if lang == 'en':
                continue
            lang_keys = self._get_all_keys(translations)
            missing[lang] = sorted(list(reference_keys - lang_keys))

        return missing

    def check_extra_keys(self) -> Dict[str, List[str]]:
        """检查多余的翻译键"""
        if not self.translations:
            return {}

        reference_keys = self._get_all_keys(self.translations.get('en', {}))
        extra = {}

        for lang, translations in self.translations.items():
            if lang == 'en':
                continue
            lang_keys = self._get_all_keys(translations)
            extra[lang] = sorted(list(lang_keys - reference_keys))

        return extra

    def check_empty_values(self) -> Dict[str, List[str]]:
        """检查空值"""
        empty = {}

        for lang, translations in self.translations.items():
            empty_keys = self._find_empty_values(translations)
            if empty_keys:
                empty[lang] = empty_keys

        return empty

    def check_parameter_consistency(self) -> Dict[str, List[Tuple[str, str, str]]]:
        """检查参数一致性"""
        if not self.translations:
            return {}

        reference_params = self._extract_parameters(self.translations.get('en', {}))
        inconsistencies = {}

        for lang, translations in self.translations.items():
            if lang == 'en':
                continue
            lang_params = self._extract_parameters(translations)
            inconsistent = []

            for key, ref_params in reference_params.items():
                lang_params_set = lang_params.get(key, set())
                if ref_params != lang_params_set:
                    inconsistent.append((key, str(ref_params), str(lang_params_set)))

            if inconsistent:
                inconsistencies[lang] = inconsistent

        return inconsistencies

    def check_length_consistency(self) -> Dict[str, List[Tuple[str, int, int]]]:
        """检查长度一致性"""
        if not self.translations:
            return {}

        reference_lengths = self._get_lengths(self.translations.get('en', {}))
        length_issues = {}

        for lang, translations in self.translations.items():
            if lang == 'en':
                continue
            lang_lengths = self._get_lengths(translations)
            issues = []

            for key, ref_len in reference_lengths.items():
                lang_len = lang_lengths.get(key, 0)
                # 允许20%的长度差异
                if lang_len > 0 and abs(lang_len - ref_len) > ref_len * 0.2:
                    issues.append((key, ref_len, lang_len))

            if issues:
                length_issues[lang] = issues

        return length_issues

    def generate_report(self) -> Dict:
        """生成完整的质量检查报告"""
        return {
            "completeness": self.check_completeness(),
            "missing_keys": self.check_missing_keys(),
            "extra_keys": self.check_extra_keys(),
            "empty_values": self.check_empty_values(),
            "parameter_consistency": self.check_parameter_consistency(),
            "length_consistency": self.check_length_consistency(),
        }

    def _get_all_keys(self, obj: Dict, prefix: str = "") -> set:
        """递归获取所有键"""
        keys = set()
        for key, value in obj.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                keys.update(self._get_all_keys(value, full_key))
            else:
                keys.add(full_key)
        return keys

    def _find_empty_values(self, obj: Dict, prefix: str = "") -> List[str]:
        """递归查找空值"""
        empty = []
        for key, value in obj.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                empty.extend(self._find_empty_values(value, full_key))
            elif not value or (isinstance(value, str) and not value.strip()):
                empty.append(full_key)
        return empty

    def _extract_parameters(self, obj: Dict, prefix: str = "") -> Dict[str, set]:
        """提取所有参数"""
        import re
        params = {}
        pattern = r'\{(\w+)\}'

        for key, value in obj.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                params.update(self._extract_parameters(value, full_key))
            elif isinstance(value, str):
                found_params = set(re.findall(pattern, value))
                if found_params:
                    params[full_key] = found_params

        return params

    def _get_lengths(self, obj: Dict, prefix: str = "") -> Dict[str, int]:
        """获取所有值的长度"""
        lengths = {}
        for key, value in obj.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                lengths.update(self._get_lengths(value, full_key))
            elif isinstance(value, str):
                lengths[full_key] = len(value)
        return lengths


class TranslationValidator:
    """翻译验证器"""

    @staticmethod
    def validate_json_syntax(file_path: Path) -> Tuple[bool, str]:
        """验证JSON语法"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                json.load(f)
            return True, "Valid JSON"
        except json.JSONDecodeError as e:
            return False, f"JSON syntax error: {str(e)}"
        except Exception as e:
            return False, f"Error: {str(e)}"

    @staticmethod
    def validate_encoding(file_path: Path) -> Tuple[bool, str]:
        """验证文件编码"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                f.read()
            return True, "Valid UTF-8 encoding"
        except UnicodeDecodeError:
            return False, "Invalid UTF-8 encoding"
        except Exception as e:
            return False, f"Error: {str(e)}"

    @staticmethod
    def validate_structure(file_path: Path, reference_structure: Dict) -> Tuple[bool, List[str]]:
        """验证结构一致性"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            errors = []
            TranslationValidator._check_structure(data, reference_structure, "", errors)
            return len(errors) == 0, errors
        except Exception as e:
            return False, [str(e)]

    @staticmethod
    def _check_structure(data: Dict, reference: Dict, path: str, errors: List[str]):
        """递归检查结构"""
        for key, ref_value in reference.items():
            current_path = f"{path}.{key}" if path else key
            if key not in data:
                errors.append(f"Missing key: {current_path}")
            elif isinstance(ref_value, dict):
                if not isinstance(data[key], dict):
                    errors.append(f"Type mismatch at {current_path}: expected dict, got {type(data[key])}")
                else:
                    TranslationValidator._check_structure(data[key], ref_value, current_path, errors)


def check_all_translations(locales_dir: str = "locales") -> Dict:
    """检查所有翻译"""
    checker = TranslationQualityChecker(locales_dir)
    report = checker.generate_report()

    # 验证每个文件
    validation_results = {}
    for lang in Language:
        lang_file = Path(locales_dir) / f"{lang.value}.json"
        if lang_file.exists():
            syntax_valid, syntax_msg = TranslationValidator.validate_json_syntax(lang_file)
            encoding_valid, encoding_msg = TranslationValidator.validate_encoding(lang_file)
            validation_results[lang.value] = {
                "syntax": {"valid": syntax_valid, "message": syntax_msg},
                "encoding": {"valid": encoding_valid, "message": encoding_msg},
            }

    return {
        "quality_report": report,
        "validation_results": validation_results,
    }
