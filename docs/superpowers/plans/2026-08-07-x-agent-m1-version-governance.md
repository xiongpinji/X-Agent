# X-Agent M1 VERSION 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 以根 `pyproject.toml` 的 `[project].version` 为唯一权威版本，使后端、CLI、Web、桌面、扩展、移动端和四种 Partner SDK 的运行时或构建元数据一致，并让版本漂移自动阻断商业 RC。

**架构：** 新增一个默认只读的版本一致性验证器，集中声明所有静态版本面及其取值规则；现有 `release.py` 复用同一声明执行显式版本同步。Python 运行时版本由 `cli.__version__` 动态解析，Chrome `manifest.version` 使用去掉预发布后缀的数值核心，其他版本面使用完整版本。版本验证作为 Codex/Hermes 矩阵 required 类别进入现有最终 RC 聚合链。

**技术栈：** Python 3.11、`tomllib`、JSON、正则表达式、pytest、npm package-lock v3、Cargo/Tauri、GitHub Actions。

---

## 责任边界

本计划只修改以下文件：

- 新增 `scripts/version_consistency.py`：版本面声明、读取、比较、显式同步函数和只读 CLI。
- 新增 `tests/test_version_consistency.py`：验证器、运行时版本和当前仓库一致性测试。
- 修改 `scripts/release.py`：复用版本面声明同步所有静态版本，不再只更新 Web。
- 新增 `tests/test_release_version_sync.py`：验证 release 同步完整、dry-run 不写入、重复执行幂等。
- 修改 `backend/app/main.py`、`backend/app/api/health.py`、`backend/app/api/agents.py`：删除手写项目版本回退值，复用动态版本。
- 修改 Web、Desktop、Extension、Mobile 的 package/lock/manifest/Cargo/Tauri 版本元数据。
- 修改 Python、JavaScript、Go、Java Partner SDK 的版本常量和 JS lockfile。
- 修改 `scripts/codex_hermes_gap_matrix.py`、`tests/test_codex_hermes_gap_matrix.py`：增加 required `version_governance` 类别。
- 修改 `.github/workflows/commercial-rc.yml`、`scripts/rc_ci_contract.py`、`tests/test_rc_ci_contract.py`：显式运行并校验版本门禁。

不修改历史发布说明中的示例版本，不重写 `desktop/PROJECT_SUMMARY.md`、各 SDK changelog 或安装示例；这些叙事文档是否更新由发布说明任务决定。`backend/local/__init__.py` 的 `1.0.0` 是独立本地模块协议版本，不纳入产品版本面。

## 受控版本面

完整版本 `0.4.0-alpha` 必须覆盖：

- `frontend/package.json` 与 `frontend/package-lock.json` 的根包版本。
- `desktop/frontend/package.json` 与 `desktop/frontend/package-lock.json` 的根包版本。
- `desktop/Cargo.toml` 的 `[package].version`。
- `desktop/tauri.conf.json` 的 `package.version`。
- `extension/package.json`、`extension/package-lock.json`、`extension/manifest.json:version_name`。
- `mobile/package.json` 与 `mobile/package-lock.json`。
- `sdks/python/xagent_partner.py:__version__`。
- `sdks/javascript/package.json`、`sdks/javascript/package-lock.json`、`sdks/javascript/xagent-partner.ts:VERSION`。
- `sdks/go/xagent.go:Version`。
- `sdks/java/PartnerClient.java:VERSION`。

数值核心 `0.4.0` 只覆盖 `extension/manifest.json:version`，满足 Chrome Manifest 版本格式。后端 OpenAPI、deploy readiness、developer portal 与 CLI 使用动态解析值，不再维护静态副本。

## 成功标准

