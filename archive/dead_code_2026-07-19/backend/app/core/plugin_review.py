"""Plugin Review and Approval System

Provides:
- Security scanning
- Code review workflow
- Approval process
- Risk assessment
- Compliance checking
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ReviewStatus(StrEnum):
    """Review status"""
    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"


class RiskLevel(StrEnum):
    """Risk assessment level"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityIssue(BaseModel):
    """Security issue found during review"""
    issue_id: str = Field(default_factory=lambda: str(uuid4()))
    severity: str = Field(..., description="Issue severity: low, medium, high, critical")
    category: str = Field(..., description="Issue category")
    description: str = Field(..., description="Issue description")
    location: Optional[str] = Field(None, description="File/line location")
    recommendation: str = Field(..., description="Recommended fix")
    resolved: bool = Field(False, description="Whether issue is resolved")


class CodeReviewComment(BaseModel):
    """Code review comment"""
    comment_id: str = Field(default_factory=lambda: str(uuid4()))
    reviewer_id: str = Field(..., description="Reviewer ID")
    file_path: str = Field(..., description="File path")
    line_number: Optional[int] = Field(None, description="Line number")
    comment: str = Field(..., description="Comment text")
    severity: str = Field("info", description="Comment severity")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PluginReview(BaseModel):
    """Plugin review record"""
    review_id: str = Field(default_factory=lambda: str(uuid4()))
    plugin_id: str = Field(..., description="Plugin ID")
    plugin_version: str = Field(..., description="Plugin version")
    status: ReviewStatus = Field(ReviewStatus.PENDING)
    risk_level: RiskLevel = Field(RiskLevel.MEDIUM)

    # Security assessment
    security_issues: list[SecurityIssue] = Field(default_factory=list)
    security_score: float = Field(0.0, ge=0.0, le=100.0)

    # Code review
    code_review_comments: list[CodeReviewComment] = Field(default_factory=list)
    code_quality_score: float = Field(0.0, ge=0.0, le=100.0)

    # Compliance
    compliance_checks: dict[str, bool] = Field(default_factory=dict)
    compliance_score: float = Field(0.0, ge=0.0, le=100.0)

    # Overall assessment
    overall_score: float = Field(0.0, ge=0.0, le=100.0)
    approved_by: Optional[str] = Field(None, description="Approver ID")
    rejection_reason: Optional[str] = Field(None, description="Rejection reason")

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: Optional[datetime] = Field(None, description="Review completion time")


class SecurityScanner:
    """Scan plugins for security issues"""

    def __init__(self):
        self.dangerous_patterns = [
            ("eval", "Use of eval() is dangerous"),
            ("exec", "Use of exec() is dangerous"),
            ("__import__", "Dynamic imports can be dangerous"),
            ("os.system", "Direct system calls are dangerous"),
            ("subprocess.call", "Subprocess calls should be restricted"),
            ("open(", "File operations should be restricted"),
            ("socket", "Network operations should be restricted"),
        ]

    def scan_plugin(self, plugin_path: Path) -> list[SecurityIssue]:
        """Scan plugin for security issues"""
        issues = []

        # Scan Python files
        for py_file in plugin_path.rglob("*.py"):
            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    issues.extend(self._scan_file(content, str(py_file)))
            except Exception as e:
                logger.warning(f"Failed to scan {py_file}: {e}")

        return issues

    def _scan_file(self, content: str, file_path: str) -> list[SecurityIssue]:
        """Scan single file for issues"""
        issues = []

        for line_num, line in enumerate(content.split("\n"), 1):
            for pattern, description in self.dangerous_patterns:
                if pattern in line and not line.strip().startswith("#"):
                    issues.append(
                        SecurityIssue(
                            severity="high",
                            category="dangerous_function",
                            description=description,
                            location=f"{file_path}:{line_num}",
                            recommendation=f"Avoid using {pattern}. Use safer alternatives.",
                        )
                    )

        return issues


