"""Data Governance module for data classification, protection, and compliance.

Implements:
- Data classification (public, internal, confidential, restricted)
- Sensitive information detection and protection
- Data lifecycle management
- Data quality monitoring
- Compliance checking
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class DataClassification(StrEnum):
    """Data classification levels."""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class SensitiveDataType(StrEnum):
    """Types of sensitive data."""
    PII = "pii"  # Personally Identifiable Information
    PHI = "phi"  # Protected Health Information
    PCI = "pci"  # Payment Card Information
    API_KEY = "api_key"
    PASSWORD = "password"
    TOKEN = "token"
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    DATABASE_CONNECTION = "database_connection"


class DataLifecycleStage(StrEnum):
    """Data lifecycle stages."""
    CREATION = "creation"
    PROCESSING = "processing"
    STORAGE = "storage"
    ARCHIVAL = "archival"
    DELETION = "deletion"


class ComplianceFramework(StrEnum):
    """Compliance frameworks."""
    GDPR = "gdpr"
    HIPAA = "hipaa"
    SOC2 = "soc2"
    PCI_DSS = "pci_dss"
    ISO27001 = "iso27001"


class SensitiveDataPattern(BaseModel):
    """Pattern for detecting sensitive data."""
    data_type: SensitiveDataType
    pattern: str  # Regex pattern
    description: str = ""
    severity: str = "high"  # low, medium, high, critical

    def detect(self, text: str) -> list[str]:
        """Detect sensitive data in text."""
        try:
            matches = re.findall(self.pattern, text, re.IGNORECASE)
            return matches
        except re.error:
            return []


class DataRecord(BaseModel):
    """Record of data with classification and metadata."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    classification: DataClassification
    owner_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_accessed_at: datetime | None = None
    retention_days: int = 365
    sensitive_data_types: list[SensitiveDataType] = Field(default_factory=list)
    encrypted: bool = False
    encryption_key_id: str | None = None
    lifecycle_stage: DataLifecycleStage = DataLifecycleStage.STORAGE
    compliance_frameworks: list[ComplianceFramework] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def should_be_deleted(self) -> bool:
        """Check if data should be deleted based on retention policy."""
        if self.lifecycle_stage == DataLifecycleStage.DELETION:
            return True
        age_days = (datetime.now(UTC) - self.created_at).days
        return age_days >= self.retention_days

    def is_sensitive(self) -> bool:
        """Check if data contains sensitive information."""
        return len(self.sensitive_data_types) > 0


class DataQualityMetric(BaseModel):
    """Data quality metric."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    data_record_id: str
    completeness: float = 0.0  # 0-100%
    accuracy: float = 0.0  # 0-100%
    consistency: float = 0.0  # 0-100%
    timeliness: float = 0.0  # 0-100%
    validity: float = 0.0  # 0-100%
    measured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def overall_score(self) -> float:
        """Calculate overall data quality score."""
        scores = [self.completeness, self.accuracy, self.consistency,
                 self.timeliness, self.validity]
        return sum(scores) / len(scores) if scores else 0.0


class ComplianceCheckResult(BaseModel):
    """Result of compliance check."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    data_record_id: str
    framework: ComplianceFramework
    passed: bool
    issues: list[str] = Field(default_factory=list)
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    next_check_at: datetime | None = None