- `python scripts/version_consistency.py` 在一致时退出 0，在任一受控版本漂移时退出 1，且不写文件。
- `python scripts/release.py --bump ...` 同步所有受控静态版本；`dry_run=True` 不修改任何文件。
- `cli.__version__`、FastAPI `app.version`、deploy readiness 默认版本和 developer portal 版本等于根 `pyproject.toml`。
- Chrome `manifest.version == 0.4.0` 且 `version_name == 0.4.0-alpha`。
- Codex/Hermes 矩阵包含 required `version_governance`，版本漂移会使矩阵和最终 RC 门禁失败。
- Commercial RC workflow 显式运行版本验证，CI contract 能检测命令或测试被删除。

### 任务 1：建立只读版本一致性验证器

**文件：**

- 新增：`tests/test_version_consistency.py`
- 新增：`scripts/version_consistency.py`

- [ ] **步骤 1：先写纯函数和 CLI 失败测试**

创建 `tests/test_version_consistency.py`，先覆盖三条不依赖当前仓库是否一致的契约：

```python
from __future__ import annotations

import json
from pathlib import Path

from scripts import version_consistency as versions


def test_expected_version_uses_numeric_core_for_chrome_manifest() -> None:
    assert versions.expected_version("0.4.0-alpha", mode="full") == "0.4.0-alpha"
    assert versions.expected_version("0.4.0-alpha", mode="numeric_core") == "0.4.0"


def test_compare_claims_reports_exact_drift() -> None:
    claims = [
        versions.VersionClaim("web", "frontend/package.json", "0.3.0-alpha", "0.4.0-alpha"),
        versions.VersionClaim("chrome", "extension/manifest.json:version", "0.4.0", "0.4.0"),
    ]

    report = versions.build_report("0.4.0-alpha", claims)

    assert report["status"] == "failed"
    assert report["drifts"] == [
        {
            "name": "web",
            "location": "frontend/package.json",
            "actual": "0.3.0-alpha",
            "expected": "0.4.0-alpha",
        }
    ]


def test_write_report_is_not_exposed_by_cli(tmp_path: Path, capsys) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text('[project]\nversion = "0.4.0-alpha"\n', encoding="utf-8")

    exit_code = versions.main(["--root", str(root)])

    assert exit_code == 1
    assert json.loads(capsys.readouterr().out)["status"] == "failed"
    assert list(root.iterdir()) == [root / "pyproject.toml"]
```

第三条测试在空版本面仓库上必须失败并输出 JSON，但不得创建 report 或同步文件。

- [ ] **步骤 2：运行并确认模块不存在或测试失败**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_version_consistency.py -o addopts= -p no:cov -q
```

预期：因 `scripts.version_consistency` 尚不存在而在收集阶段失败。

- [ ] **步骤 3：实现数据结构、目标声明和只读 CLI**

在 `scripts/version_consistency.py` 定义：

```python
@dataclass(frozen=True)
class VersionSpec:
    name: str
    path: str
    kind: str
    selector: tuple[str, ...] | str
    mode: str = "full"


@dataclass(frozen=True)
class VersionClaim:
    name: str
    location: str
    actual: str | None
    expected: str
