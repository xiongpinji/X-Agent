"""P2-03: GDPR 数据主体权利服务.

实现 GDPR 合规核心能力:
- 删除权 (Right to Erasure / Art. 17): 级联删除用户所有数据
- 导出权 (Right to Data Portability / Art. 20): 导出用户所有数据
- PII 检测与脱敏
- 数据驻留配置

级联删除覆盖:
- Memory items (按 user_id/tenant_id)
- Run records (按 user_id)
- Checkpoints (按 user_id)
- Tool execution records (按 user_id)
- Audit logs (按 actor_id)
- Sessions (按 user_id)
- Approvals (按 user_id)
- Collaboration data (按 user_id)
"""

from backend.app.core.gdpr.pii import PIIDetector, PIIMasker, PIIType
from backend.app.core.gdpr.residency import DataResidencyConfig, get_residency_config
from backend.app.core.gdpr.service import DataSubjectRightsService, DeletionResult, ExportResult

__all__ = [
    "DataResidencyConfig",
    "DataSubjectRightsService",
    "DeletionResult",
    "ExportResult",
    "PIIDetector",
    "PIIMasker",
    "PIIType",
    "get_residency_config",
]