class ComplianceChecker:
    """Check plugin compliance with requirements"""

    def __init__(self):
        self.required_files = ["manifest.json", "README.md"]
        self.required_fields = ["name", "version", "author", "description"]

    def check_compliance(self, plugin_path: Path, manifest: dict) -> dict[str, bool]:
        """Check plugin compliance"""
        checks = {}

        # Check required files
        for required_file in self.required_files:
            checks[f"has_{required_file}"] = (plugin_path / required_file).exists()

        # Check manifest fields
        for field in self.required_fields:
            checks[f"manifest_has_{field}"] = field in manifest

        # Check version format
        version = manifest.get("version", "")
        checks["valid_version_format"] = self._is_valid_version(version)

        # Check license
        checks["has_license"] = "license" in manifest

        # Check documentation
        readme_path = plugin_path / "README.md"
        checks["has_documentation"] = readme_path.exists()
        if readme_path.exists():
            with open(readme_path) as f:
                content = f.read()
                checks["documentation_length"] = len(content) > 100

        return checks

    @staticmethod
    def _is_valid_version(version: str) -> bool:
        """Check if version is valid semantic version"""
        try:
            parts = version.split(".")
            if len(parts) < 2:
                return False
            for part in parts:
                int(part)
            return True
        except (ValueError, AttributeError):
            return False


class CodeQualityAnalyzer:
    """Analyze code quality"""

    def analyze_plugin(self, plugin_path: Path) -> tuple[float, list[str]]:
        """Analyze plugin code quality"""
        issues = []
        score = 100.0

        # Count Python files
        py_files = list(plugin_path.rglob("*.py"))
        if not py_files:
            issues.append("No Python files found")
            score -= 20

        # Check file sizes
        for py_file in py_files:
            size = py_file.stat().st_size
            if size > 10000:  # 10KB
                issues.append(f"Large file: {py_file.name} ({size} bytes)")
                score -= 5

        # Check for common issues
        for py_file in py_files:
            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.read()

                    # Check for missing docstrings
                    if "def " in content and '"""' not in content:
                        issues.append(f"Missing docstrings in {py_file.name}")
                        score -= 5

                    # Check for long lines
                    for line_num, line in enumerate(content.split("\n"), 1):
                        if len(line) > 120:
                            issues.append(f"Long line in {py_file.name}:{line_num}")
                            score -= 2

            except Exception as e:
                logger.warning(f"Failed to analyze {py_file}: {e}")

        return max(0.0, score), issues


