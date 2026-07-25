"""P2-03: 数据驻留配置.

支持按租户/区域配置数据存储位置, 满足数据主权要求:
- EU 数据不出欧盟
- 中国数据境内存储
- 按租户指定存储区域
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum

logger = logging.getLogger(__name__)


class DataRegion(StrEnum):
    """数据驻留区域."""

    GLOBAL = "global"
    EU = "eu"
    CN = "cn"
    US = "us"
    APAC = "apac"


@dataclass
class ResidencyRule:
    """单条驻留规则."""

    tenant_id: str
    region: DataRegion
    allowed_regions: list[DataRegion] = field(default_factory=list)
    block_cross_border: bool = True

    def __post_init__(self):
        if not self.allowed_regions:
            self.allowed_regions = [self.region]


@dataclass
class DataResidencyConfig:
    """数据驻留配置."""

    default_region: DataRegion = DataRegion.GLOBAL
    rules: dict[str, ResidencyRule] = field(default_factory=dict)
    enabled: bool = False

    def get_rule(self, tenant_id: str) -> ResidencyRule | None:
        """获取租户的驻留规则."""
        return self.rules.get(tenant_id)

    def set_rule(self, tenant_id: str, region: DataRegion,
                 allowed_regions: list[DataRegion] | None = None,
                 block_cross_border: bool = True) -> ResidencyRule:
        """设置租户驻留规则."""
        rule = ResidencyRule(
            tenant_id=tenant_id,
            region=region,
            allowed_regions=allowed_regions or [region],
            block_cross_border=block_cross_border,
        )
        self.rules[tenant_id] = rule
        logger.info("data residency rule set: tenant=%s region=%s", tenant_id, region.value)
        return rule

    def remove_rule(self, tenant_id: str) -> bool:
        """移除租户驻留规则."""
        if tenant_id in self.rules:
            del self.rules[tenant_id]
            return True
        return False

    def is_allowed(self, tenant_id: str, target_region: DataRegion) -> bool:
        """检查数据是否允许存储到目标区域."""
        if not self.enabled:
            return True
        rule = self.rules.get(tenant_id)
        if rule is None:
            return True  # 无规则 = 不限制
        if not rule.block_cross_border:
            return True
        return target_region in rule.allowed_regions

    def validate_storage_target(self, tenant_id: str, storage_region: DataRegion) -> None:
        """验证存储目标是否合规, 不合规则抛出异常."""
        if not self.is_allowed(tenant_id, storage_region):
            rule = self.rules.get(tenant_id)
            raise DataResidencyViolation(
                tenant_id=tenant_id,
                target_region=storage_region,
                allowed_regions=rule.allowed_regions if rule else [],
            )


class DataResidencyViolation(Exception):
    """数据驻留违规."""

    def __init__(self, tenant_id: str, target_region: DataRegion,
                 allowed_regions: list[DataRegion]):
        self.tenant_id = tenant_id
        self.target_region = target_region
        self.allowed_regions = allowed_regions
        super().__init__(
            f"Data residency violation: tenant={tenant_id} "
            f"cannot store in {target_region.value}, "
            f"allowed: {[r.value for r in allowed_regions]}"
        )


# ─── 单例 ─────────────────────────────────────────────────────────────────────

_residency_config: DataResidencyConfig | None = None


def get_residency_config() -> DataResidencyConfig:
    """获取数据驻留配置单例."""
    global _residency_config
    if _residency_config is None:
        _residency_config = DataResidencyConfig()
        # 从 settings 加载
        try:
            from backend.app.settings import get_settings
            settings = get_settings()
            _residency_config.enabled = getattr(settings, "gdpr_residency_enabled", False)
            default_region = getattr(settings, "gdpr_default_region", "global")
            _residency_config.default_region = DataRegion(default_region)
        except Exception:
            pass
    return _residency_config


def reset_residency_config() -> None:
    """重置配置 (测试用)."""
    global _residency_config
    _residency_config = None