```

`STATIC_VERSION_SPECS` 必须逐项声明“受控版本面”中的 23 个取值；package-lock 的 selector 使用 `("version",)` 和 `("packages", "", "version")` 两条 claim，不能只检查根字段。支持三种读取方式：

```python
STATIC_VERSION_SPECS = (
    VersionSpec("web_package", "frontend/package.json", "json", ("version",)),
    VersionSpec("web_lock", "frontend/package-lock.json", "json", ("version",)),
    VersionSpec("web_lock_root", "frontend/package-lock.json", "json", ("packages", "", "version")),
    VersionSpec("desktop_web_package", "desktop/frontend/package.json", "json", ("version",)),
    VersionSpec("desktop_web_lock", "desktop/frontend/package-lock.json", "json", ("version",)),
    VersionSpec("desktop_web_lock_root", "desktop/frontend/package-lock.json", "json", ("packages", "", "version")),
    VersionSpec("desktop_cargo", "desktop/Cargo.toml", "toml", ("package", "version")),
    VersionSpec("desktop_tauri", "desktop/tauri.conf.json", "json", ("package", "version")),
    VersionSpec("extension_package", "extension/package.json", "json", ("version",)),
    VersionSpec("extension_lock", "extension/package-lock.json", "json", ("version",)),
    VersionSpec("extension_lock_root", "extension/package-lock.json", "json", ("packages", "", "version")),
    VersionSpec("extension_manifest_name", "extension/manifest.json", "json", ("version_name",)),
    VersionSpec("extension_manifest_numeric", "extension/manifest.json", "json", ("version",), "numeric_core"),
    VersionSpec("mobile_package", "mobile/package.json", "json", ("version",)),
    VersionSpec("mobile_lock", "mobile/package-lock.json", "json", ("version",)),
    VersionSpec("mobile_lock_root", "mobile/package-lock.json", "json", ("packages", "", "version")),
    VersionSpec("python_sdk", "sdks/python/xagent_partner.py", "regex", r'^__version__\s*=\s*"([^"]+)"'),
    VersionSpec("javascript_sdk_package", "sdks/javascript/package.json", "json", ("version",)),
    VersionSpec("javascript_sdk_lock", "sdks/javascript/package-lock.json", "json", ("version",)),
    VersionSpec("javascript_sdk_lock_root", "sdks/javascript/package-lock.json", "json", ("packages", "", "version")),
    VersionSpec("javascript_sdk_source", "sdks/javascript/xagent-partner.ts", "regex", r"^export const VERSION = '([^']+)';"),
    VersionSpec("go_sdk", "sdks/go/xagent.go", "regex", r'^const Version = "([^"]+)"'),
    VersionSpec("java_sdk", "sdks/java/PartnerClient.java", "regex", r'^\s*public static final String VERSION = "([^"]+)";'),
)
```

- `json`：按 selector tuple 读取嵌套字段。
- `toml`：用 `tomllib` 读取 `desktop/Cargo.toml` 的 `("package", "version")`。
- `regex`：对 Python/TypeScript/Go/Java 常量使用带一个捕获组的完整行正则。

权威版本读取必须使用：

```python
with (root / "pyproject.toml").open("rb") as handle:
    return str(tomllib.load(handle)["project"]["version"])
```

`expected_version()` 只允许 `full` 和 `numeric_core`；未知 mode 立即 `ValueError`。`build_report()` 输出固定 schema：

```python
{
    "schema_version": "2026-08-07.xagent-version-consistency.v1",
    "status": "passed" if not drifts else "failed",
    "authoritative_version": authoritative_version,
    "source": "pyproject.toml:[project].version",
    "claims": [asdict(claim) for claim in claims],
    "drifts": drifts,
}
```

`main(argv: list[str] | None = None)` 只接受 `--root`，把完整报告写到 stdout，并按 passed/failed 返回 0/1；不要增加 `--write` 或自动修复参数。

- [ ] **步骤 4：运行验证器单元测试**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_version_consistency.py -o addopts= -p no:cov -q
.\venv\Scripts\python.exe -m ruff check scripts/version_consistency.py tests/test_version_consistency.py
```

预期：三条基础测试通过。

- [ ] **步骤 5：提交任务 1**

```powershell
git add -- scripts/version_consistency.py tests/test_version_consistency.py
git commit -m "feat: 增加只读版本一致性门禁"
```

### 任务 2：让 Python 运行时版本复用权威解析值

**文件：**

- 修改：`tests/test_version_consistency.py`
- 修改：`backend/app/main.py`
- 修改：`backend/app/api/health.py`
- 修改：`backend/app/api/agents.py`
- 验证但不修改：`cli/__init__.py`

- [ ] **步骤 1：写运行时失败测试**

在 `tests/test_version_consistency.py` 增加：

