#!/usr/bin/env python3
"""
快速清理剩余临时文档
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

# 剩余的临时文档
REMAINING_DOCS = [
    "DEPLOYMENT_SOLUTION_SUMMARY.md",
    "DEPLOYMENT_SUMMARY.md",
    "MONITORING_DEPLOYMENT_COMPLETE.md",
    "MONITORING_DEPLOYMENT_SUMMARY.md",
    "PLUGIN_MARKET_DEPLOYMENT.md",
]

def main():
    print("=" * 70)
    print("清理剩余临时文档")
    print("=" * 70)

    deleted = 0
    for doc in REMAINING_DOCS:
        file_path = PROJECT_ROOT / doc
        if file_path.exists():
            try:
                file_path.unlink()
                print(f"✅ 已删除: {doc}")
                deleted += 1
            except Exception as e:
                print(f"❌ 删除失败: {doc} - {e}")
        else:
            print(f"⚠️  不存在: {doc}")

    print(f"\n总计删除: {deleted} 个文件")
    print("\n请再次运行验证:")
    print("  python scripts/validate_project.py")

    return 0

if __name__ == "__main__":
    sys.exit(main())
