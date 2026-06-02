"""
X-Agent 端到端测试框架 - 测试执行和报告生成

功能:
- 测试执行管理
- 测试结果收集
- 报告生成
- 缺陷追踪
"""

import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import csv


# ============================================================================
# 数据模型
# ============================================================================

class TestStatus(str, Enum):
    """测试状态"""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class DefectSeverity(str, Enum):
    """缺陷严重级别"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class TestResult:
    """测试结果"""
    test_id: str
    test_name: str
    test_case_id: str
    status: TestStatus
    start_time: datetime
    end_time: datetime
    duration: float  # 秒
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None
    assertions: int = 0
    passed_assertions: int = 0


@dataclass
class Defect:
    """缺陷"""
    defect_id: str
    test_case_id: str
    title: str
    description: str
    severity: DefectSeverity
    status: str  # new, assigned, fixed, verified, closed
    created_at: datetime
    updated_at: datetime
    assigned_to: Optional[str] = None
    reproduction_steps: Optional[str] = None
    expected_result: Optional[str] = None
    actual_result: Optional[str] = None


@dataclass
class TestExecutionReport:
    """测试执行报告"""
    report_id: str
    execution_date: datetime
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    error_tests: int
    total_duration: float
    pass_rate: float
    code_coverage: float
    defects: List[Defect]
    test_results: List[TestResult]


# ============================================================================
# 测试执行管理器
# ============================================================================

class TestExecutionManager:
    """测试执行管理器"""

    def __init__(self):
        self.test_results: List[TestResult] = []
        self.defects: List[Defect] = []
        self.execution_start_time: Optional[datetime] = None
        self.execution_end_time: Optional[datetime] = None
        self.defect_counter = 0
        self.test_counter = 0

    def start_execution(self):
        """开始执行"""
        self.execution_start_time = datetime.now()
        self.test_results = []
        self.defects = []

    def end_execution(self):
        """结束执行"""
        self.execution_end_time = datetime.now()

    def record_test_result(self, test_name: str, test_case_id: str, status: TestStatus,
                          duration: float, error_message: Optional[str] = None,
                          stack_trace: Optional[str] = None) -> TestResult:
        """记录测试结果"""
        self.test_counter += 1
        result = TestResult(
            test_id=f"test_{self.test_counter:06d}",
            test_name=test_name,
            test_case_id=test_case_id,
            status=status,
            start_time=datetime.now() - timedelta(seconds=duration),
            end_time=datetime.now(),
            duration=duration,
            error_message=error_message,
            stack_trace=stack_trace
        )
        self.test_results.append(result)

        # 如果测试失败，创建缺陷
        if status == TestStatus.FAILED:
            self.create_defect(
                test_case_id=test_case_id,
                title=f"Test Failed: {test_name}",
                description=error_message or "Test execution failed",
                severity=DefectSeverity.HIGH,
                reproduction_steps=f"Run test case: {test_case_id}",
                actual_result=error_message
            )

        return result

    def create_defect(self, test_case_id: str, title: str, description: str,
                     severity: DefectSeverity, reproduction_steps: Optional[str] = None,
                     expected_result: Optional[str] = None,
                     actual_result: Optional[str] = None) -> Defect:
        """创建缺陷"""
        self.defect_counter += 1
        defect = Defect(
            defect_id=f"defect_{self.defect_counter:06d}",
            test_case_id=test_case_id,
            title=title,
            description=description,
            severity=severity,
            status="new",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            reproduction_steps=reproduction_steps,
            expected_result=expected_result,
            actual_result=actual_result
        )
        self.defects.append(defect)
        return defect

    def update_defect_status(self, defect_id: str, status: str, assigned_to: Optional[str] = None) -> bool:
        """更新缺陷状态"""
        for defect in self.defects:
            if defect.defect_id == defect_id:
                defect.status = status
                defect.updated_at = datetime.now()
                if assigned_to:
                    defect.assigned_to = assigned_to
                return True
        return False

    def get_execution_report(self) -> TestExecutionReport:
        """获取执行报告"""
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r.status == TestStatus.PASSED])
        failed_tests = len([r for r in self.test_results if r.status == TestStatus.FAILED])
        skipped_tests = len([r for r in self.test_results if r.status == TestStatus.SKIPPED])
        error_tests = len([r for r in self.test_results if r.status == TestStatus.ERROR])

        total_duration = sum(r.duration for r in self.test_results)
        pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

        report = TestExecutionReport(
            report_id=f"report_{int(datetime.now().timestamp())}",
            execution_date=self.execution_start_time or datetime.now(),
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            skipped_tests=skipped_tests,
            error_tests=error_tests,
            total_duration=total_duration,
            pass_rate=pass_rate,
            code_coverage=0,  # 需要实际测量
            defects=self.defects,
            test_results=self.test_results
        )

        return report

    def get_defects_by_severity(self, severity: DefectSeverity) -> List[Defect]:
        """按严重级别获取缺陷"""
        return [d for d in self.defects if d.severity == severity]

    def get_defects_by_status(self, status: str) -> List[Defect]:
        """按状态获取缺陷"""
        return [d for d in self.defects if d.status == status]


# ============================================================================
# 报告生成器
# ============================================================================

class ReportGenerator:
    """报告生成器"""

    @staticmethod
    def generate_json_report(report: TestExecutionReport, output_path: str):
        """生成 JSON 报告"""
        report_dict = {
            "report_id": report.report_id,
            "execution_date": report.execution_date.isoformat(),
            "summary": {
                "total_tests": report.total_tests,
                "passed_tests": report.passed_tests,
                "failed_tests": report.failed_tests,
                "skipped_tests": report.skipped_tests,
                "error_tests": report.error_tests,
                "pass_rate": f"{report.pass_rate:.2f}%",
                "total_duration": f"{report.total_duration:.2f}s",
                "code_coverage": f"{report.code_coverage:.2f}%"
            },
            "test_results": [
                {
                    "test_id": r.test_id,
                    "test_name": r.test_name,
                    "test_case_id": r.test_case_id,
                    "status": r.status.value,
                    "duration": f"{r.duration:.3f}s",
                    "error_message": r.error_message
                }
                for r in report.test_results
            ],
            "defects": [
                {
                    "defect_id": d.defect_id,
                    "test_case_id": d.test_case_id,
                    "title": d.title,
                    "severity": d.severity.value,
                    "status": d.status,
                    "created_at": d.created_at.isoformat()
                }
                for d in report.defects
            ]
        }

        with open(output_path, "w") as f:
            json.dump(report_dict, f, indent=2)

    @staticmethod
    def generate_csv_report(report: TestExecutionReport, output_path: str):
        """生成 CSV 报告"""
        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)

            # 写入摘要
            writer.writerow(["Test Execution Report"])
            writer.writerow(["Report ID", report.report_id])
            writer.writerow(["Execution Date", report.execution_date.isoformat()])
            writer.writerow([])

            # 写入统计
            writer.writerow(["Summary"])
            writer.writerow(["Total Tests", report.total_tests])
            writer.writerow(["Passed Tests", report.passed_tests])
            writer.writerow(["Failed Tests", report.failed_tests])
            writer.writerow(["Skipped Tests", report.skipped_tests])
            writer.writerow(["Error Tests", report.error_tests])
            writer.writerow(["Pass Rate", f"{report.pass_rate:.2f}%"])
            writer.writerow(["Total Duration", f"{report.total_duration:.2f}s"])
            writer.writerow([])

            # 写入测试结果
            writer.writerow(["Test Results"])
            writer.writerow(["Test ID", "Test Name", "Test Case ID", "Status", "Duration", "Error Message"])
            for result in report.test_results:
                writer.writerow([
                    result.test_id,
                    result.test_name,
                    result.test_case_id,
                    result.status.value,
                    f"{result.duration:.3f}s",
                    result.error_message or ""
                ])
            writer.writerow([])

            # 写入缺陷
            writer.writerow(["Defects"])
            writer.writerow(["Defect ID", "Test Case ID", "Title", "Severity", "Status", "Created At"])
            for defect in report.defects:
                writer.writerow([
                    defect.defect_id,
                    defect.test_case_id,
                    defect.title,
                    defect.severity.value,
                    defect.status,
                    defect.created_at.isoformat()
                ])

    @staticmethod
    def generate_html_report(report: TestExecutionReport, output_path: str):
        """生成 HTML 报告"""
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Test Execution Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        h2 {{ color: #666; margin-top: 30px; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 10px; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #4CAF50; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .summary {{ background-color: #f9f9f9; padding: 10px; border-radius: 5px; }}
        .passed {{ color: green; }}
        .failed {{ color: red; }}
        .skipped {{ color: orange; }}
    </style>
</head>
<body>
    <h1>Test Execution Report</h1>
    <p><strong>Report ID:</strong> {report.report_id}</p>
    <p><strong>Execution Date:</strong> {report.execution_date.isoformat()}</p>

    <div class="summary">
        <h2>Summary</h2>
        <p><strong>Total Tests:</strong> {report.total_tests}</p>
        <p><strong>Passed Tests:</strong> <span class="passed">{report.passed_tests}</span></p>
        <p><strong>Failed Tests:</strong> <span class="failed">{report.failed_tests}</span></p>
        <p><strong>Skipped Tests:</strong> <span class="skipped">{report.skipped_tests}</span></p>
        <p><strong>Error Tests:</strong> {report.error_tests}</p>
        <p><strong>Pass Rate:</strong> {report.pass_rate:.2f}%</p>
        <p><strong>Total Duration:</strong> {report.total_duration:.2f}s</p>
        <p><strong>Code Coverage:</strong> {report.code_coverage:.2f}%</p>
    </div>

    <h2>Test Results</h2>
    <table>
        <tr>
            <th>Test ID</th>
            <th>Test Name</th>
            <th>Test Case ID</th>
            <th>Status</th>
            <th>Duration</th>
            <th>Error Message</th>
        </tr>
"""

        for result in report.test_results:
            status_class = "passed" if result.status == TestStatus.PASSED else "failed"
            html_content += f"""
        <tr>
            <td>{result.test_id}</td>
            <td>{result.test_name}</td>
            <td>{result.test_case_id}</td>
            <td class="{status_class}">{result.status.value}</td>
            <td>{result.duration:.3f}s</td>
            <td>{result.error_message or ""}</td>
        </tr>
"""

        html_content += """
    </table>

    <h2>Defects</h2>
    <table>
        <tr>
            <th>Defect ID</th>
            <th>Test Case ID</th>
            <th>Title</th>
            <th>Severity</th>
            <th>Status</th>
            <th>Created At</th>
        </tr>
"""

        for defect in report.defects:
            html_content += f"""
        <tr>
            <td>{defect.defect_id}</td>
            <td>{defect.test_case_id}</td>
            <td>{defect.title}</td>
            <td>{defect.severity.value}</td>
            <td>{defect.status}</td>
            <td>{defect.created_at.isoformat()}</td>
        </tr>
"""

        html_content += """
    </table>
</body>
</html>
"""

        with open(output_path, "w") as f:
            f.write(html_content)


