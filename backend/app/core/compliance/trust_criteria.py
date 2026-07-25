"""SOC 2 Trust Services Criteria 映射 — 控制点到代码实现的追溯矩阵。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class CriteriaMapping:
    """单个 TSC 控制点的实现映射。"""

    criteria_id: str
    criteria_name: str
    category: str  # CC6/CC7/CC8/CC9/P
    description: str
    implementation: str  # 代码实现位置
    evidence_source: str  # 证据来源
    status: str = "implemented"  # implemented | partial | planned | n/a
    notes: str = ""


class TrustServicesCriteria:
    """SOC 2 Trust Services Criteria 完整映射。

    基于 AICPA SOC 2 Type I 的五大信任服务类别：
    - CC6: Logical and Physical Access Controls (安全)
    - CC7: System Operations (可用性)
    - CC8: Change Management (处理完整性)
    - CC9: Risk Mitigation (保密性)
    - P: Privacy (隐私)
    """

    def __init__(self):
        self._mappings: list[CriteriaMapping] = self._build_default_mappings()

    def get_all(self) -> list[CriteriaMapping]:
        return list(self._mappings)

    def get_by_category(self, category: str) -> list[CriteriaMapping]:
        return [m for m in self._mappings if m.category == category]

    def get_status_summary(self) -> dict[str, int]:
        summary: dict[str, int] = {}
        for m in self._mappings:
            summary[m.status] = summary.get(m.status, 0) + 1
        return summary

    def get_compliance_score(self) -> float:
        """计算合规得分 (implemented=1, partial=0.5, 其他=0)。"""
        if not self._mappings:
            return 0.0
        score = 0.0
        for m in self._mappings:
            if m.status == "implemented":
                score += 1.0
            elif m.status == "partial":
                score += 0.5
        return round(score / len(self._mappings) * 100, 1)

    def to_matrix(self) -> list[dict[str, Any]]:
        """输出追溯矩阵（供审计师使用）。"""
        return [
            {
                "criteria_id": m.criteria_id,
                "criteria_name": m.criteria_name,
                "category": m.category,
                "description": m.description,
                "implementation": m.implementation,
                "evidence_source": m.evidence_source,
                "status": m.status,
                "notes": m.notes,
            }
            for m in self._mappings
        ]

    @staticmethod
    def _build_default_mappings() -> list[CriteriaMapping]:
        return [
            # --- CC6: 访问控制 ---
            CriteriaMapping(
                "CC6.1", "Logical Access Security", "CC6",
                "Implement logical access security software, infrastructure, and architectures",
                "backend/app/core/sso/ (OIDC+SAML), backend/app/api/enterprise_sso.py",
                "SSO configuration, authentication logs",
            ),
            CriteriaMapping(
                "CC6.2", "User Authentication", "CC6",
                "Authenticate users through defined mechanisms",
                "backend/app/core/sso/oidc_provider.py, saml_provider.py",
                "Authentication flow tests, token validation",
            ),
            CriteriaMapping(
                "CC6.3", "Access Authorization", "CC6",
                "Authorize access based on defined roles and permissions",
                "backend/app/core/tools.py (ToolRegistry risk levels + approval gates)",
                "RBAC configuration, approval records",
            ),
            CriteriaMapping(
                "CC6.4", "Tenant Isolation", "CC6",
                "Isolate tenant data and prevent cross-tenant access",
                "backend/app/core/tenant_isolation.py, middleware enforcement",
                "Isolation tests, cross-tenant query rejection logs",
            ),
            CriteriaMapping(
                "CC6.5", "User Provisioning (SCIM)", "CC6",
                "Manage user lifecycle through automated provisioning",
                "backend/app/api/scim.py (SCIM 2.0 endpoints)",
                "SCIM operation logs, provisioning records",
            ),
            CriteriaMapping(
                "CC6.6", "Encryption at Rest", "CC6",
                "Protect data at rest using encryption",
                "backend/app/core/kms/ (AES-256 via Fernet, key rotation)",
                "KMS configuration, key rotation logs",
            ),
            CriteriaMapping(
                "CC6.7", "Encryption in Transit", "CC6",
                "Protect data in transit using TLS",
                "deployment/ TLS termination config, docker-compose TLS settings",
                "TLS configuration, certificate management",
            ),
            # --- CC7: 系统运维 ---
            CriteriaMapping(
                "CC7.1", "System Monitoring", "CC7",
                "Monitor system components and operations",
                "monitoring/ (Prometheus + Grafana), /ready health endpoint",
                "Monitoring dashboards, alert rules",
            ),
            CriteriaMapping(
                "CC7.2", "Incident Detection", "CC7",
                "Detect and respond to security incidents",
                "backend/app/core/compliance/incident_response.py",
                "Incident response procedures, drill records",
            ),
            CriteriaMapping(
                "CC7.3", "Backup and Recovery", "CC7",
                "Maintain data backup and recovery procedures",
                "deployment/backup/, disaster-recovery/",
                "Backup schedules, recovery test records",
            ),
            CriteriaMapping(
                "CC7.4", "Audit Logging", "CC7",
                "Maintain tamper-evident audit trails",
                "backend/app/core/audit.py (HMAC chain), audit_enhanced/ (SIEM export)",
                "Audit log integrity verification, export records",
            ),
            # --- CC8: 变更管理 ---
            CriteriaMapping(
                "CC8.1", "Change Management Process", "CC8",
                "Manage changes through defined approval and testing processes",
                "backend/app/core/compliance/change_management.py, .github/workflows/",
                "Change records, CI pipeline logs",
            ),
            CriteriaMapping(
                "CC8.2", "Code Review", "CC8",
                "Require peer review before code deployment",
                ".github/workflows/branch-protection.yml",
                "PR review records, branch protection config",
            ),
            CriteriaMapping(
                "CC8.3", "Automated Testing", "CC8",
                "Execute automated tests as part of change management",
                ".github/workflows/ci.yml, tests/",
                "Test execution reports, coverage metrics",
            ),
            CriteriaMapping(
                "CC8.4", "Dependency Management", "CC8",
                "Monitor and manage third-party dependencies",
                ".github/workflows/security.yml (pip-audit + npm audit + SBOM)",
                "Dependency scan reports, SBOM",
            ),
            # --- CC9: 风险缓解 ---
            CriteriaMapping(
                "CC9.1", "Risk Assessment", "CC9",
                "Identify and assess risks to the system",
                "commercial_audit/ (gap analysis), SECURITY.md",
                "Risk assessment documents, audit reports",
            ),
            CriteriaMapping(
                "CC9.2", "Vulnerability Management", "CC9",
                "Identify and remediate vulnerabilities",
                ".github/workflows/security.yml (Bandit + Semgrep + TruffleHog)",
                "Vulnerability scan reports, remediation records",
            ),
            CriteriaMapping(
                "CC9.3", "Data Retention", "CC9",
                "Manage data retention and disposal",
                "backend/app/core/audit_enhanced/retention.py (WORM semantics)",
                "Retention policy configuration, disposal records",
            ),
            # --- P: 隐私 ---
            CriteriaMapping(
                "P1.1", "Privacy Notice", "P",
                "Provide notice about privacy practices",
                "SECURITY.md, data governance documentation",
                "Privacy notice, consent records",
                status="partial",
                notes="GDPR DPA template needed for enterprise customers",
            ),
            CriteriaMapping(
                "P1.2", "Data Minimization", "P",
                "Collect only necessary personal data",
                "backend/app/core/data_governance/ (PII classification)",
                "Data inventory, minimization controls",
                status="partial",
                notes="PII cascade deletion implemented, data inventory pending",
            ),
        ]
