"""
X-Agent 技能审核系统 - 完整的技能审核流程、安全检查、质量评估
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, UTC, timedelta
from enum import Enum
import json

logger = logging.getLogger(__name__)


class ReviewStatus(str, Enum):
    """审核状态"""
    PENDING = "pending"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"
    APPROVED_WITH_CONDITIONS = "approved_with_conditions"


class ReviewCategory(str, Enum):
    """审核类别"""
    SECURITY = "security"
    PERFORMANCE = "performance"
    FUNCTIONALITY = "functionality"
    DOCUMENTATION = "documentation"
    COMPATIBILITY = "compatibility"
    LICENSING = "licensing"


class SeverityLevel(str, Enum):
    """严重程度"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ReviewIssue:
    """审核问题"""
    issue_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    category: ReviewCategory = ReviewCategory.FUNCTIONALITY
    severity: SeverityLevel = SeverityLevel.WARNING
    title: str = ""
    description: str = ""
    recommendation: str = ""
    code_reference: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "issue_id": self.issue_id,
            "category": self.category.value,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "recommendation": self.recommendation,
            "code_reference": self.code_reference,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class SecurityCheckResult:
    """安全检查结果"""
    check_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    check_name: str = ""
    passed: bool = True
    issues: List[ReviewIssue] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "check_id": self.check_id,
            "check_name": self.check_name,
            "passed": self.passed,
            "issues": [i.to_dict() for i in self.issues],
            "details": self.details,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class SkillReview:
    """技能审核记录"""
    review_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    skill_id: str = ""
    skill_name: str = ""
    skill_version: str = ""
    reviewer_id: str = ""
    reviewer_name: str = ""
    status: ReviewStatus = ReviewStatus.PENDING
    overall_score: float = 0.0  # 0-100
    security_score: float = 0.0
    performance_score: float = 0.0
    functionality_score: float = 0.0
    documentation_score: float = 0.0
    compatibility_score: float = 0.0
    issues: List[ReviewIssue] = field(default_factory=list)
    security_checks: List[SecurityCheckResult] = field(default_factory=list)
    comments: str = ""
    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "review_id": self.review_id,
            "skill_id": self.skill_id,
            "skill_name": self.skill_name,
            "skill_version": self.skill_version,
            "reviewer_id": self.reviewer_id,
            "reviewer_name": self.reviewer_name,
            "status": self.status.value,
            "overall_score": self.overall_score,
            "security_score": self.security_score,
            "performance_score": self.performance_score,
            "functionality_score": self.functionality_score,
            "documentation_score": self.documentation_score,
            "compatibility_score": self.compatibility_score,
            "issues": [i.to_dict() for i in self.issues],
            "security_checks": [c.to_dict() for c in self.security_checks],
            "comments": self.comments,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "rejected_at": self.rejected_at.isoformat() if self.rejected_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class SkillSecurityChecker:
    """技能安全检查器"""

    async def check_security(self, skill_metadata: Dict[str, Any]) -> SecurityCheckResult:
        """
        检查技能安全性

        Args:
            skill_metadata: 技能元数据

        Returns:
            SecurityCheckResult: 安全检查结果
        """
        result = SecurityCheckResult(check_name="Security Check")
        issues = []

        # 检查1: 风险等级
        risk_level = skill_metadata.get("risk_level", "medium")
        if risk_level == "critical":
            issues.append(
                ReviewIssue(
                    category=ReviewCategory.SECURITY,
                    severity=SeverityLevel.CRITICAL,
                    title="Critical Risk Level",
                    description="Skill has critical risk level and requires additional security review",
                    recommendation="Provide detailed security documentation and threat analysis",
                )
            )

        # 检查2: 依赖安全性
        dependencies = skill_metadata.get("dependencies", {})
        if dependencies:
            issues.append(
                ReviewIssue(
                    category=ReviewCategory.SECURITY,
                    severity=SeverityLevel.WARNING,
                    title="External Dependencies",
                    description=f"Skill has {len(dependencies)} external dependencies",
                    recommendation="Ensure all dependencies are from trusted sources and regularly updated",
                )
            )

        # 检查3: 权限检查
        allowed_actions = skill_metadata.get("allowed_actions", [])
        if "execute" in allowed_actions and "system:execute" in skill_metadata.get("capabilities", []):
            issues.append(
                ReviewIssue(
                    category=ReviewCategory.SECURITY,
                    severity=SeverityLevel.WARNING,
                    title="System Execution Capability",
                    description="Skill has system execution capability",
                    recommendation="Provide detailed documentation on what system commands are executed",
                )
            )

        # 检查4: 网络访问
        if "network:request" in skill_metadata.get("capabilities", []):
            issues.append(
                ReviewIssue(
                    category=ReviewCategory.SECURITY,
                    severity=SeverityLevel.WARNING,
                    title="Network Access",
                    description="Skill has network access capability",
                    recommendation="Document all external services accessed and implement rate limiting",
                )
            )

        # 检查5: 数据处理
        if "document:write" in skill_metadata.get("capabilities", []):
            issues.append(
                ReviewIssue(
                    category=ReviewCategory.SECURITY,
                    severity=SeverityLevel.WARNING,
                    title="Data Write Capability",
                    description="Skill can write data",
                    recommendation="Implement proper data validation and sanitization",
                )
            )

        result.issues = issues
        result.passed = all(i.severity != SeverityLevel.CRITICAL for i in issues)
        result.details = {
            "risk_level": risk_level,
            "dependencies_count": len(dependencies),
            "capabilities": skill_metadata.get("capabilities", []),
            "issues_count": len(issues),
            "critical_issues": sum(1 for i in issues if i.severity == SeverityLevel.CRITICAL),
        }

        return result

    async def check_performance(self, skill_metadata: Dict[str, Any]) -> SecurityCheckResult:
        """检查性能"""
        result = SecurityCheckResult(check_name="Performance Check")
        issues = []

        timeout = skill_metadata.get("timeout_seconds", 300)
        if timeout > 600:
            issues.append(
                ReviewIssue(
                    category=ReviewCategory.PERFORMANCE,
                    severity=SeverityLevel.WARNING,
                    title="High Timeout Value",
                    description=f"Skill timeout is {timeout} seconds",
                    recommendation="Consider reducing timeout to improve responsiveness",
                )
            )

        memory = skill_metadata.get("max_memory_mb", 512)
        if memory > 2048:
            issues.append(
                ReviewIssue(
                    category=ReviewCategory.PERFORMANCE,
                    severity=SeverityLevel.WARNING,
                    title="High Memory Requirement",
                    description=f"Skill requires {memory}MB memory",
                    recommendation="Optimize memory usage or document why high memory is needed",
                )
            )

        cpu = skill_metadata.get("max_cpu_percent", 50.0)
        if cpu > 80.0:
            issues.append(
                ReviewIssue(
                    category=ReviewCategory.PERFORMANCE,
                    severity=SeverityLevel.WARNING,
                    title="High CPU Usage",
                    description=f"Skill uses up to {cpu}% CPU",
                    recommendation="Optimize CPU usage or implement throttling",
                )
            )

        result.issues = issues
        result.passed = len(issues) == 0
        result.details = {
            "timeout_seconds": timeout,
            "max_memory_mb": memory,
            "max_cpu_percent": cpu,
        }

        return result

    async def check_functionality(self, skill_metadata: Dict[str, Any]) -> SecurityCheckResult:
        """检查功能"""
        result = SecurityCheckResult(check_name="Functionality Check")
        issues = []

        # 检查必需字段
        required_fields = ["name", "version", "description", "author"]
        for field in required_fields:
            if not skill_metadata.get(field):
                issues.append(
                    ReviewIssue(
                        category=ReviewCategory.FUNCTIONALITY,
                        severity=SeverityLevel.ERROR,
                        title=f"Missing {field}",
                        description=f"Required field '{field}' is missing",
                        recommendation=f"Provide a valid {field}",
                    )
                )

        # 检查参数定义
        parameters = skill_metadata.get("parameters", [])
        if not parameters:
            issues.append(
                ReviewIssue(
                    category=ReviewCategory.FUNCTIONALITY,
                    severity=SeverityLevel.WARNING,
                    title="No Parameters Defined",
                    description="Skill has no input parameters defined",
                    recommendation="Define input parameters for better usability",
                )
            )

        # 检查能力定义
        capabilities = skill_metadata.get("capabilities", [])
        if not capabilities:
            issues.append(
                ReviewIssue(
                    category=ReviewCategory.FUNCTIONALITY,
                    severity=SeverityLevel.WARNING,
                    title="No Capabilities Defined",
                    description="Skill has no capabilities defined",
                    recommendation="Define what the skill can do",
                )
            )

        result.issues = issues
        result.passed = all(i.severity != SeverityLevel.ERROR for i in issues)
        result.details = {
            "parameters_count": len(parameters),
            "capabilities_count": len(capabilities),
        }

        return result

    async def check_documentation(self, skill_metadata: Dict[str, Any]) -> SecurityCheckResult:
        """检查文档"""
        result = SecurityCheckResult(check_name="Documentation Check")
        issues = []

        description = skill_metadata.get("description", "")
        if not description or len(description) < 50:
            issues.append(
                ReviewIssue(
                    category=ReviewCategory.DOCUMENTATION,
                    severity=SeverityLevel.WARNING,
                    title="Insufficient Description",
                    description="Skill description is too short",
                    recommendation="Provide a detailed description (at least 50 characters)",
                )
            )

        doc_url = skill_metadata.get("documentation_url", "")
        if not doc_url:
            issues.append(
                ReviewIssue(
                    category=ReviewCategory.DOCUMENTATION,
                    severity=SeverityLevel.WARNING,
                    title="Missing Documentation URL",
                    description="No documentation URL provided",
                    recommendation="Provide a link to detailed documentation",
                )
            )

        repo_url = skill_metadata.get("repository_url", "")
        if not repo_url:
            issues.append(
                ReviewIssue(
                    category=ReviewCategory.DOCUMENTATION,
                    severity=SeverityLevel.INFO,
                    title="Missing Repository URL",
                    description="No repository URL provided",
                    recommendation="Provide a link to the source code repository",
                )
            )

        result.issues = issues
        result.passed = len([i for i in issues if i.severity in [SeverityLevel.ERROR, SeverityLevel.CRITICAL]]) == 0
        result.details = {
            "has_description": bool(description),
            "description_length": len(description),
            "has_documentation_url": bool(doc_url),
            "has_repository_url": bool(repo_url),
        }

        return result

    async def check_compatibility(self, skill_metadata: Dict[str, Any]) -> SecurityCheckResult:
        """检查兼容性"""
        result = SecurityCheckResult(check_name="Compatibility Check")
        issues = []

        version = skill_metadata.get("version", "")
        if not self._is_valid_version(version):
            issues.append(
                ReviewIssue(
                    category=ReviewCategory.COMPATIBILITY,
                    severity=SeverityLevel.ERROR,
                    title="Invalid Version Format",
                    description=f"Version '{version}' is not in valid format",
                    recommendation="Use semantic versioning (e.g., 1.0.0)",
                )
            )

        license_type = skill_metadata.get("license", "")
        valid_licenses = ["MIT", "Apache-2.0", "GPL-3.0", "BSD-3-Clause", "ISC", "Proprietary"]
        if license_type and license_type not in valid_licenses:
            issues.append(
                ReviewIssue(
                    category=ReviewCategory.COMPATIBILITY,
                    severity=SeverityLevel.WARNING,
                    title="Uncommon License",
                    description=f"License '{license_type}' is not commonly used",
                    recommendation=f"Consider using one of: {', '.join(valid_licenses)}",
                )
            )

        result.issues = issues
        result.passed = all(i.severity != SeverityLevel.ERROR for i in issues)
        result.details = {
            "version": version,
            "license": license_type,
        }

        return result

    def _is_valid_version(self, version: str) -> bool:
        """验证版本格式"""
        import re
        pattern = r"^\d+\.\d+\.\d+(-[a-zA-Z0-9]+)?$"
        return bool(re.match(pattern, version))