# ============================================================================
# 测试用例
# ============================================================================

class TestExecutionManagement:
    """测试执行管理测试"""

    def test_record_test_result(self):
        """测试记录测试结果"""
        manager = TestExecutionManager()
        manager.start_execution()

        result = manager.record_test_result(
            test_name="test_create_task",
            test_case_id="TC-TASK-001",
            status=TestStatus.PASSED,
            duration=0.5
        )

        assert result.status == TestStatus.PASSED
        assert len(manager.test_results) == 1

    def test_create_defect(self):
        """测试创建缺陷"""
        manager = TestExecutionManager()

        defect = manager.create_defect(
            test_case_id="TC-TASK-001",
            title="Test Failed",
            description="Task creation failed",
            severity=DefectSeverity.HIGH
        )

        assert defect.severity == DefectSeverity.HIGH
        assert defect.status == "new"

    def test_update_defect_status(self):
        """测试更新缺陷状态"""
        manager = TestExecutionManager()

        defect = manager.create_defect(
            test_case_id="TC-TASK-001",
            title="Test Failed",
            description="Task creation failed",
            severity=DefectSeverity.HIGH
        )

        success = manager.update_defect_status(defect.defect_id, "assigned", "developer_001")

        assert success
        assert defect.status == "assigned"
        assert defect.assigned_to == "developer_001"

    def test_get_execution_report(self):
        """测试获取执行报告"""
        manager = TestExecutionManager()
        manager.start_execution()

        # 记录测试结果
        manager.record_test_result("test_1", "TC-001", TestStatus.PASSED, 0.5)
        manager.record_test_result("test_2", "TC-002", TestStatus.FAILED, 0.3)
        manager.record_test_result("test_3", "TC-003", TestStatus.PASSED, 0.4)

        manager.end_execution()

        report = manager.get_execution_report()

        assert report.total_tests == 3
        assert report.passed_tests == 2
        assert report.failed_tests == 1
        assert report.pass_rate == 66.67


