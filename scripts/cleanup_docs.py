#!/usr/bin/env python3
"""
X-Agent 文档清理脚本
删除所有临时的审计、部署、测试报告文档，保留核心开源文档
"""

import os
import sys
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 要删除的文件列表
FILES_TO_DELETE = [
    # 审计报告（过时）
    "X-Agent深度审计综合报告.md",
    "X-Agent 原创内核计划/backend/SECURITY_AUDIT_REPORT.md",

    # 部署临时文档（已完成）
    "DEPLOYMENT_GUIDE_IMMEDIATE.md",
    "DEPLOYMENT_STATUS_REPORT.md",
    "DEPLOYMENT_EXECUTION_SUMMARY.md",
    "DEPLOYMENT_FINAL_REPORT.md",
    "BUG_FIX_VERIFICATION_REPORT.md",
    "DEPLOYMENT_COMPLETE_REPORT.md",
    "PERFORMANCE_OPTIMIZATION_GUIDE.md",

    # 升级/修复方案（已完成）
    "X-Agent完整升级修复方案.md",
    "SKILLS_INTEGRATION.md",
    "PARALLEL_EXECUTION_PLAN.md",

    # 测试报告（临时）
    "X-Agent 原创内核计划/TESTING_COMPLETION_REPORT.txt",
    "X-Agent 原创内核计划/TESTING_REPORT.txt",
    "X-Agent 原创内核计划/tests/TEST_REPORT.txt",
    "X-Agent 原创内核计划/tests/EXECUTION_SUMMARY.txt",
    "X-Agent 原创内核计划/TYPE_HINTS_FINAL_REPORT.txt",
    "X-Agent 原创内核计划/SKILLS_IMPLEMENTATION_COMPLETE.txt",
    "backend/tests/performance/PERFORMANCE_TEST_EXECUTION_REPORT.txt",
    "backend/tests/performance/PERFORMANCE_TEST_EXECUTION_SUMMARY.txt",
    "验证执行总结.txt",

    # P2集成报告（临时）
    "X-Agent 原创内核计划/P2_INTEGRATION_REPORT.txt",
    "X-Agent 原创内核计划/P2_INTEGRATION_COMPLETION_SUMMARY.txt",

    # 清理计划本身（执行后删除）
    "CLEANUP_PLAN.md",
]

def delete_file(file_path: Path) -> bool:
    """删除文件"""
    try:
        if file_path.exists():
            file_path.unlink()
            print(f"✅ 已删除: {file_path.relative_to(PROJECT_ROOT)}")
            return True
        else:
            print(f"⚠️  文件不存在: {file_path.relative_to(PROJECT_ROOT)}")
            return False
    except Exception as e:
        print(f"❌ 删除失败: {file_path.relative_to(PROJECT_ROOT)} - {e}")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("X-Agent 文档清理")
    print("=" * 60)
    print(f"项目根目录: {PROJECT_ROOT}")
    print(f"待删除文件数: {len(FILES_TO_DELETE)}")
    print()

    # 确认
    response = input("确认删除以上文件？(yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("取消清理")
        return 1

    print("\n开始清理...")
    print("-" * 60)

    deleted_count = 0
    not_found_count = 0
    failed_count = 0

    for file_rel_path in FILES_TO_DELETE:
        file_path = PROJECT_ROOT / file_rel_path

        if file_path.exists():
            if delete_file(file_path):
                deleted_count += 1
            else:
                failed_count += 1
        else:
            not_found_count += 1
            print(f"⚠️  跳过（不存在）: {file_rel_path}")

    # 总结
    print()
    print("=" * 60)
    print("清理完成")
    print("=" * 60)
    print(f"✅ 已删除: {deleted_count} 个文件")
    print(f"⚠️  不存在: {not_found_count} 个文件")
    print(f"❌ 失败: {failed_count} 个文件")
    print()

    if failed_count == 0:
        print("🎉 所有文件清理成功！")
        print("项目目录已达到可开源级别的干净程度。")
        return 0
    else:
        print("⚠️  部分文件清理失败，请手动检查。")
        return 1

if __name__ == "__main__":
    sys.exit(main())
