"""Compliance Reporting module.

Implements:
- GDPR compliance (data subject rights, data protection)
- HIPAA compliance (medical data protection)
- SOC2 compliance (security, availability, confidentiality)
- Audit report generation
- Compliance dashboard
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ComplianceFramework(StrEnum):
    """Compliance frameworks."""
    GDPR = "gdpr"
    HIPAA = "hipaa"
    SOC2 = "soc2"
    PCI_DSS = "pci_dss"
    ISO27001 = "iso27001"


class ComplianceStatus(StrEnum):
    """Compliance status."""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class AuditFinding(BaseModel):
    """Audit finding."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    description: str
    severity: str  # low, medium, high, critical
    framework: ComplianceFramework
    finding_date: datetime = Field(default_factory=lambda: datetime.now(UTC))
    remediation_date: datetime | None = None
    remediation_plan: str = ""
    status: str = "open"  # open, in_progress, resolved


class GDPRCompliance(BaseModel):
    """GDPR compliance tracking."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    organization_id: str
    data_processing_agreement: bool = False
    privacy_policy_updated: bool = False
    dpia_completed: bool = False  # Data Protection Impact Assessment
    data_retention_policy: bool = False
    right_to_access_implemented: bool = False
    right_to_erasure_implemented: bool = False
    right_to_rectification_implemented: bool = False
    data_portability_implemented: bool = False
    consent_management_implemented: bool = False
    breach_notification_process: bool = False
    dpo_appointed: bool = False  # Data Protection Officer
    last_audit_date: datetime | None = None
    next_audit_date: datetime | None = None
    findings: list[AuditFinding] = Field(default_factory=list)
    status: ComplianceStatus = ComplianceStatus.UNKNOWN
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class HIPAACompliance(BaseModel):
    """HIPAA compliance tracking."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    organization_id: str
    phi_encryption_enabled: bool = False
    access_controls_implemented: bool = False
    audit_controls_implemented: bool = False
    integrity_controls_implemented: bool = False
    transmission_security_implemented: bool = False
    breach_notification_process: bool = False
    business_associate_agreements: bool = False
    workforce_training_completed: bool = False
    security_risk_analysis_completed: bool = False
    incident_response_plan: bool = False
    last_audit_date: datetime | None = None
    next_audit_date: datetime | None = None
    findings: list[AuditFinding] = Field(default_factory=list)
    status: ComplianceStatus = ComplianceStatus.UNKNOWN
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SOC2Compliance(BaseModel):
    """SOC2 compliance tracking."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    organization_id: str
    trust_service_criteria: dict[str, bool] = Field(default_factory=dict)
    # CC (Common Criteria) controls
    cc_controls_implemented: dict[str, bool] = Field(default_factory=dict)
    security_controls_tested: bool = False
    availability_controls_tested: bool = False
    confidentiality_controls_tested: bool = False
    integrity_controls_tested: bool = False
    privacy_controls_tested: bool = False
    last_audit_date: datetime | None = None
    next_audit_date: datetime | None = None
    audit_report_available: bool = False
    findings: list[AuditFinding] = Field(default_factory=list)
    status: ComplianceStatus = ComplianceStatus.UNKNOWN
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ComplianceReport(BaseModel):
    """Compliance report."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    organization_id: str
    framework: ComplianceFramework
    report_date: datetime = Field(default_factory=lambda: datetime.now(UTC))
    period_start: datetime
    period_end: datetime
    status: ComplianceStatus
    findings: list[AuditFinding] = Field(default_factory=list)
    remediation_items: list[str] = Field(default_factory=list)
    compliance_score: float = 0.0  # 0-100
    executive_summary: str = ""
    detailed_findings: str = ""
    recommendations: list[str] = Field(default_factory=list)
    generated_by: str = ""
    approved_by: str | None = None
    approved_at: datetime | None = None