class TestReportGeneration:
    """报告生成测试"""

    def test_generate_json_report(self, tmp_path):
        """测试生成 JSON 报告"""
        manager = TestExecutionManager()
        manager.start_execution()

        manager.record_test_result("test_1", "TC-001", TestStatus.PASSED, 0.5)
        manager.end_execution()

        report = manager.get_execution_report()

        output_path = tmp_path / "report.json"
        ReportGenerator.generate_json_report(report, str(output_path))

        assert output_path.exists()

    def test_generate_csv_report(self, tmp_path):
        """测试生成 CSV 报告"""
        manager = TestExecutionManager()
        manager.start_execution()

        manager.record_test_result("test_1", "TC-001", TestStatus.PASSED, 0.5)
        manager.end_execution()

        report = manager.get_execution_report()

        output_path = tmp_path / "report.csv"
        ReportGenerator.generate_csv_report(report, str(output_path))

        assert output_path.exists()

    def test_generate_html_report(self, tmp_path):
        """测试生成 HTML 报告"""
        manager = TestExecutionManager()
        manager.start_execution()

        manager.record_test_result("test_1", "TC-001", TestStatus.PASSED, 0.5)
        manager.end_execution()

        report = manager.get_execution_report()

        output_path = tmp_path / "report.html"
        ReportGenerator.generate_html_report(report, str(output_path))

        assert output_path.exists()


# ============================================================================
# 测试套件
# ============================================================================

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "--tb=short"])

