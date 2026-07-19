#!/usr/bin/env python3
"""
X-Agent 最终清理脚本
修复剩余问题，达到可开源级别
"""

import os
import sys
from pathlib import Path
import shutil

PROJECT_ROOT = Path(__file__).parent.parent

def create_custom_skills_dir():
    """创建custom-skills目录"""
    print("=" * 70)
    print("1. 创建custom-skills目录")
    print("=" * 70)

    custom_skills_dir = PROJECT_ROOT / "custom-skills"

    if custom_skills_dir.exists():
        print("  ✅ custom-skills目录已存在")
        return True

    try:
        custom_skills_dir.mkdir(parents=True, exist_ok=True)

        # 创建README.md
        readme_content = """# Custom Skills

This directory contains custom skills for X-Agent.

## Structure

Each skill should be in its own directory with the following structure:

```
skill-name/
├── SKILL.md          # Skill definition and documentation
├── __init__.py       # Python package initialization
└── skill.py          # Skill implementation
```

## Creating a New Skill

1. Create a new directory for your skill
2. Add a SKILL.md file describing the skill
3. Implement the skill logic in skill.py
4. Test your skill thoroughly

## Examples

See the `.claude/skills/` directory for example skill implementations.
"""

        readme_path = custom_skills_dir / "README.md"
        readme_path.write_text(readme_content, encoding='utf-8')

        print("  ✅ 已创建custom-skills目录")
        print("  ✅ 已创建README.md")
        return True

    except Exception as e:
        print(f"  ❌ 创建失败: {e}")
        return False

def delete_temp_docs():
    """删除临时部署文档"""
    print("\n" + "=" * 70)
    print("2. 删除临时部署文档")
    print("=" * 70)

    temp_docs = [
        "ANALYTICS_DEPLOYMENT_GUIDE.md",
        "DEPLOYMENT_CHECKLIST.md",
        "DEPLOYMENT_GUIDE.md",
        "DEPLOYMENT_INDEX.md",
        "DEPLOYMENT_QUICK_REFERENCE.md",
        "SECURITY-CONFIG.md",
        "security-fixes-report.md",
        "dependency-management-report.md",
        "DEPENDENCY-CHECKLIST.md",
        "EXECUTION-SUMMARY.md",
        "GIT_SETUP_README.md",
        "GIT_NORMALIZATION_REPORT.md",
        "AGENTS.md",
        "backend/SECURITY_AUDIT_REPORT.md",
    ]

    deleted = 0
    not_found = 0

    for doc in temp_docs:
        file_path = PROJECT_ROOT / doc
        if file_path.exists():
            try:
                file_path.unlink()
                print(f"  ✅ 已删除: {doc}")
                deleted += 1
            except Exception as e:
                print(f"  ❌ 删除失败: {doc} - {e}")
        else:
            not_found += 1

    print(f"\n  总计: {deleted} 个已删除, {not_found} 个不存在")
    return True

def verify_fixes():
    """验证修复结果"""
    print("\n" + "=" * 70)
    print("3. 验证修复结果")
    print("=" * 70)

    # 检查custom-skills
    custom_skills = PROJECT_ROOT / "custom-skills"
    if custom_skills.exists():
        print("  ✅ custom-skills目录存在")
    else:
        print("  ❌ custom-skills目录仍然缺失")
        return False

    # 检查临时文档
    temp_docs = list(PROJECT_ROOT.glob("*DEPLOYMENT*.md"))
    temp_docs.extend(PROJECT_ROOT.glob("*SECURITY*.md"))

    if not temp_docs:
        print("  ✅ 临时文档已清理")
    else:
        print(f"  ⚠️  仍有 {len(temp_docs)} 个临时文档")
        for doc in temp_docs[:3]:
            print(f"     - {doc.name}")

    return True

def main():
    """主函数"""
    print("=" * 70)
    print("X-Agent 最终清理 - 达到可开源级别")
    print("=" * 70)
    print(f"项目根目录: {PROJECT_ROOT}\n")

    # 执行修复
    create_custom_skills_dir()
    delete_temp_docs()
    verify_fixes()

    print("\n" + "=" * 70)
    print("✅ 清理完成！")
    print("=" * 70)
    print("\n请再次运行验证脚本:")
    print("  python scripts/validate_project.py")
    print("\n预期结果: 项目完整性评分 ≥ 90%")

    return 0

if __name__ == "__main__":
    sys.exit(main())