class DataSubjectRequest(BaseModel):
    """Data subject request (GDPR)."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    request_type: str  # access, erasure, rectification, portability, objection
    subject_id: str
    requested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    due_date: datetime
    status: str = "pending"  # pending, in_progress, completed, denied
    response_date: datetime | None = None
    data_provided: bool = False
    notes: str = ""


class ComplianceReportingEngine:
    """Compliance reporting engine."""

    def __init__(self):
        self.gdpr_compliance: dict[str, GDPRCompliance] = {}
        self.hipaa_compliance: dict[str, HIPAACompliance] = {}
        self.soc2_compliance: dict[str, SOC2Compliance] = {}
        self.reports: dict[str, ComplianceReport] = {}
        self.data_subject_requests: dict[str, DataSubjectRequest] = {}
        self.audit_findings: list[AuditFinding] = []

    def initialize_gdpr_compliance(self, organization_id: str) -> GDPRCompliance:
        """Initialize GDPR compliance tracking."""
        compliance = GDPRCompliance(organization_id=organization_id)
        self.gdpr_compliance[organization_id] = compliance
        return compliance

    def initialize_hipaa_compliance(self, organization_id: str) -> HIPAACompliance:
        """Initialize HIPAA compliance tracking."""
        compliance = HIPAACompliance(organization_id=organization_id)
        self.hipaa_compliance[organization_id] = compliance
        return compliance

    def initialize_soc2_compliance(self, organization_id: str) -> SOC2Compliance:
        """Initialize SOC2 compliance tracking."""
        compliance = SOC2Compliance(organization_id=organization_id)
        self.soc2_compliance[organization_id] = compliance
        return compliance

    def update_gdpr_compliance(self, organization_id: str,
                              **kwargs) -> GDPRCompliance:
        """Update GDPR compliance status."""
        if organization_id not in self.gdpr_compliance:
            self.initialize_gdpr_compliance(organization_id)

        compliance = self.gdpr_compliance[organization_id]
        for key, value in kwargs.items():
            if hasattr(compliance, key):
                setattr(compliance, key, value)

        compliance.updated_at = datetime.now(UTC)
        self._update_compliance_status(compliance)
        return compliance

    def update_hipaa_compliance(self, organization_id: str,
                               **kwargs) -> HIPAACompliance:
        """Update HIPAA compliance status."""
        if organization_id not in self.hipaa_compliance:
            self.initialize_hipaa_compliance(organization_id)

        compliance = self.hipaa_compliance[organization_id]
        for key, value in kwargs.items():
            if hasattr(compliance, key):
                setattr(compliance, key, value)

        compliance.updated_at = datetime.now(UTC)
        self._update_compliance_status(compliance)
        return compliance

    def update_soc2_compliance(self, organization_id: str,
                              **kwargs) -> SOC2Compliance:
        """Update SOC2 compliance status."""
        if organization_id not in self.soc2_compliance:
            self.initialize_soc2_compliance(organization_id)

        compliance = self.soc2_compliance[organization_id]
        for key, value in kwargs.items():
            if hasattr(compliance, key):
                setattr(compliance, key, value)

        compliance.updated_at = datetime.now(UTC)
        self._update_compliance_status(compliance)
        return compliance

    def _update_compliance_status(self, compliance: Any) -> None:
        """Update compliance status based on controls."""
        # Count implemented controls
        bool_fields = [v for v in compliance.__dict__.values() if isinstance(v, bool)]
        if not bool_fields:
            compliance.status = ComplianceStatus.UNKNOWN
            return

        implemented = sum(1 for v in bool_fields if v)
        total = len(bool_fields)
        ratio = implemented / total

        if ratio == 1.0:
            compliance.status = ComplianceStatus.COMPLIANT
        elif ratio >= 0.8:
            compliance.status = ComplianceStatus.PARTIAL
        else:
            compliance.status = ComplianceStatus.NON_COMPLIANT

    def add_audit_finding(self, framework: ComplianceFramework,
                         title: str, description: str,
                         severity: str = "medium") -> AuditFinding:
        """Add audit finding."""
        finding = AuditFinding(
            title=title,
            description=description,
            severity=severity,
            framework=framework
        )
        self.audit_findings.append(finding)
        return finding

    def create_data_subject_request(self, request_type: str,
                                   subject_id: str) -> DataSubjectRequest:
        """Create data subject request (GDPR)."""
        # GDPR requires response within 30 days
        due_date = datetime.now(UTC) + timedelta(days=30)

        request = DataSubjectRequest(
            request_type=request_type,
            subject_id=subject_id,
            due_date=due_date
        )
        self.data_subject_requests[request.id] = request
        return request

    def complete_data_subject_request(self, request_id: str,
                                     data_provided: bool = False) -> DataSubjectRequest:
        """Complete data subject request."""
        if request_id not in self.data_subject_requests:
            raise ValueError(f"Request {request_id} not found")

        request = self.data_subject_requests[request_id]
        request.status = "completed"
        request.response_date = datetime.now(UTC)
        request.data_provided = data_provided
        return request

    def generate_compliance_report(self, organization_id: str,
                                  framework: ComplianceFramework,
                                  period_days: int = 90) -> ComplianceReport:
        """Generate compliance report."""
        period_start = datetime.now(UTC) - timedelta(days=period_days)
        period_end = datetime.now(UTC)

        # Get compliance data
        if framework == ComplianceFramework.GDPR:
            compliance = self.gdpr_compliance.get(organization_id)
        elif framework == ComplianceFramework.HIPAA:
            compliance = self.hipaa_compliance.get(organization_id)
        elif framework == ComplianceFramework.SOC2:
            compliance = self.soc2_compliance.get(organization_id)
        else:
            compliance = None

        # Get findings for period
        findings = [f for f in self.audit_findings
                   if f.framework == framework and
                   period_start <= f.finding_date <= period_end]

        # Calculate compliance score
        compliance_score = self._calculate_compliance_score(compliance, findings)

        report = ComplianceReport(
            organization_id=organization_id,
            framework=framework,
            period_start=period_start,
            period_end=period_end,
            status=compliance.status if compliance else ComplianceStatus.UNKNOWN,
            findings=findings,
            compliance_score=compliance_score,
            executive_summary=self._generate_executive_summary(framework, compliance_score),
            recommendations=self._generate_recommendations(framework, findings)
        )

        self.reports[report.id] = report
        return report

    def _calculate_compliance_score(self, compliance: Any,
                                   findings: list[AuditFinding]) -> float:
        """Calculate compliance score."""
        if compliance is None:
            return 0.0

        # Base score from compliance status
        status_scores = {
            ComplianceStatus.COMPLIANT: 100.0,
            ComplianceStatus.PARTIAL: 70.0,
            ComplianceStatus.NON_COMPLIANT: 30.0,
            ComplianceStatus.UNKNOWN: 50.0
        }
        base_score = status_scores.get(compliance.status, 50.0)

        # Deduct for findings
        critical_findings = sum(1 for f in findings if f.severity == "critical")
        high_findings = sum(1 for f in findings if f.severity == "high")

        deduction = (critical_findings * 10) + (high_findings * 5)
        final_score = max(0.0, base_score - deduction)

        return min(100.0, final_score)

    def _generate_executive_summary(self, framework: ComplianceFramework,
                                   score: float) -> str:
        """Generate executive summary."""
        status = "compliant" if score >= 80 else "needs improvement"
        return f"Organization is {status} with {framework.value} requirements. Compliance score: {score:.1f}%"

    def _generate_recommendations(self, framework: ComplianceFramework,
                                 findings: list[AuditFinding]) -> list[str]:
        """Generate recommendations."""
        recommendations = []

        for finding in findings:
            if finding.severity in ["critical", "high"]:
                recommendations.append(f"Address {finding.severity} finding: {finding.title}")

        if framework == ComplianceFramework.GDPR:
            recommendations.append("Ensure Data Protection Officer is appointed")
            recommendations.append("Conduct regular Data Protection Impact Assessments")

        elif framework == ComplianceFramework.HIPAA:
            recommendations.append("Conduct annual security risk analysis")
            recommendations.append("Implement workforce security training")

        elif framework == ComplianceFramework.SOC2:
            recommendations.append("Perform annual SOC2 audit")
            recommendations.append("Implement continuous monitoring")

        return recommendations

    def get_compliance_dashboard(self, organization_id: str) -> dict[str, Any]:
        """Get compliance dashboard data."""
        gdpr = self.gdpr_compliance.get(organization_id)
        hipaa = self.hipaa_compliance.get(organization_id)
        soc2 = self.soc2_compliance.get(organization_id)

        return {
            "gdpr": {
                "status": gdpr.status if gdpr else ComplianceStatus.UNKNOWN,
                "last_audit": gdpr.last_audit_date if gdpr else None,
                "findings_count": len(gdpr.findings) if gdpr else 0
            },
            "hipaa": {
                "status": hipaa.status if hipaa else ComplianceStatus.UNKNOWN,
                "last_audit": hipaa.last_audit_date if hipaa else None,
                "findings_count": len(hipaa.findings) if hipaa else 0
            },
            "soc2": {
                "status": soc2.status if soc2 else ComplianceStatus.UNKNOWN,
                "last_audit": soc2.last_audit_date if soc2 else None,
                "findings_count": len(soc2.findings) if soc2 else 0
            },
            "pending_data_subject_requests": sum(
                1 for r in self.data_subject_requests.values()
                if r.status == "pending"
            ),
            "open_findings": sum(1 for f in self.audit_findings if f.status == "open")
        }

    def get_overdue_data_subject_requests(self) -> list[DataSubjectRequest]:
        """Get overdue data subject requests."""
        now = datetime.now(UTC)
        return [r for r in self.data_subject_requests.values()
                if r.status != "completed" and r.due_date < now]

    def export_compliance_report(self, report_id: str) -> dict[str, Any]:
        """Export compliance report as dictionary."""
        if report_id not in self.reports:
            raise ValueError(f"Report {report_id} not found")

        report = self.reports[report_id]
        return {
            "id": report.id,
            "organization_id": report.organization_id,
            "framework": report.framework.value,
            "report_date": report.report_date.isoformat(),
            "period": {
                "start": report.period_start.isoformat(),
                "end": report.period_end.isoformat()
            },
            "status": report.status.value,
            "compliance_score": report.compliance_score,
            "findings_count": len(report.findings),
            "executive_summary": report.executive_summary,
            "recommendations": report.recommendations
        }
