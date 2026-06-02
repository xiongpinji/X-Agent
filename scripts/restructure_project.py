#!/usr/bin/env python3
"""
X-Agent 目录结构重组脚本

当前结构：
D:\AI编程库\项目库\进行中的项目\X-Agent 原创内核计划\
├── X-Agent 原创内核计划\  (真正的项目根目录)
│   ├── backend/
│   ├── requirements.txt
│   └── ...
├── X-Agent深度审计综合报告.md (临时文档)
├── DEPLOYMENT_*.md (临时文档)
└── ...

目标结构：
D:\AI编程库\项目库\进行中的项目\X-Agent\
├── backend/
├── requirements.txt
└── ...

操作步骤：
1. 列出外层目录的所有临时文档
2. 确认删除
3. 删除临时文档
4. 提示用户手动重命名目录
"""

import os
import sys
from pathlib import Path

# 当前脚本位置
SCRIPT_DIR = Path(__file__).parent
# 项目根目录（内层）
PROJECT_ROOT = SCRIPT_DIR.parent
# 外层目录
OUTER_DIR = PROJECT_ROOT.parent

print("=" * 70)
print("X-Agent 目录结构分析")
print("=" * 70)
print(f"脚本位置: {SCRIPT_DIR}")
print(f"项目根目录（内层）: {PROJECT_ROOT}")
print(f"外层目录: {OUTER_DIR}")
print()

# 要删除的外层临时文档
TEMP_DOCS_TO_DELETE = [
    "X-Agent深度审计综合报告.md",
    "X-Agent完整升级修复方案.md",
    "SKILLS_INTEGRATION.md",
    "PARALLEL_EXECUTION_PLAN.md",
    "DEPLOYMENT_GUIDE_IMMEDIATE.md",
    "DEPLOYMENT_STATUS_REPORT.md",
    "DEPLOYMENT_EXECUTION_SUMMARY.md",
    "DEPLOYMENT_FINAL_REPORT.md",
    "BUG_FIX_VERIFICATION_REPORT.md",
    "DEPLOYMENT_COMPLETE_REPORT.md",
    "CLEANUP_PLAN.md",
    "CLEANUP_README.md",
    "CLEANUP_SUMMARY.md",
]

def list_outer_files():
    """列出外层目录的所有文件"""
    print("=" * 70)
    print("外层目录文件列表")
    print("=" * 70)

    files = []
    dirs = []

    for item in OUTER_DIR.iterdir():
        if item.is_file():
            files.append(item.name)
        elif item.is_dir():
            dirs.append(item.name)

    print("\n📁 目录:")
    for d in sorted(dirs):
        print(f"  - {d}")

    print("\n📄 文件:")
    for f in sorted(files):
        print(f"  - {f}")

    return files, dirs

def delete_temp_docs():
    """删除外层临时文档"""
    print("\n" + "=" * 70)
    print("准备删除外层临时文档")
    print("=" * 70)

    existing_files = []
    for doc in TEMP_DOCS_TO_DELETE:
        file_path = OUTER_DIR / doc
        if file_path.exists():
            existing_files.append(doc)
            print(f"  ✅ {doc}")

    if not existing_files:
        print("  ℹ️  没有找到需要删除的临时文档")
        return True

    print(f"\n找到 {len(existing_files)} 个临时文档")
    response = input("\n确认删除这些文件？(yes/no): ")

    if response.lower() not in ['yes', 'y']:
        print("取消删除")
        return False

    print("\n开始删除...")
    deleted = 0
    failed = 0

    for doc in existing_files:
        file_path = OUTER_DIR / doc
        try:
            file_path.unlink()
            print(f"  ✅ 已删除: {doc}")
            deleted += 1
        except Exception as e:
            print(f"  ❌ 删除失败: {doc} - {e}")
            failed += 1

    print(f"\n删除完成: {deleted} 成功, {failed} 失败")
    return failed == 0

def show_restructure_guide():
    """显示重组指南"""
    print("\n" + "=" * 70)
    print("📋 目录重组指南")
    print("=" * 70)

    print("""
由于Python脚本无法安全地移动正在运行的目录，请手动执行以下步骤：

步骤1：关闭所有使用该目录的程序
  - 关闭IDE、终端、文件资源管理器等

步骤2：重命名内层目录
  当前: D:\\AI编程库\\项目库\\进行中的项目\\X-Agent 原创内核计划\\X-Agent 原创内核计划
  重命名为: X-Agent-temp

步骤3：将X-Agent-temp移动到外层
  从: D:\\AI编程库\\项目库\\进行中的项目\\X-Agent 原创内核计划\\X-Agent-temp
  到: D:\\AI编程库\\项目库\\进行中的项目\\X-Agent-temp

步骤4：删除空的外层目录
  删除: D:\\AI编程库\\项目库\\进行中的项目\\X-Agent 原创内核计划

步骤5：重命名X-Agent-temp为X-Agent
  从: D:\\AI编程库\\项目库\\进行中的项目\\X-Agent-temp
  到: D:\\AI编程库\\项目库\\进行中的项目\\X-Agent

最终结构：
D:\\AI编程库\\项目库\\进行中的项目\\X-Agent\\
├── backend/
├── requirements.txt
├── CONTRIBUTING.md
├── CHANGELOG.md
└── ...

或者使用PowerShell命令（推荐）：
""")

    print("# 在PowerShell中执行：")
    print('cd "D:\\AI编程库\\项目库\\进行中的项目"')
    print('Move-Item "X-Agent 原创内核计划\\X-Agent 原创内核计划" "X-Agent-temp"')
    print('Remove-Item "X-Agent 原创内核计划" -Recurse')
    print('Rename-Item "X-Agent-temp" "X-Agent"')

def main():
    """主函数"""
    # 列出外层文件
    files, dirs = list_outer_files()

    # 删除临时文档
    if not delete_temp_docs():
        print("\n⚠️  临时文档删除未完成")
        return 1

    # 显示重组指南
    show_restructure_guide()

    print("\n" + "=" * 70)
    print("✅ 临时文档清理完成！")
    print("📋 请按照上述指南手动重组目录结构")
    print("=" * 70)

    return 0

if __name__ == "__main__":
    sys.exit(main())