class DataGovernanceEngine:
    """Data governance engine."""

    def __init__(self):
        self.data_records: dict[str, DataRecord] = {}
        self.quality_metrics: dict[str, list[DataQualityMetric]] = {}
        self.compliance_checks: dict[str, list[ComplianceCheckResult]] = {}
        self.sensitive_patterns: dict[SensitiveDataType, SensitiveDataPattern] = {}
        self._init_default_patterns()

    def _init_default_patterns(self) -> None:
        """Initialize default sensitive data patterns."""
        self.sensitive_patterns[SensitiveDataType.EMAIL] = SensitiveDataPattern(
            data_type=SensitiveDataType.EMAIL,
            pattern=r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            description="Email address pattern"
        )

        self.sensitive_patterns[SensitiveDataType.PHONE] = SensitiveDataPattern(
            data_type=SensitiveDataType.PHONE,
            pattern=r'\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b',
            description="Phone number pattern"
        )

        self.sensitive_patterns[SensitiveDataType.SSN] = SensitiveDataPattern(
            data_type=SensitiveDataType.SSN,
            pattern=r'\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0{4})\d{4}\b',
            description="Social Security Number pattern",
            severity="critical"
        )

        self.sensitive_patterns[SensitiveDataType.CREDIT_CARD] = SensitiveDataPattern(
            data_type=SensitiveDataType.CREDIT_CARD,
            pattern=r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
            description="Credit card number pattern",
            severity="critical"
        )

        self.sensitive_patterns[SensitiveDataType.API_KEY] = SensitiveDataPattern(
            data_type=SensitiveDataType.API_KEY,
            pattern=r'(?i)(api[_-]?key|apikey|api_secret|secret_key)\s*[:=]\s*[\'"]?([a-zA-Z0-9_\-]{20,})[\'"]?',
            description="API key pattern",
            severity="critical"
        )

        self.sensitive_patterns[SensitiveDataType.PASSWORD] = SensitiveDataPattern(
            data_type=SensitiveDataType.PASSWORD,
            pattern=r'(?i)(password|passwd|pwd)\s*[:=]\s*[\'"]?([^\s\'\"]+)[\'"]?',
            description="Password pattern",
            severity="critical"
        )

    def register_data(self, name: str, classification: DataClassification,
                     owner_id: str, retention_days: int = 365,
                     compliance_frameworks: list[ComplianceFramework] | None = None) -> DataRecord:
        """Register a data record."""
        record = DataRecord(
            name=name,
            classification=classification,
            owner_id=owner_id,
            retention_days=retention_days,
            compliance_frameworks=compliance_frameworks or []
        )
        self.data_records[record.id] = record
        return record

    def detect_sensitive_data(self, data_id: str, content: str) -> list[tuple[SensitiveDataType, list[str]]]:
        """Detect sensitive data in content."""
        if data_id not in self.data_records:
            raise ValueError(f"Data record {data_id} not found")

        record = self.data_records[data_id]
        detected = []

        for data_type, pattern in self.sensitive_patterns.items():
            matches = pattern.detect(content)
            if matches:
                detected.append((data_type, matches))
                if data_type not in record.sensitive_data_types:
                    record.sensitive_data_types.append(data_type)

        record.updated_at = datetime.now(UTC)
        return detected

    def mask_sensitive_data(self, content: str, mask_char: str = "*") -> str:
        """Mask sensitive data in content."""
        masked = content
        for pattern in self.sensitive_patterns.values():
            matches = pattern.detect(masked)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                masked = masked.replace(str(match), mask_char * len(str(match)))
        return masked

    def encrypt_data(self, data_id: str, encryption_key_id: str) -> None:
        """Mark data as encrypted."""
        if data_id not in self.data_records:
            raise ValueError(f"Data record {data_id} not found")
        record = self.data_records[data_id]
        record.encrypted = True
        record.encryption_key_id = encryption_key_id
        record.updated_at = datetime.now(UTC)

    def record_quality_metric(self, data_id: str, completeness: float,
                             accuracy: float, consistency: float,
                             timeliness: float, validity: float) -> DataQualityMetric:
        """Record data quality metric."""
        if data_id not in self.data_records:
            raise ValueError(f"Data record {data_id} not found")

        metric = DataQualityMetric(
            data_record_id=data_id,
            completeness=completeness,
            accuracy=accuracy,
            consistency=consistency,
            timeliness=timeliness,
            validity=validity
        )

        if data_id not in self.quality_metrics:
            self.quality_metrics[data_id] = []

        self.quality_metrics[data_id].append(metric)
        return metric

    def get_quality_metrics(self, data_id: str, days: int = 30) -> list[DataQualityMetric]:
        """Get quality metrics for data."""
        if data_id not in self.quality_metrics:
            return []

        cutoff = datetime.now(UTC) - timedelta(days=days)
        return [m for m in self.quality_metrics[data_id] if m.measured_at >= cutoff]

    def check_compliance(self, data_id: str, framework: ComplianceFramework) -> ComplianceCheckResult:
        """Check compliance for data."""
        if data_id not in self.data_records:
            raise ValueError(f"Data record {data_id} not found")

        record = self.data_records[data_id]
        issues = []

        # GDPR checks
        if framework == ComplianceFramework.GDPR:
            if record.classification == DataClassification.RESTRICTED and not record.encrypted:
                issues.append("GDPR: Restricted data must be encrypted")
            if record.sensitive_data_types and not record.encrypted:
                issues.append("GDPR: Data containing PII must be encrypted")

        # HIPAA checks
        elif framework == ComplianceFramework.HIPAA:
            if SensitiveDataType.PHI in record.sensitive_data_types and not record.encrypted:
                issues.append("HIPAA: PHI must be encrypted")
            if record.retention_days > 6 * 365:  # 6 years
                issues.append("HIPAA: PHI retention exceeds 6 years")

        # SOC2 checks
        elif framework == ComplianceFramework.SOC2:
            if record.classification in [DataClassification.CONFIDENTIAL, DataClassification.RESTRICTED]:
                if not record.encrypted:
                    issues.append("SOC2: Confidential data must be encrypted")

        result = ComplianceCheckResult(
            data_record_id=data_id,
            framework=framework,
            passed=len(issues) == 0,
            issues=issues,
            next_check_at=datetime.now(UTC) + timedelta(days=30)
        )

        if data_id not in self.compliance_checks:
            self.compliance_checks[data_id] = []

        self.compliance_checks[data_id].append(result)
        return result

    def get_compliance_status(self, data_id: str) -> dict[ComplianceFramework, bool]:
        """Get compliance status for data."""
        if data_id not in self.compliance_checks:
            return {}

        status = {}
        for result in self.compliance_checks[data_id]:
            status[result.framework] = result.passed

        return status

    def cleanup_expired_data(self) -> list[str]:
        """Clean up expired data records."""
        deleted_ids = []
        for data_id, record in list(self.data_records.items()):
            if record.should_be_deleted():
                record.lifecycle_stage = DataLifecycleStage.DELETION
                deleted_ids.append(data_id)

        return deleted_ids

    def get_data_by_classification(self, classification: DataClassification) -> list[DataRecord]:
        """Get all data records with specific classification."""
        return [r for r in self.data_records.values() if r.classification == classification]

    def get_sensitive_data_inventory(self) -> dict[SensitiveDataType, int]:
        """Get inventory of sensitive data types."""
        inventory = {}
        for record in self.data_records.values():
            for data_type in record.sensitive_data_types:
                inventory[data_type] = inventory.get(data_type, 0) + 1
        return inventory

    def hash_data(self, content: str) -> str:
        """Hash data for integrity verification."""
        return hashlib.sha256(content.encode()).hexdigest()
