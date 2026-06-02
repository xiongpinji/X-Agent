"""
示例技能1: 代码审查助手
"""

from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class CodeReviewAssistant:
    """代码审查助手 - 自动审查代码质量、安全性和最佳实践"""

    def __init__(self):
        self.name = "Code Review Assistant"
        self.version = "1.0.0"
        self.author = "X-Agent Team"

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行代码审查

        Args:
            input_data: {
                "code": "代码内容",
                "language": "编程语言",
                "focus": ["security", "performance", "style"]  # 审查重点
            }

        Returns:
            审查结果
        """
        try:
            code = input_data.get("code", "")
            language = input_data.get("language", "python")
            focus = input_data.get("focus", ["security", "performance", "style"])

            if not code:
                raise ValueError("代码内容不能为空")

            issues = self._analyze_code(code, language, focus)

            return {
                "status": "success",
                "data": {
                    "language": language,
                    "issues": issues,
                    "summary": self._generate_summary(issues),
                    "score": self._calculate_score(issues),
                }
            }
        except Exception as e:
            logger.error(f"代码审查失败: {e}")
            return {"status": "error", "error": str(e)}

    def _analyze_code(self, code: str, language: str, focus: List[str]) -> List[Dict[str, Any]]:
        """分析代码"""
        issues = []

        if "security" in focus:
            issues.extend(self._check_security(code, language))

        if "performance" in focus:
            issues.extend(self._check_performance(code, language))

        if "style" in focus:
            issues.extend(self._check_style(code, language))

        return issues

    def _check_security(self, code: str, language: str) -> List[Dict[str, Any]]:
        """检查安全问题"""
        issues = []

        # 检查 SQL 注入
        if "sql" in code.lower() and "+" in code:
            issues.append({
                "type": "security",
                "severity": "high",
                "message": "可能存在 SQL 注入风险，建议使用参数化查询",
                "line": "N/A",
            })

        # 检查硬编码密钥
        if "password" in code.lower() or "api_key" in code.lower():
            if "=" in code and '"' in code:
                issues.append({
                    "type": "security",
                    "severity": "critical",
                    "message": "检测到硬编码的敏感信息，建议使用环境变量",
                    "line": "N/A",
                })

        return issues

    def _check_performance(self, code: str, language: str) -> List[Dict[str, Any]]:
        """检查性能问题"""
        issues = []

        # 检查嵌套循环
        if code.count("for ") > 2:
            issues.append({
                "type": "performance",
                "severity": "medium",
                "message": "检测到多层嵌套循环，可能影响性能",
                "line": "N/A",
            })

        return issues

    def _check_style(self, code: str, language: str) -> List[Dict[str, Any]]:
        """检查代码风格"""
        issues = []

        # 检查命名规范
        if language == "python":
            if "CamelCase" in code:
                issues.append({
                    "type": "style",
                    "severity": "low",
                    "message": "Python 建议使用 snake_case 命名变量",
                    "line": "N/A",
                })

        return issues

    def _generate_summary(self, issues: List[Dict[str, Any]]) -> str:
        """生成总结"""
        if not issues:
            return "代码质量良好，未发现问题"

        critical = len([i for i in issues if i["severity"] == "critical"])
        high = len([i for i in issues if i["severity"] == "high"])
        medium = len([i for i in issues if i["severity"] == "medium"])

        return f"发现 {len(issues)} 个问题: {critical} 个严重, {high} 个高, {medium} 个中等"

    def _calculate_score(self, issues: List[Dict[str, Any]]) -> float:
        """计算代码质量分数"""
        if not issues:
            return 100.0

        severity_weights = {"critical": 10, "high": 5, "medium": 2, "low": 1}
        total_weight = sum(severity_weights.get(i["severity"], 0) for i in issues)

        return max(0, 100 - total_weight)


__all__ = ["CodeReviewAssistant"]