class PluginReviewManager:
    """Manage plugin reviews"""

    def __init__(self, storage_path: Optional[str | Path] = None):
        self.storage_path = Path(storage_path) if storage_path else Path("./plugin_reviews")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.security_scanner = SecurityScanner()
        self.compliance_checker = ComplianceChecker()
        self.code_analyzer = CodeQualityAnalyzer()
        self._reviews: dict[str, PluginReview] = {}
        self._load_reviews()

    def _load_reviews(self) -> None:
        """Load reviews from storage"""
        reviews_file = self.storage_path / "reviews.json"
        if reviews_file.exists():
            try:
                with open(reviews_file) as f:
                    data = json.load(f)
                    for review_data in data.get("reviews", []):
                        review = PluginReview(**review_data)
                        self._reviews[review.review_id] = review
                logger.info(f"Loaded {len(self._reviews)} reviews")
            except Exception as e:
                logger.error(f"Failed to load reviews: {e}")

    def _save_reviews(self) -> None:
        """Save reviews to storage"""
        reviews_file = self.storage_path / "reviews.json"
        try:
            with open(reviews_file, "w") as f:
                data = {
                    "reviews": [
                        json.loads(r.model_dump_json(default=str))
                        for r in self._reviews.values()
                    ]
                }
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save reviews: {e}")

    def create_review(
        self,
        plugin_id: str,
        plugin_version: str,
        plugin_path: Path
    ) -> PluginReview:
        """Create new review"""
        review = PluginReview(
            plugin_id=plugin_id,
            plugin_version=plugin_version,
            status=ReviewStatus.IN_REVIEW
        )

        # Run security scan
        security_issues = self.security_scanner.scan_plugin(plugin_path)
        review.security_issues = security_issues
        review.security_score = max(0.0, 100.0 - len(security_issues) * 10)

        # Check compliance
        try:
            with open(plugin_path / "manifest.json") as f:
                manifest = json.load(f)
        except Exception:
            manifest = {}

        compliance_checks = self.compliance_checker.check_compliance(plugin_path, manifest)
        review.compliance_checks = compliance_checks
        passed = sum(1 for v in compliance_checks.values() if v)
        review.compliance_score = (passed / len(compliance_checks) * 100) if compliance_checks else 0.0

        # Analyze code quality
        code_score, code_issues = self.code_analyzer.analyze_plugin(plugin_path)
        review.code_quality_score = code_score

        # Calculate overall score
        review.overall_score = (
            review.security_score * 0.4 +
            review.code_quality_score * 0.3 +
            review.compliance_score * 0.3
        )

        # Determine risk level
        if review.overall_score >= 80:
            review.risk_level = RiskLevel.LOW
        elif review.overall_score >= 60:
            review.risk_level = RiskLevel.MEDIUM
        elif review.overall_score >= 40:
            review.risk_level = RiskLevel.HIGH
        else:
            review.risk_level = RiskLevel.CRITICAL

        self._reviews[review.review_id] = review
        self._save_reviews()

        logger.info(f"Review created: {review.review_id} for {plugin_id}")
        return review

    def add_code_review_comment(
        self,
        review_id: str,
        reviewer_id: str,
        file_path: str,
        comment: str,
        line_number: Optional[int] = None,
        severity: str = "info"
    ) -> Optional[CodeReviewComment]:
        """Add code review comment"""
        review = self._reviews.get(review_id)
        if not review:
            return None

        comment_obj = CodeReviewComment(
            reviewer_id=reviewer_id,
            file_path=file_path,
            line_number=line_number,
            comment=comment,
            severity=severity
        )

        review.code_review_comments.append(comment_obj)
        review.updated_at = datetime.now(UTC)
        self._save_reviews()

        return comment_obj

    def approve_review(
        self,
        review_id: str,
        approver_id: str
    ) -> Optional[PluginReview]:
        """Approve plugin review"""
        review = self._reviews.get(review_id)
        if not review:
            return None

        review.status = ReviewStatus.APPROVED
        review.approved_by = approver_id
        review.completed_at = datetime.now(UTC)
        review.updated_at = datetime.now(UTC)
        self._save_reviews()

        logger.info(f"Review approved: {review_id} by {approver_id}")
        return review

    def reject_review(
        self,
        review_id: str,
        reason: str
    ) -> Optional[PluginReview]:
        """Reject plugin review"""
        review = self._reviews.get(review_id)
        if not review:
            return None

        review.status = ReviewStatus.REJECTED
        review.rejection_reason = reason
        review.completed_at = datetime.now(UTC)
        review.updated_at = datetime.now(UTC)
        self._save_reviews()

        logger.info(f"Review rejected: {review_id}")
        return review

    def get_review(self, review_id: str) -> Optional[PluginReview]:
        """Get review"""
        return self._reviews.get(review_id)

    def list_reviews(
        self,
        plugin_id: Optional[str] = None,
        status: Optional[ReviewStatus] = None
    ) -> list[PluginReview]:
        """List reviews"""
        reviews = list(self._reviews.values())

        if plugin_id:
            reviews = [r for r in reviews if r.plugin_id == plugin_id]

        if status:
            reviews = [r for r in reviews if r.status == status]

        return sorted(reviews, key=lambda r: r.created_at, reverse=True)


# Global instance
review_manager = PluginReviewManager()