```python
def test_python_runtime_versions_resolve_from_pyproject(monkeypatch) -> None:
    monkeypatch.delenv("XAGENT_VERSION", raising=False)
    authoritative = versions.read_authoritative_version(versions.ROOT)

    from cli import __version__
    from backend.app.main import app

    assert __version__ == authoritative
    assert app.version == authoritative


def test_backend_version_surfaces_do_not_embed_release_literal() -> None:
    main = (versions.ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    health = (versions.ROOT / "backend/app/api/health.py").read_text(encoding="utf-8")
    agents = (versions.ROOT / "backend/app/api/agents.py").read_text(encoding="utf-8")

    assert "version=PROJECT_VERSION" in main
    assert 'os.environ.get("XAGENT_VERSION", PROJECT_VERSION)' in health
    assert '"version": PROJECT_VERSION' in agents
    assert 'version="0.3.0-alpha"' not in main
```

- [ ] **步骤 2：运行并确认 FastAPI 与源码契约失败**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_version_consistency.py -o addopts= -p no:cov -q
```

预期：CLI 断言通过；FastAPI 仍报告 `0.3.0-alpha`，三个动态源码断言失败。

- [ ] **步骤 3：做最小运行时修改**

在三个 backend 文件各自的顶层导入区增加：

```python
from cli import __version__ as PROJECT_VERSION
```

然后只替换三个项目版本字段：

```python
# backend/app/main.py
version=PROJECT_VERSION,

# backend/app/api/health.py
version = os.environ.get("XAGENT_VERSION", PROJECT_VERSION)

# backend/app/api/agents.py
"version": PROJECT_VERSION,
```

不要改动 `backend/local/__init__.py`，不要删除 deploy readiness 的显式环境覆盖。

- [ ] **步骤 4：运行 Python 运行时回归**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_version_consistency.py tests/test_api.py -o addopts= -p no:cov -q
.\venv\Scripts\python.exe -m ruff check backend/app/main.py backend/app/api/health.py backend/app/api/agents.py
```

预期：版本测试通过；API 回归测试无新增失败。

- [ ] **步骤 5：提交任务 2**

```powershell
git add -- backend/app/main.py backend/app/api/health.py backend/app/api/agents.py tests/test_version_consistency.py
git commit -m "fix: 统一后端运行时版本来源"
```

### 任务 3：对齐全部静态构建与 SDK 版本面

**文件：**

- 修改：`tests/test_version_consistency.py`
- 修改：`frontend/package.json`
- 修改：`frontend/package-lock.json`
- 修改：`desktop/frontend/package.json`
- 修改：`desktop/frontend/package-lock.json`
- 修改：`desktop/Cargo.toml`
- 修改：`desktop/tauri.conf.json`
- 修改：`extension/package.json`
- 修改：`extension/package-lock.json`
- 修改：`extension/manifest.json`
- 修改：`mobile/package.json`
- 修改：`mobile/package-lock.json`
- 修改：`sdks/python/xagent_partner.py`
- 修改：`sdks/javascript/package.json`
- 修改：`sdks/javascript/package-lock.json`
- 修改：`sdks/javascript/xagent-partner.ts`
- 修改：`sdks/go/xagent.go`
- 修改：`sdks/java/PartnerClient.java`

- [ ] **步骤 1：增加当前仓库集成失败测试**

```python
def test_repository_version_claims_match_pyproject() -> None:
    report = versions.validate_repository(versions.ROOT)

    assert report["status"] == "passed", json.dumps(report["drifts"], ensure_ascii=False, indent=2)
    assert report["authoritative_version"] == "0.4.0-alpha"
```

