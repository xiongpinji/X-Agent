#!/usr/bin/env python3
"""
X-Agent 项目完整性深度检查脚本
验证项目是否达到可开源级别
"""

import os
import sys
from pathlib import Path
from typing import List, Tuple

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

class ProjectValidator:
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.passed = []

    def check_core_files(self) -> bool:
        """检查核心文件"""
        print("\n" + "=" * 70)
        print("1. 检查核心文件")
        print("=" * 70)

        required_files = {
            "README.md": "项目说明文档",
            "CONTRIBUTING.md": "贡献指南",
            "CHANGELOG.md": "变更日志",
            "INSTALL.md": "安装指南",
            "LICENSE": "许可证文件",
            "requirements.txt": "生产依赖",
            "requirements-dev.txt": "开发依赖",
            "pytest.ini": "测试配置",
            ".env.example": "环境变量示例",
            ".gitignore": "Git忽略配置",
        }

        all_exist = True
        for file, desc in required_files.items():
            file_path = PROJECT_ROOT / file
            if file_path.exists():
                print(f"  ✅ {file} - {desc}")
                self.passed.append(f"核心文件: {file}")
            else:
                print(f"  ❌ {file} - {desc} (缺失)")
                self.issues.append(f"缺少核心文件: {file}")
                all_exist = False

        return all_exist

    def check_directory_structure(self) -> bool:
        """检查目录结构"""
        print("\n" + "=" * 70)
        print("2. 检查目录结构")
        print("=" * 70)

        required_dirs = {
            "backend": "后端代码",
            "backend/app": "应用代码",
            "backend/app/core": "核心模块",
            "backend/app/api": "API路由",
            "tests": "测试代码",
            "docs": "文档目录",
            "scripts": "工具脚本",
            ".claude/skills": "Claude技能",
            "custom-skills": "自定义技能",
        }

        all_exist = True
        for dir_path, desc in required_dirs.items():
            full_path = PROJECT_ROOT / dir_path
            if full_path.exists() and full_path.is_dir():
                print(f"  ✅ {dir_path}/ - {desc}")
                self.passed.append(f"目录结构: {dir_path}")
            else:
                print(f"  ❌ {dir_path}/ - {desc} (缺失)")
                self.issues.append(f"缺少目录: {dir_path}")
                all_exist = False

        return all_exist

    def check_code_files(self) -> bool:
        """检查代码文件"""
        print("\n" + "=" * 70)
        print("3. 检查核心代码文件")
        print("=" * 70)

        core_modules = [
            "backend/app/core/llm_providers/anthropic.py",
            "backend/app/core/llm_providers/openai.py",
            "backend/app/core/skill_system_v2.py",
            "backend/app/core/audio_processor.py",
            "backend/app/core/advanced_rbac.py",
            "backend/app/core/plugin_system_v2.py",
            "backend/app/core/i18n.py",
        ]

        found = 0
        for module in core_modules:
            file_path = PROJECT_ROOT / module
            if file_path.exists():
                found += 1

        if found > 0:
            print(f"  ✅ 找到 {found}/{len(core_modules)} 个核心模块")
            self.passed.append(f"核心代码: {found}/{len(core_modules)} 模块存在")
            return True
        else:
            print(f"  ❌ 核心模块缺失")
            self.issues.append("核心代码模块缺失")
            return False

    def check_optimization_modules(self) -> bool:
        """检查性能优化模块"""
        print("\n" + "=" * 70)
        print("4. 检查性能优化模块")
        print("=" * 70)

        optimization_modules = [
            "backend/app/core/multimodal_processor_optimized.py",
        ]

        found = 0
        for module in optimization_modules:
            file_path = PROJECT_ROOT / module
            if file_path.exists():
                found += 1

        print(f"  ℹ️  找到 {found}/{len(optimization_modules)} 个优化模块")
        if found > 0:
            self.passed.append(f"性能优化: {found}/{len(optimization_modules)} 模块")
        else:
            self.warnings.append("性能优化模块未找到（可选）")

        return True

    def check_temp_docs(self) -> bool:
        """检查是否还有临时文档"""
        print("\n" + "=" * 70)
        print("5. 检查临时文档（应该已清理）")
        print("=" * 70)

        temp_patterns = [
            "*审计*.md",
            "*DEPLOYMENT*.md",
            "*BUG_FIX*.md",
            "*CLEANUP*.md",
            "*测试报告*.txt",
            "*TESTING*.txt",
            "*P2_INTEGRATION*.txt",
        ]

        temp_files = []
        for pattern in temp_patterns:
            temp_files.extend(PROJECT_ROOT.glob(pattern))

        if not temp_files:
            print("  ✅ 没有发现临时文档")
            self.passed.append("临时文档已清理")
            return True
        else:
            print(f"  ⚠️  发现 {len(temp_files)} 个临时文档:")
            for f in temp_files[:5]:  # 只显示前5个
                print(f"     - {f.name}")
                self.warnings.append(f"临时文档: {f.name}")
            return False

    def check_git_setup(self) -> bool:
        """检查Git配置"""
        print("\n" + "=" * 70)
        print("6. 检查Git配置")
        print("=" * 70)

        git_dir = PROJECT_ROOT / ".git"
        gitignore = PROJECT_ROOT / ".gitignore"

        if git_dir.exists():
            print("  ✅ Git仓库已初始化")
            self.passed.append("Git仓库已初始化")
        else:
            print("  ⚠️  Git仓库未初始化")
            self.warnings.append("Git仓库未初始化")

        if gitignore.exists():
            print("  ✅ .gitignore 文件存在")
            self.passed.append(".gitignore 存在")
        else:
            print("  ❌ .gitignore 文件缺失")
            self.issues.append(".gitignore 文件缺失")

        return True

    def check_documentation_quality(self) -> bool:
        """检查文档质量"""
        print("\n" + "=" * 70)
        print("7. 检查文档质量")
        print("=" * 70)

        readme = PROJECT_ROOT / "README.md"
        if readme.exists():
            size = readme.stat().st_size
            if size > 1000:  # 至少1KB
                print(f"  ✅ README.md 存在且有内容 ({size} bytes)")
                self.passed.append("README.md 质量良好")
            else:
                print(f"  ⚠️  README.md 内容较少 ({size} bytes)")
                self.warnings.append("README.md 内容可能不完整")
        else:
            print("  ❌ README.md 不存在")
            self.issues.append("README.md 缺失")

        return True

    def generate_report(self):
        """生成检查报告"""
        print("\n" + "=" * 70)
        print("📊 检查报告")
        print("=" * 70)

        print(f"\n✅ 通过项: {len(self.passed)}")
        print(f"⚠️  警告项: {len(self.warnings)}")
        print(f"❌ 问题项: {len(self.issues)}")

        if self.issues:
            print("\n❌ 需要修复的问题:")
            for issue in self.issues:
                print(f"  - {issue}")

        if self.warnings:
            print("\n⚠️  警告（可选）:")
            for warning in self.warnings:
                print(f"  - {warning}")

        # 计算分数
        total_checks = len(self.passed) + len(self.warnings) + len(self.issues)
        score = (len(self.passed) / total_checks * 100) if total_checks > 0 else 0

        print(f"\n📈 项目完整性评分: {score:.1f}%")

        if score >= 90:
            print("🎉 项目已达到可开源级别！")
            return 0
        elif score >= 70:
            print("✅ 项目基本完整，建议修复上述问题后开源")
            return 0
        else:
            print("⚠️  项目需要进一步完善才能开源")
            return 1

def main():
    """主函数"""
    print("=" * 70)
    print("X-Agent 项目完整性深度检查")
    print("=" * 70)
    print(f"项目根目录: {PROJECT_ROOT}")
    print()

    validator = ProjectValidator()

    # 执行所有检查
    validator.check_core_files()
    validator.check_directory_structure()
    validator.check_code_files()
    validator.check_optimization_modules()
    validator.check_temp_docs()
    validator.check_git_setup()
    validator.check_documentation_quality()

    # 生成报告
    return validator.generate_report()

if __name__ == "__main__":
    sys.exit(main())
