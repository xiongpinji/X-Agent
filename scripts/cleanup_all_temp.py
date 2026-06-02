#!/usr/bin/env python3
"""
通用临时文档清理脚本 - 清理所有匹配模式的临时文档
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

def find_and_delete_temp_docs():
    """查找并删除所有临时文档"""
    print("=" * 70)
    print("查找并清理所有临时文档")
    print("=" * 70)

    # 临时文档匹配模式
    patterns = [
        "*DEPLOYMENT*.md",
        "*DEPLOYMENT*.txt",
        "*TESTING*.txt",
        "*TESTING*.md",
        "*REPORT*.txt",
        "*SUMMARY*.md",
        "*SUMMARY*.txt",
        "*GUIDE*.md",
        "*CHECKLIST*.md",
        "*EXECUTION*.md",
        "*SECURITY*.md",
        "*AUDIT*.md",
    ]

    # 排除的文档（核心文档，不应删除）
    exclude = {
        "README.md",
        "CONTRIBUTING.md",
        "CHANGELOG.md",
        "INSTALL.md",
        "QUICKSTART.md",
        "ARCHITECTURE.md",
        "EXAMPLES.md",
        "TROUBLESHOOTING.md",
        "git-workflow.md",
    }

    temp_files = []
    for pattern in patterns:
        for file in PROJECT_ROOT.glob(pattern):
            if file.is_file() and file.name not in exclude:
                temp_files.append(file)

    # 去重
    temp_files = list(set(temp_files))

    if not temp_files:
        print("✅ 没有找到临时文档")
        return 0

    print(f"\n找到 {len(temp_files)} 个临时文档:")
    for f in temp_files:
        print(f"  - {f.name}")

    response = input(f"\n确认删除这 {len(temp_files)} 个文件？(yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("取消删除")
        return 1

    deleted = 0
    failed = 0

    print("\n开始删除...")
    for file in temp_files:
        try:
            file.unlink()
            print(f"  ✅ 已删除: {file.name}")
            deleted += 1
        except Exception as e:
            print(f"  ❌ 删除失败: {file.name} - {e}")
            failed += 1

    print(f"\n总计: {deleted} 个已删除, {failed} 个失败")

    if deleted > 0:
        print("\n✅ 清理完成！")
        print("\n请再次运行验证:")
        print("  python scripts/validate_project.py")

    return 0

def main():
    return find_and_delete_temp_docs()

if __name__ == "__main__":
    sys.exit(main())