- [ ] **步骤 2：运行并保存真实漂移清单**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_version_consistency.py -o addopts= -p no:cov -q
.\venv\Scripts\python.exe scripts/version_consistency.py
```

预期：退出 1；漂移清单包含当前 `0.1.0`、`0.2.0-alpha`、`0.3.0-alpha` 版本面，不包含依赖包版本或历史文档示例。

- [ ] **步骤 3：精确同步静态版本**

把所有“完整版本”受控面改为 `0.4.0-alpha`。对五个 package-lock 文件同时修改顶层 `version` 与 `packages[""]["version"]`，不要改依赖包版本。

扩展 manifest 必须是：

```json
{
  "version": "0.4.0",
  "version_name": "0.4.0-alpha"
}
```

这里只表示要修改的两个现有字段，不要重建或截断 manifest。SDK 常量必须分别是：

```python
__version__ = "0.4.0-alpha"
```

```typescript
export const VERSION = '0.4.0-alpha';
```

```go
const Version = "0.4.0-alpha"
```

```java
public static final String VERSION = "0.4.0-alpha";
```

同步现有行尾注释，使其只陈述“与根 pyproject.toml 对齐”，不再声称某个 SDK 文件是全仓单一事实源。

- [ ] **步骤 4：验证版本面和构建元数据**

```powershell
.\venv\Scripts\python.exe scripts/version_consistency.py
.\venv\Scripts\python.exe -m pytest tests/test_version_consistency.py -o addopts= -p no:cov -q
npm run type-check --prefix frontend
npm run build --prefix sdks/javascript
cargo metadata --manifest-path desktop/Cargo.toml --no-deps --format-version 1 | Out-Null
git diff --check
```

预期：版本验证退出 0；Python 测试、Web type-check、JS SDK build 和 Cargo metadata 全部通过。

- [ ] **步骤 5：提交任务 3**

```powershell
git add -- frontend/package.json frontend/package-lock.json desktop/frontend/package.json desktop/frontend/package-lock.json desktop/Cargo.toml desktop/tauri.conf.json extension/package.json extension/package-lock.json extension/manifest.json mobile/package.json mobile/package-lock.json sdks/python/xagent_partner.py sdks/javascript/package.json sdks/javascript/package-lock.json sdks/javascript/xagent-partner.ts sdks/go/xagent.go sdks/java/PartnerClient.java tests/test_version_consistency.py
git commit -m "fix: 对齐全仓产品版本元数据"
```

### 任务 4：让 release.py 使用同一版本面声明同步

**文件：**

- 新增：`tests/test_release_version_sync.py`
- 修改：`scripts/version_consistency.py`
- 修改：`scripts/release.py`

- [ ] **步骤 1：写 dry-run、完整同步和幂等失败测试**

创建 `tests/test_release_version_sync.py`。使用 `versions.STATIC_VERSION_SPECS` 把每个受控文件复制到临时仓库，并复制根 `pyproject.toml`；不要手写简化版目标清单。

测试辅助函数固定为：

```python
def _copy_version_fixture(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    for relative in {"pyproject.toml", *versions.static_version_paths()}:
        source = versions.ROOT / relative
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
    return root


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }
```

核心测试为：

```python
def test_release_update_synchronizes_every_version_claim(tmp_path: Path) -> None:
    root = _copy_version_fixture(tmp_path)

    updated = release.update_version("0.4.1-alpha", root=root)
    report = versions.validate_repository(root)

    assert report["status"] == "passed"
    assert report["authoritative_version"] == "0.4.1-alpha"
    assert set(updated) == {"pyproject.toml", *versions.static_version_paths()}


def test_release_update_dry_run_does_not_write(tmp_path: Path) -> None:
    root = _copy_version_fixture(tmp_path)
    before = _snapshot(root)

    updated = release.update_version("0.4.1-alpha", dry_run=True, root=root)

    assert updated
    assert _snapshot(root) == before


def test_release_update_is_idempotent(tmp_path: Path) -> None:
    root = _copy_version_fixture(tmp_path)
    release.update_version("0.4.1-alpha", root=root)

    assert release.update_version("0.4.1-alpha", root=root) == []
