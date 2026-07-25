"""P2-03: PII 自动检测与脱敏引擎.

检测文本中的个人身份信息 (PII), 支持:
- 邮箱地址
- 手机号码 (中国/国际)
- 身份证号 (中国)
- IP 地址
- 银行卡号
- 姓名模式 (可选)

脱敏策略:
- mask: 部分遮盖 (保留首尾字符)
- hash: SHA-256 哈希替换
- remove: 完全移除
- generalize: 泛化 (如年龄→年龄段)
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from enum import StrEnum

logger = logging.getLogger(__name__)


class PIIType(StrEnum):
    """PII 类型."""

    EMAIL = "email"
    PHONE_CN = "phone_cn"
    PHONE_INTL = "phone_intl"
    ID_CARD_CN = "id_card_cn"
    IP_ADDRESS = "ip_address"
    BANK_CARD = "bank_card"
    URL_WITH_PARAMS = "url_with_params"


class MaskStrategy(StrEnum):
    """脱敏策略."""

    MASK = "mask"        # 部分遮盖: j***@example.com
    HASH = "hash"        # SHA-256: [HASH:a1b2c3]
    REMOVE = "remove"    # 完全移除: [REMOVED]
    GENERALIZE = "generalize"  # 泛化


@dataclass
class PIIMatch:
    """PII 匹配结果."""

    pii_type: PIIType
    value: str
    start: int
    end: int
    confidence: float = 1.0


@dataclass
class PIIScanResult:
    """PII 扫描结果."""

    text: str
    matches: list[PIIMatch] = field(default_factory=list)
    has_pii: bool = False
    masked_text: str = ""

    @property
    def pii_count(self) -> int:
        return len(self.matches)


# ─── 检测模式 ─────────────────────────────────────────────────────────────────

_PATTERNS: list[tuple[PIIType, re.Pattern, float]] = [
    # 邮箱
    (PIIType.EMAIL, re.compile(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    ), 0.95),
    # 中国手机号 (11位, 1开头)
    (PIIType.PHONE_CN, re.compile(
        r'(?<!\d)1[3-9]\d{9}(?!\d)'
    ), 0.90),
    # 国际电话 (+XX XXXXXXXXXX)
    (PIIType.PHONE_INTL, re.compile(
        r'\+\d{1,3}[-.\s]?\d{6,14}'
    ), 0.80),
    # 中国身份证 (18位)
    (PIIType.ID_CARD_CN, re.compile(
        r'(?<!\d)[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)'
    ), 0.95),
    # IPv4 地址
    (PIIType.IP_ADDRESS, re.compile(
        r'(?<!\d)(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)(?!\d)'
    ), 0.85),
    # 银行卡号 (16-19位数字)
    (PIIType.BANK_CARD, re.compile(
        r'(?<!\d)[3-6]\d{15,18}(?!\d)'
    ), 0.75),
    # 带参数的 URL (可能含 token/key)
    (PIIType.URL_WITH_PARAMS, re.compile(
        r'https?://[^\s]+[?&](?:token|key|secret|password|api_key|access_token)=[^\s&]+'
    ), 0.90),
]


# ─── PIIDetector ──────────────────────────────────────────────────────────────


class PIIDetector:
    """PII 检测器.

    扫描文本中的 PII, 返回匹配位置和类型。
    """

    def __init__(self, enabled_types: set[PIIType] | None = None,
                 min_confidence: float = 0.7):
        self._enabled_types = enabled_types
        self._min_confidence = min_confidence

    def scan(self, text: str) -> PIIScanResult:
        """扫描文本中的 PII."""
        if not text:
            return PIIScanResult(text=text, has_pii=False, masked_text=text)

        matches: list[PIIMatch] = []
        for pii_type, pattern, confidence in _PATTERNS:
            if self._enabled_types and pii_type not in self._enabled_types:
                continue
            if confidence < self._min_confidence:
                continue
            for m in pattern.finditer(text):
                matches.append(PIIMatch(
                    pii_type=pii_type,
                    value=m.group(),
                    start=m.start(),
                    end=m.end(),
                    confidence=confidence,
                ))

        # 去重: 移除被更长匹配覆盖的短匹配
        matches = self._deduplicate(matches)
        matches.sort(key=lambda x: x.start)

        return PIIScanResult(
            text=text,
            matches=matches,
            has_pii=len(matches) > 0,
            masked_text=text,
        )

    def contains_pii(self, text: str) -> bool:
        """快速检查是否包含 PII."""
        return self.scan(text).has_pii

    @staticmethod
    def _deduplicate(matches: list[PIIMatch]) -> list[PIIMatch]:
        """移除重叠匹配 (保留置信度更高的)."""
        if len(matches) <= 1:
            return matches
        matches.sort(key=lambda x: (x.start, -(x.end - x.start), -x.confidence))
        result = [matches[0]]
        for m in matches[1:]:
            last = result[-1]
            if m.start < last.end:
                # 重叠: 保留更长/更高置信度的
                if m.confidence > last.confidence or (m.end - m.start) > (last.end - last.start):
                    result[-1] = m
            else:
                result.append(m)
        return result


# ─── PIIMasker ────────────────────────────────────────────────────────────────


class PIIMasker:
    """PII 脱敏器.

    对检测到的 PII 应用脱敏策略。
    """

    def __init__(self, default_strategy: MaskStrategy = MaskStrategy.MASK):
        self._detector = PIIDetector()
        self._default_strategy = default_strategy
        self._strategy_overrides: dict[PIIType, MaskStrategy] = {}

    def set_strategy(self, pii_type: PIIType, strategy: MaskStrategy) -> None:
        """为特定 PII 类型设置脱敏策略."""
        self._strategy_overrides[pii_type] = strategy

    def mask(self, text: str) -> PIIScanResult:
        """检测并脱敏文本中的 PII."""
        scan_result = self._detector.scan(text)
        if not scan_result.has_pii:
            scan_result.masked_text = text
            return scan_result

        # 从后向前替换, 避免偏移
        masked = text
        for match in reversed(scan_result.matches):
            strategy = self._strategy_overrides.get(match.pii_type, self._default_strategy)
            replacement = self._apply_strategy(match, strategy)
            masked = masked[:match.start] + replacement + masked[match.end:]

        scan_result.masked_text = masked
        return scan_result

    def mask_dict(self, data: dict, keys_to_scan: list[str] | None = None) -> dict:
        """脱敏字典中的字符串值."""
        result = {}
        for key, value in data.items():
            if keys_to_scan and key not in keys_to_scan:
                result[key] = value
            elif isinstance(value, str):
                result[key] = self.mask(value).masked_text
            elif isinstance(value, dict):
                result[key] = self.mask_dict(value)
            else:
                result[key] = value
        return result

    @staticmethod
    def _apply_strategy(match: PIIMatch, strategy: MaskStrategy) -> str:
        """应用脱敏策略."""
        value = match.value

        if strategy == MaskStrategy.REMOVE:
            return "[REMOVED]"

        if strategy == MaskStrategy.HASH:
            h = hashlib.sha256(value.encode()).hexdigest()[:12]
            return f"[HASH:{h}]"

        if strategy == MaskStrategy.GENERALIZE:
            return f"[{match.pii_type.value}]"

        # MASK: 部分遮盖
        return _mask_value(value, match.pii_type)


def _mask_value(value: str, pii_type: PIIType) -> str:
    """部分遮盖 PII 值."""
    if pii_type == PIIType.EMAIL:
        parts = value.split("@")
        if len(parts) == 2:
            local = parts[0]
            masked_local = local[0] + "***" if len(local) > 1 else "***"
            return f"{masked_local}@{parts[1]}"
        return "***@***"

    if pii_type in (PIIType.PHONE_CN, PIIType.PHONE_INTL):
        if len(value) >= 7:
            return value[:3] + "****" + value[-4:]
        return "****"

    if pii_type == PIIType.ID_CARD_CN:
        return value[:6] + "********" + value[-4:]

    if pii_type == PIIType.BANK_CARD:
        return value[:4] + " **** **** " + value[-4:]

    if pii_type == PIIType.IP_ADDRESS:
        parts = value.split(".")
        return f"{parts[0]}.{parts[1]}.*.*"

    if pii_type == PIIType.URL_WITH_PARAMS:
        # 保留 URL 前缀, 遮盖参数值
        return re.sub(r'((?:token|key|secret|password|api_key|access_token)=)[^\s&]+',
                      r'\1[MASKED]', value)

    # 默认: 保留首尾
    if len(value) > 4:
        return value[0] + "***" + value[-1]
    return "***"
