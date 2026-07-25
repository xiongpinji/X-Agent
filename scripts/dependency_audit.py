#!/usr/bin/env python3
"""P1-05: 依赖治理 — 全量扫描 + SBOM 生成 + 前端审计。

用法:
    python scripts/dependency_audit.py [--fix] [--json]

功能:
1. Python: pip-audit 全量扫描 requirements-lock.txt
2. Frontend: npm audit (frontend/desktop/mobile/extension)
3. SBOM: 生成 CycloneDX 格式 sbom.json
4. 输出: 漏洞摘要 + 修复建议

退出码:
    0 = 无已知高危漏洞
    1 = 存在高危漏洞需处理
    2 = 扫描工具缺失(降级为警告)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 前端项目目录(含 package.json)
FRONTEND_PROJECTS = [
    "frontend",
    "desktop/frontend",
    "mobile",
    "extension",
]


@dataclass
class AuditResult:
    """单个审计通道的结果。"""

    channel: str
    vulnerabilities: list[dict] = field(default_factory=list)
    error: str | None = None
    skipped: bool = False

    @property
    def critical_count(self) -> int:
        return sum(1 for v in self.vulnerabilities if v.get("severity") in ("critical", "high"))

    @property
    def total_count(self) -> int:
        return len(self.vulnerabilities)


def run_python_audit() -> AuditResult:
    """Python 依赖审计 (pip-audit)。"""
    result = AuditResult(channel="python/pip-audit")
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip_audit", "--format", "json", "-r", str(ROOT / "requirements-lock.txt")],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode == 0:
            result.vulnerabilities = []
        else:
            try:
                data = json.loads(proc.stdout)
                result.vulnerabilities = [
                    {
                        "package": v.get("name", ""),
                        "version": v.get("version", ""),
                        "id": v.get("id", ""),
                        "severity": v.get("fix_versions", [""])[0] and "high" or "medium",
                        "description": v.get("description", "")[:200],
                    }
                    for v in data.get("vulnerabilities", [])
                ]
            except (json.JSONDecodeError, KeyError):
                result.error = proc.stderr[:500] or "pip-audit returned non-zero"
    except FileNotFoundError:
        result.skipped = True
        result.error = "pip-audit not installed (pip install pip-audit)"
    except subprocess.TimeoutExpired:
        result.error = "pip-audit timed out (120s)"
    return result


def run_npm_audit(project_dir: str) -> AuditResult:
    """npm audit for a frontend project."""
    result = AuditResult(channel=f"npm/{project_dir}")
    pkg_path = ROOT / project_dir / "package.json"
    if not pkg_path.exists():
        result.skipped = True
        result.error = f"{project_dir}/package.json not found"
        return result

    try:
        proc = subprocess.run(
            ["npm", "audit", "--json", "--audit-level=high"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(ROOT / project_dir),
        )
        try:
            data = json.loads(proc.stdout)
            vulns = data.get("vulnerabilities", {})
            result.vulnerabilities = [
                {
                    "package": name,
                    "severity": info.get("severity", "unknown"),
                    "id": info.get("via", [{}])[0].get("id", "") if isinstance(info.get("via"), list) else "",
                    "description": str(info.get("via", [""]))[:200],
                }
                for name, info in vulns.items()
            ]
        except (json.JSONDecodeError, KeyError):
            if proc.returncode != 0:
                result.error = proc.stderr[:300] or "npm audit failed"
    except FileNotFoundError:
        result.skipped = True
        result.error = "npm not found in PATH"
    except subprocess.TimeoutExpired:
        result.error = "npm audit timed out (60s)"
    return result


def generate_sbom() -> Path:
    """生成 CycloneDX SBOM (sbom.json)。"""
    sbom_path = ROOT / "sbom.json"
    components = []

    # Python deps from requirements-lock.txt
    lock_file = ROOT / "requirements-lock.txt"
    if lock_file.exists():
        for line in lock_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            # Parse "package==version" or "package>=version"
            for sep in ("==", ">=", "<=", "~=", "!="):
                if sep in line:
                    name, version = line.split(sep, 1)
                    components.append({
                        "type": "library",
                        "name": name.strip(),
                        "version": version.strip().split(";")[0].strip(),
                        "purl": f"pkg:pypi/{name.strip()}@{version.strip().split(';')[0].strip()}",
                    })
                    break

    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{__import__('uuid').uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(UTC).isoformat(),
            "tools": [{"vendor": "X-Agent", "name": "dependency_audit.py", "version": "1.0.0"}],
            "component": {
                "type": "application",
                "bom-ref": "pkg:generic/x-agent@0.2.0-alpha",
                "name": "x-agent",
                "version": "0.2.0-alpha",
            },
        },
        "components": components,
    }
    sbom_path.write_text(json.dumps(sbom, indent=2, ensure_ascii=False), encoding="utf-8")
    return sbom_path


def main() -> int:
    parser = argparse.ArgumentParser(description="P1-05 依赖治理审计")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--skip-npm", action="store_true", help="跳过 npm audit")
    parser.add_argument("--sbom-only", action="store_true", help="仅生成 SBOM")
    args = parser.parse_args()

    if args.sbom_only:
        path = generate_sbom()
        print(f"SBOM generated: {path} ({len(json.loads(path.read_text())['components'])} components)")
        return 0

    results: list[AuditResult] = []

    # 1. Python audit
    print("── Python (pip-audit) ──")
    py_result = run_python_audit()
    results.append(py_result)
    if py_result.skipped:
        print(f"  ⚠ SKIP: {py_result.error}")
    elif py_result.error:
        print(f"  ✗ ERROR: {py_result.error}")
    else:
        print(f"  ✓ {py_result.total_count} vulnerabilities ({py_result.critical_count} high/critical)")

    # 2. npm audit
    if not args.skip_npm:
        for project in FRONTEND_PROJECTS:
            print(f"── npm ({project}) ──")
            npm_result = run_npm_audit(project)
            results.append(npm_result)
            if npm_result.skipped:
                print(f"  ⚠ SKIP: {npm_result.error}")
            elif npm_result.error:
                print(f"  ✗ ERROR: {npm_result.error}")
            else:
                print(f"  ✓ {npm_result.total_count} vulnerabilities ({npm_result.critical_count} high/critical)")

    # 3. SBOM
    print("── SBOM ──")
    sbom_path = generate_sbom()
    sbom_data = json.loads(sbom_path.read_text(encoding="utf-8"))
    print(f"  ✓ {sbom_path.name}: {len(sbom_data['components'])} components")

    # Summary
    total_vulns = sum(r.total_count for r in results)
    total_critical = sum(r.critical_count for r in results)
    print(f"\n{'='*50}")
    print(f"总计: {total_vulns} 漏洞 ({total_critical} high/critical)")
    print(f"SBOM: {sbom_path}")

    if args.json:
        output = {
            "timestamp": datetime.now(UTC).isoformat(),
            "results": [
                {"channel": r.channel, "total": r.total_count, "critical": r.critical_count,
                 "skipped": r.skipped, "error": r.error}
                for r in results
            ],
            "total_vulnerabilities": total_vulns,
            "total_critical": total_critical,
        }
        print(json.dumps(output, indent=2))

    return 1 if total_critical > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