```

- [ ] **步骤 2：运行并确认现有签名与同步范围失败**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_release_version_sync.py -o addopts= -p no:cov -q
```

预期：`update_version` 不接受 `root`，且当前只同步根 pyproject、Web package 和 changelog。

- [ ] **步骤 3：实现显式同步函数**

在 `version_consistency.py` 增加：

```python
def synchronize_static_versions(root: Path, version: str, *, dry_run: bool = False) -> list[str]:
    """Synchronize declared static claims; the verifier CLI never calls this function."""
```

该函数必须按 `STATIC_VERSION_SPECS` 修改 JSON/TOML/regex 目标：

- JSON 保持 key 顺序、2 空格缩进、UTF-8 和结尾换行。
- TOML/regex 只替换捕获组对应值，保留相邻内容。
- 同一文件有多个 claim 时只写一次。
- 实际内容已等于期望时不计入 `updated`。
- `dry_run=True` 返回将变更的相对路径但不写盘。

把 `release.update_version` 签名改为：

```python
def update_version(new_version: str, *, dry_run: bool = False, root: Path = ROOT) -> list[str]:
```

函数先更新 `root / "pyproject.toml"`，再调用 `synchronize_static_versions(root, new_version, dry_run=dry_run)`，最后处理 `root / "CHANGELOG.md"`。删除原来只处理 `FRONTEND_PKG` 的专用代码，避免双写。

- [ ] **步骤 4：运行 release 同步回归**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_release_version_sync.py tests/test_version_consistency.py -o addopts= -p no:cov -q
.\venv\Scripts\python.exe scripts/release.py --show
.\venv\Scripts\python.exe -m ruff check scripts/release.py scripts/version_consistency.py tests/test_release_version_sync.py
```

预期：测试通过；`--show` 输出 `0.4.0-alpha` 且不修改工作树。

- [ ] **步骤 5：提交任务 4**

```powershell
git add -- scripts/release.py scripts/version_consistency.py tests/test_release_version_sync.py
git commit -m "feat: 扩展发布版本同步范围"
```

### 任务 5：把版本验证接入竞品矩阵和商业 RC CI

**文件：**

- 修改：`tests/test_codex_hermes_gap_matrix.py`
- 修改：`scripts/codex_hermes_gap_matrix.py`
- 修改：`tests/test_rc_ci_contract.py`
- 修改：`scripts/rc_ci_contract.py`
- 修改：`.github/workflows/commercial-rc.yml`

- [ ] **步骤 1：写 required 类别和 CI token 失败测试**

把矩阵类别期望改为：

```python
assert [check.category for check in build_checks()] == [
    "first_release",
    "web_chat",
    "telegram_loop",
    "github_issue_to_pr",
    "skill_curator",
    "gateway",
    "installer",
    "version_governance",
    "frontend",
    "docs",
]
```

并增加：

```python
def test_version_governance_is_required() -> None:
    check = next(check for check in build_checks() if check.category == "version_governance")
    assert check.required is True
    assert check.command == ["python", "scripts/version_consistency.py"]
    assert check.evidence_paths == (
        "scripts/version_consistency.py",
        "tests/test_version_consistency.py",
    )
```

在 `tests/test_rc_ci_contract.py` 增加一个删除 `python scripts/version_consistency.py` 后 contract 失败的用例，断言 finding id 为 `release_gate_commands`。

- [ ] **步骤 2：运行并确认类别与 CI 契约失败**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_codex_hermes_gap_matrix.py tests/test_rc_ci_contract.py -o addopts= -p no:cov -q
```

预期：矩阵缺少 `version_governance`；CI contract 尚不要求版本命令。

- [ ] **步骤 3：接入矩阵与 workflow**

在 `build_checks()` 的 installer 后增加：

```python
MatrixCheck(
    category="version_governance",
    name="repository version single-source contract",
    command=["python", "scripts/version_consistency.py"],
    evidence_paths=("scripts/version_consistency.py", "tests/test_version_consistency.py"),
),
```