class SkillReviewManager:
    """技能审核管理器"""

    def __init__(self):
        self.security_checker = SkillSecurityChecker()
        self._reviews: Dict[str, SkillReview] = {}

    async def create_review(
        self,
        skill_id: str,
        skill_name: str,
        skill_version: str,
        skill_metadata: Dict[str, Any],
    ) -> SkillReview:
        """
        创建审核记录

        Args:
            skill_id: 技能ID
            skill_name: 技能名称
            skill_version: 技能版本
            skill_metadata: 技能元数据

        Returns:
            SkillReview: 审核记录
        """
        review = SkillReview(
            skill_id=skill_id,
            skill_name=skill_name,
            skill_version=skill_version,
        )

        # 执行所有检查
        security_result = await self.security_checker.check_security(skill_metadata)
        performance_result = await self.security_checker.check_performance(skill_metadata)
        functionality_result = await self.security_checker.check_functionality(skill_metadata)
        documentation_result = await self.security_checker.check_documentation(skill_metadata)
        compatibility_result = await self.security_checker.check_compatibility(skill_metadata)

        review.security_checks = [
            security_result,
            performance_result,
            functionality_result,
            documentation_result,
            compatibility_result,
        ]

        # 收集所有问题
        all_issues = []
        for check in review.security_checks:
            all_issues.extend(check.issues)
        review.issues = all_issues

        # 计算分数
        review.security_score = self._calculate_score(security_result)
        review.performance_score = self._calculate_score(performance_result)
        review.functionality_score = self._calculate_score(functionality_result)
        review.documentation_score = self._calculate_score(documentation_result)
        review.compatibility_score = self._calculate_score(compatibility_result)

        # 计算总分
        review.overall_score = (
            review.security_score * 0.3
            + review.performance_score * 0.2
            + review.functionality_score * 0.2
            + review.documentation_score * 0.15
            + review.compatibility_score * 0.15
        )

        # 确定状态
        critical_issues = [i for i in all_issues if i.severity == SeverityLevel.CRITICAL]
        error_issues = [i for i in all_issues if i.severity == SeverityLevel.ERROR]

        if critical_issues:
            review.status = ReviewStatus.REJECTED
        elif error_issues:
            review.status = ReviewStatus.NEEDS_REVISION
        elif review.overall_score >= 80:
            review.status = ReviewStatus.APPROVED
        elif review.overall_score >= 60:
            review.status = ReviewStatus.APPROVED_WITH_CONDITIONS
        else:
            review.status = ReviewStatus.NEEDS_REVISION

        self._reviews[review.review_id] = review
        logger.info(f"Review created: {review.review_id} for skill {skill_name}")

        return review

    async def approve_review(
        self,
        review_id: str,
        reviewer_id: str,
        reviewer_name: str,
        comments: str = "",
    ) -> SkillReview:
        """批准审核"""
        review = self._reviews.get(review_id)
        if not review:
            raise ValueError(f"Review not found: {review_id}")

        review.status = ReviewStatus.APPROVED
        review.reviewer_id = reviewer_id
        review.reviewer_name = reviewer_name
        review.comments = comments
        review.approved_at = datetime.now(UTC)
        review.updated_at = datetime.now(UTC)

        logger.info(f"Review approved: {review_id}")
        return review

    async def reject_review(
        self,
        review_id: str,
        reviewer_id: str,
        reviewer_name: str,
        comments: str = "",
    ) -> SkillReview:
        """拒绝审核"""
        review = self._reviews.get(review_id)
        if not review:
            raise ValueError(f"Review not found: {review_id}")

        review.status = ReviewStatus.REJECTED
        review.reviewer_id = reviewer_id
        review.reviewer_name = reviewer_name
        review.comments = comments
        review.rejected_at = datetime.now(UTC)
        review.updated_at = datetime.now(UTC)

        logger.info(f"Review rejected: {review_id}")
        return review

    async def get_review(self, review_id: str) -> Optional[SkillReview]:
        """获取审核记录"""
        return self._reviews.get(review_id)

    async def list_reviews(
        self,
        status: Optional[ReviewStatus] = None,
        limit: int = 100,
    ) -> List[SkillReview]:
        """列出审核记录"""
        reviews = list(self._reviews.values())
        if status:
            reviews = [r for r in reviews if r.status == status]
        return sorted(reviews, key=lambda x: x.created_at, reverse=True)[:limit]

    def _calculate_score(self, result: SecurityCheckResult) -> float:
        """计算检查分数"""
        if result.passed:
            return 100.0

        # 根据问题严重程度计算分数
        critical_count = sum(1 for i in result.issues if i.severity == SeverityLevel.CRITICAL)
        error_count = sum(1 for i in result.issues if i.severity == SeverityLevel.ERROR)
        warning_count = sum(1 for i in result.issues if i.severity == SeverityLevel.WARNING)

        score = 100.0
        score -= critical_count * 30
        score -= error_count * 20
        score -= warning_count * 5

        return max(0.0, score)


# Global instance
_review_manager: Optional[SkillReviewManager] = None


def get_skill_review_manager() -> SkillReviewManager:
    """获取全局技能审核管理器"""
    global _review_manager
    if _review_manager is None:
        _review_manager = SkillReviewManager()
    return _review_manager


__all__ = [
    "ReviewStatus",
    "ReviewCategory",
    "SeverityLevel",
    "ReviewIssue",
    "SecurityCheckResult",
    "SkillReview",
    "SkillSecurityChecker",
    "SkillReviewManager",
    "get_skill_review_manager",
]
