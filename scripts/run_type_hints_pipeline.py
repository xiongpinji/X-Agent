#!/usr/bin/env python3
"""
类型提示补充完整流程 - Complete Type Hints Enhancement Pipeline
1. 分析当前覆盖率
2. 补充缺失的类型提示
3. 启用mypy strict mode验证
4. 生成报告
"""

import subprocess
import sys
from pathlib import Path
from typing import Tuple


def run_command(cmd: list, description: str) -> Tuple[int, str]:
    """运行命令并返回结果"""
    print(f"\n{'=' * 100}")
    print(f"执行: {description}")
    print(f"{'=' * 100}")
    print(f"命令: {' '.join(cmd)}\n")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        return result.returncode, result.stdout
    except subprocess.TimeoutExpired:
        print(f"命令超时: {description}")
        return 1, ""
    except Exception as e:
        print(f"执行错误: {e}")
        return 1, ""


def main():
    """主函数"""
    project_root = Path(__file__).parent.parent

    print("\n" + "=" * 100)
    print("类型提示补充完整流程 - Complete Type Hints Enhancement Pipeline")
    print("=" * 100)
    print()

    # 步骤1: 分析当前覆盖率
    print("\n[步骤 1/4] 分析当前类型提示覆盖率...")
    analyze_script = project_root / "scripts" / "analyze_type_hints_coverage.py"
    if analyze_script.exists():
        run_command(
            [sys.executable, str(analyze_script)],
            "分析类型提示覆盖率"
        )
    else:
        print(f"分析脚本不存在: {analyze_script}")

    # 步骤2: 补充类型提示
    print("\n[步骤 2/4] 补充缺失的类型提示...")
    enhance_script = project_root / "scripts" / "enhance_type_hints.py"
    if enhance_script.exists():
        returncode, output = run_command(
            [sys.executable, str(enhance_script)],
            "补充类型提示"
        )
        if returncode != 0:
            print(f"警告: 类型提示补充过程返回非零状态码: {returncode}")
    else:
        print(f"增强脚本不存在: {enhance_script}")

    # 步骤3: 再次分析覆盖率
    print("\n[步骤 3/4] 验证类型提示覆盖率...")
    if analyze_script.exists():
        run_command(
            [sys.executable, str(analyze_script)],
            "验证类型提示覆盖率"
        )

    # 步骤4: 运行mypy验证
    print("\n[步骤 4/4] 运行mypy strict mode验证...")
    mypy_config = project_root / "mypy.ini"
    backend_dir = project_root / "backend"

    if backend_dir.exists():
        cmd = [sys.executable, "-m", "mypy", "--config-file", str(mypy_config), str(backend_dir)]
        returncode, output = run_command(cmd, "mypy strict mode验证")

        # 解析mypy输出
        if "error:" in output.lower():
            error_count = output.lower().count("error:")
            print(f"\n发现 {error_count} 个类型错误")
        else:
            print("\n✓ mypy验证通过！")
    else:
        print(f"backend目录不存在: {backend_dir}")

    # 最终报告
    print("\n" + "=" * 100)
    print("完整流程执行完成")
    print("=" * 100)
    print("""
下一步建议:
1. 检查mypy报告中的错误
2. 根据错误信息修复类型提示
3. 运行测试套件确保功能正常
4. 提交代码变更

相关文件:
- mypy.ini: mypy配置文件
- scripts/analyze_type_hints_coverage.py: 覆盖率分析工具
- scripts/enhance_type_hints.py: 类型提示补充工具
""")
    print("=" * 100)
    print()


if __name__ == "__main__":
    main()