在 Commercial RC workflow 的 gap matrix 前增加 blocking 步骤：

```yaml
- name: Version consistency
  run: python scripts/version_consistency.py
```

同时把 `tests/test_version_consistency.py`、`tests/test_release_version_sync.py` 加入 targeted RC pytest group。

在 `rc_ci_contract.py` 的三个位置加入对应 token：

- static scripts：`scripts/version_consistency.py`。
- targeted tests：`tests/test_version_consistency.py` 与 `tests/test_release_version_sync.py`。
- release gate commands：`python scripts/version_consistency.py`。

- [ ] **步骤 4：验证矩阵和 CI contract**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_codex_hermes_gap_matrix.py tests/test_rc_ci_contract.py tests/test_version_consistency.py tests/test_release_version_sync.py -o addopts= -p no:cov -q
.\venv\Scripts\python.exe scripts/rc_ci_contract.py
```

预期：全部通过；CI contract 状态为 `passed`。

- [ ] **步骤 5：提交任务 5**

```powershell
git add -- scripts/codex_hermes_gap_matrix.py tests/test_codex_hermes_gap_matrix.py .github/workflows/commercial-rc.yml scripts/rc_ci_contract.py tests/test_rc_ci_contract.py
git commit -m "ci: 将版本一致性纳入商业 RC"
```

### 任务 6：在干净 HEAD 上验证 VERSION 闭环

**文件：**

- 运行时生成（不提交）：`.xagent_runtime/reports/codex-hermes-gap-closure.json`
- 运行时生成（不提交）：`.xagent_runtime/reports/rc-ci-contract.json`
- 运行时生成（不提交）：`.xagent_runtime/reports/rc-final-gate.json`

- [ ] **步骤 1：确认所有版本治理提交完成且工作树干净**

```powershell
git status --short
git rev-parse HEAD
```

预期：工作树无输出。存在无关用户改动时停止生成发布证据，不重置或暂存这些改动。

- [ ] **步骤 2：运行版本、构建和静态门禁**

```powershell
.\venv\Scripts\python.exe scripts/version_consistency.py
.\venv\Scripts\python.exe -m pytest tests/test_version_consistency.py tests/test_release_version_sync.py tests/test_codex_hermes_gap_matrix.py tests/test_rc_ci_contract.py -o addopts= -p no:cov -q
.\venv\Scripts\python.exe -m ruff check scripts/version_consistency.py scripts/release.py scripts/codex_hermes_gap_matrix.py scripts/rc_ci_contract.py tests/test_version_consistency.py tests/test_release_version_sync.py
npm run type-check --prefix frontend
npm run build --prefix sdks/javascript
cargo metadata --manifest-path desktop/Cargo.toml --no-deps --format-version 1 | Out-Null
git diff --check
```

预期：所有命令退出 0，版本报告无 drift。

- [ ] **步骤 3：重建绑定当前 HEAD 的竞品矩阵**

```powershell
.\venv\Scripts\python.exe scripts/codex_hermes_gap_matrix.py --write-report
```

预期：十个 required 类别全部 `passed`，其中 `version_governance=passed`；报告 SHA 等于步骤 1 的 HEAD，`is_dirty=false`，`full_parity_claimed=false`。

- [ ] **步骤 4：运行聚合链**

```powershell
.\venv\Scripts\python.exe scripts/rc_ci_contract.py
.\venv\Scripts\python.exe scripts/rc_final_gate.py
```

预期：版本一致性不再导致 CI contract、gap matrix 或 final gate 失败。真实外部 owner gate 仍按原状态保留。

- [ ] **步骤 5：交付版本矩阵**

交付时报告根版本、所有受控版本面数量、Chrome numeric/full 双字段、验证测试计数、矩阵 `version_governance` 状态和最终门禁状态。不要把历史示例版本误报为构建版本漂移。
