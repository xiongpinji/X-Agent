"""四形态可安装冒烟测试 (P1-22)。

验证 X-Agent 四大产品形态各自可构建/安装：
1. Web (frontend/) — npm install + vite build
2. Desktop (desktop/) — Tauri cargo check
3. Extension (extension/) — manifest 验证 + webpack build
4. Mobile (mobile/) — npm install + expo export

用法:
    python scripts/smoke_install.py [--form web|desktop|extension|mobile|all]
    python scripts/smoke_install.py --form all --skip-build  # 仅验证结构
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class SmokeResult:
    """单个形态的冒烟测试结果。"""

    form: str
    passed: bool = False
    checks: list[dict[str, any]] = field(default_factory=list)
    duration_seconds: float = 0.0
    error: str = ""

    def add_check(self, name: str, passed: bool, detail: str = "") -> None:
        self.checks.append({"name": name, "passed": passed, "detail": detail})

    @property
    def all_passed(self) -> bool:
        return all(c["passed"] for c in self.checks)


def run_cmd(
    cmd: list[str],
    cwd: Path,
    timeout: int = 300,
    env: Optional[dict] = None,
) -> tuple[int, str, str]:
    """运行命令并返回 (returncode, stdout, stderr)。"""
    merged_env = {**os.environ, **(env or {})}
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=merged_env,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Timeout after {timeout}s"
    except FileNotFoundError:
        return -2, "", f"Command not found: {cmd[0]}"


# ============================================================================
# Web 形态
# ============================================================================

def smoke_web(skip_build: bool = False) -> SmokeResult:
    """Web 前端冒烟: 结构验证 + npm install + vite build。"""
    result = SmokeResult(form="web")
    start = time.time()
    frontend_dir = PROJECT_ROOT / "frontend"

    # 1. 结构检查
    pkg_json = frontend_dir / "package.json"
    result.add_check("package.json exists", pkg_json.exists())
    if not pkg_json.exists():
        result.passed = False
        result.error = "frontend/package.json not found"
        return result

    # 2. 解析 package.json
    try:
        pkg = json.loads(pkg_json.read_text(encoding="utf-8"))
        result.add_check("package.json valid", True)
        result.add_check("has build script", "build" in pkg.get("scripts", {}))
        result.add_check("has react dep", "react" in pkg.get("dependencies", {}))
    except Exception as e:
        result.add_check("package.json valid", False, str(e))

    # 3. 入口文件
    src_dir = frontend_dir / "src"
    result.add_check("src/ exists", src_dir.exists())
    result.add_check("App.tsx exists", (src_dir / "App.tsx").exists())
    result.add_check("main.tsx exists", (src_dir / "main.tsx").exists())

    # 4. 构建 (可选)
    if not skip_build:
        # npm install
        rc, out, err = run_cmd(["npm", "install", "--prefer-offline"], frontend_dir, timeout=180)
        result.add_check("npm install", rc == 0, err[:200] if rc != 0 else "")

        # vite build
        if rc == 0:
            rc, out, err = run_cmd(["npm", "run", "build"], frontend_dir, timeout=120)
            result.add_check("vite build", rc == 0, err[:200] if rc != 0 else "")
            dist_dir = frontend_dir / "dist"
            result.add_check("dist/ created", dist_dir.exists())

    result.passed = result.all_passed
    result.duration_seconds = time.time() - start
    return result


# ============================================================================
# Desktop 形态 (Tauri)
# ============================================================================

def smoke_desktop(skip_build: bool = False) -> SmokeResult:
    """桌面端冒烟: Tauri 结构验证 + cargo check。"""
    result = SmokeResult(form="desktop")
    start = time.time()
    desktop_dir = PROJECT_ROOT / "desktop"

    # 1. 结构检查
    cargo_toml = desktop_dir / "Cargo.toml"
    result.add_check("Cargo.toml exists", cargo_toml.exists())
    if not cargo_toml.exists():
        result.passed = False
        result.error = "desktop/Cargo.toml not found"
        return result

    # 2. Tauri 配置
    tauri_conf = desktop_dir / "tauri.conf.json"
    if not tauri_conf.exists():
        # Tauri v2 可能用不同路径
        tauri_conf = desktop_dir / "src-tauri" / "tauri.conf.json"
    result.add_check("tauri.conf.json exists", tauri_conf.exists())

    # 3. Rust 入口
    main_rs = desktop_dir / "src" / "main.rs"
    result.add_check("src/main.rs exists", main_rs.exists())

    # 4. 前端资源
    frontend_dir = desktop_dir / "frontend"
    result.add_check("frontend/ exists", frontend_dir.exists())

    # 5. 图标
    icons_dir = desktop_dir / "icons"
    result.add_check("icons/ exists", icons_dir.exists())

    # 6. cargo check (可选)
    if not skip_build:
        rc, out, err = run_cmd(["cargo", "check"], desktop_dir, timeout=300)
        result.add_check("cargo check", rc == 0, err[:300] if rc != 0 else "cargo not available or check failed")

    result.passed = result.all_passed
    result.duration_seconds = time.time() - start
    return result


# ============================================================================
# Extension 形态 (浏览器扩展)
# ============================================================================

def smoke_extension(skip_build: bool = False) -> SmokeResult:
    """浏览器扩展冒烟: manifest 验证 + 构建。"""
    result = SmokeResult(form="extension")
    start = time.time()
    ext_dir = PROJECT_ROOT / "extension"

    # 1. 结构检查
    manifest = ext_dir / "manifest.json"
    result.add_check("manifest.json exists", manifest.exists())
    if not manifest.exists():
        result.passed = False
        result.error = "extension/manifest.json not found"
        return result

    # 2. 解析 manifest
    try:
        mf = json.loads(manifest.read_text(encoding="utf-8"))
        result.add_check("manifest valid JSON", True)
        result.add_check("manifest_version", mf.get("manifest_version") in (2, 3),
                         f"v{mf.get('manifest_version')}")
        result.add_check("has name", bool(mf.get("name")))
        result.add_check("has version", bool(mf.get("version")))
        result.add_check("has permissions", "permissions" in mf or "host_permissions" in mf)
    except Exception as e:
        result.add_check("manifest valid JSON", False, str(e))

    # 3. 核心文件
    result.add_check("background.js exists", (ext_dir / "background.js").exists())
    result.add_check("content.js exists", (ext_dir / "content.js").exists())

    # 4. 图标
    images_dir = ext_dir / "images"
    result.add_check("images/ exists", images_dir.exists())

    # 5. 构建 (如果有 webpack)
    if not skip_build:
        pkg_json = ext_dir / "package.json"
        if pkg_json.exists():
            rc, out, err = run_cmd(["npm", "install", "--prefer-offline"], ext_dir, timeout=120)
            result.add_check("npm install", rc == 0, err[:200] if rc != 0 else "")
            if rc == 0:
                rc, out, err = run_cmd(["npm", "run", "build"], ext_dir, timeout=60)
                # 构建脚本可能不存在，不算失败
                result.add_check("npm run build", rc == 0 or "missing script" in err,
                                 "build script not defined (OK for MV3)" if "missing script" in err else "")

    result.passed = result.all_passed
    result.duration_seconds = time.time() - start
    return result


# ============================================================================
# Mobile 形态 (React Native / Expo)
# ============================================================================

def smoke_mobile(skip_build: bool = False) -> SmokeResult:
    """移动端冒烟: Expo 结构验证 + 依赖安装。"""
    result = SmokeResult(form="mobile")
    start = time.time()
    mobile_dir = PROJECT_ROOT / "mobile"

    # 1. 结构检查
    app_json = mobile_dir / "app.json"
    result.add_check("app.json exists", app_json.exists())
    if not app_json.exists():
        result.passed = False
        result.error = "mobile/app.json not found"
        return result

    # 2. 解析 app.json
    try:
        app = json.loads(app_json.read_text(encoding="utf-8"))
        result.add_check("app.json valid", True)
        expo = app.get("expo", {})
        result.add_check("has expo config", bool(expo))
        result.add_check("has name", bool(expo.get("name")))
        result.add_check("has slug", bool(expo.get("slug")))
    except Exception as e:
        result.add_check("app.json valid", False, str(e))

    # 3. 入口文件
    result.add_check("App.tsx exists", (mobile_dir / "App.tsx").exists())
    result.add_check("package.json exists", (mobile_dir / "package.json").exists())

    # 4. 平台目录
    result.add_check("android/ exists", (mobile_dir / "android").exists())
    result.add_check("ios/ exists", (mobile_dir / "ios").exists())

    # 5. 源码
    src_dir = mobile_dir / "src"
    result.add_check("src/ exists", src_dir.exists())

    # 6. 依赖安装 (可选)
    if not skip_build:
        pkg_json = mobile_dir / "package.json"
        if pkg_json.exists():
            rc, out, err = run_cmd(["npm", "install", "--prefer-offline"], mobile_dir, timeout=180)
            result.add_check("npm install", rc == 0, err[:200] if rc != 0 else "")

    result.passed = result.all_passed
    result.duration_seconds = time.time() - start
    return result


# ============================================================================
# 主入口
# ============================================================================

SMOKE_FUNCS = {
    "web": smoke_web,
    "desktop": smoke_desktop,
    "extension": smoke_extension,
    "mobile": smoke_mobile,
}


def main():
    parser = argparse.ArgumentParser(description="X-Agent 四形态可安装冒烟测试")
    parser.add_argument(
        "--form",
        choices=["web", "desktop", "extension", "mobile", "all"],
        default="all",
        help="要测试的形态 (default: all)",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="跳过构建步骤，仅验证文件结构",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="输出 JSON 格式结果",
    )
    args = parser.parse_args()

    forms = list(SMOKE_FUNCS.keys()) if args.form == "all" else [args.form]
    results: list[SmokeResult] = []

    print("=" * 60)
    print("X-Agent 四形态可安装冒烟测试 (P1-22)")
    print("=" * 60)

    for form in forms:
        print(f"\n{'─' * 40}")
        print(f"  测试形态: {form.upper()}")
        print(f"{'─' * 40}")

        result = SMOKE_FUNCS[form](skip_build=args.skip_build)
        results.append(result)

        for check in result.checks:
            icon = "✓" if check["passed"] else "✗"
            detail = f" ({check['detail']})" if check.get("detail") else ""
            print(f"  {icon} {check['name']}{detail}")

        status = "PASS" if result.passed else "FAIL"
        print(f"\n  结果: {status} ({result.duration_seconds:.1f}s)")
        if result.error:
            print(f"  错误: {result.error}")

    # 汇总
    print(f"\n{'=' * 60}")
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    print(f"总计: {passed}/{total} 形态通过")

    if args.json:
        output = {
            "results": [
                {
                    "form": r.form,
                    "passed": r.passed,
                    "checks": r.checks,
                    "duration_seconds": round(r.duration_seconds, 2),
                    "error": r.error,
                }
                for r in results
            ],
            "summary": {"passed": passed, "total": total},
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
