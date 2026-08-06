# X-Agent M1 RC-TRUTH 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 让 Codex/Hermes 差距矩阵、商业 RC CI 和最终聚合门禁基于同一提交、显式环境和现行证据路径作出可复现结论，并清除会误导审计的旧探针契约。

**架构：** 保留现有 `codex_hermes_gap_matrix.py → commercial-rc.yml → rc_final_gate.py` 链路，只增强环境固定、Git 绑定和阻断语义。矩阵报告继续声明 `full_parity_claimed=false`；最终门禁把报告中的 `git.head_sha` 与当前 HEAD 比较，并拒绝缺失、脏工作树或不一致证据。

**技术栈：** Python 3.11、pytest、FastAPI TestClient、Git、GitHub Actions YAML、现有 RC JSON 报告。

---

## 责任边界

本计划只修改以下文件：

- `scripts/codex_hermes_gap_matrix.py`：固定执行环境、修正文档证据路径、记录 HEAD 和工作树状态。
- `tests/test_codex_hermes_gap_matrix.py`：覆盖环境、路径、Git 元数据、状态和脱敏契约。
- `tests/test_settings_production_guard_p119.py`：锁定开发/生产限流默认策略。
- `scripts/rc_final_gate.py`：拒绝缺失、脏工作树和 SHA 不一致的矩阵报告。
- `tests/test_rc_final_gate.py`：补齐矩阵 Git 绑定的通过与失败用例。
- `.github/workflows/commercial-rc.yml`：把竞品矩阵从 advisory 改为 blocking。
- `scripts/rc_ci_contract.py`：机器校验矩阵步骤不得 `continue-on-error`。
- `tests/test_rc_ci_contract.py`：覆盖 CI 阻断契约。
- `_audit_probe_routes.py`、`_audit_probe_auth.py`、`_audit_probe_agentrun.py`：同步现行路由和请求体。
- `tests/test_audit_probes_contract.py`：防止旧审计探针再次漂移。
- `AUDIT_2026-08-02_独立深度审计.md`：保留当前根目录探针命令，并明确其契约已刷新。

不修改四端产品代码、不修扩展测试、不实现新的 Codex/Hermes 功能、不伪造外部生产证据。

## 成功标准

- `tests/test_codex_hermes_gap_matrix.py`、`tests/test_settings_production_guard_p119.py`、`tests/test_rc_final_gate.py`、`tests/test_rc_ci_contract.py`、`tests/test_audit_probes_contract.py` 全部通过。
- 矩阵子进程显式设置 mock LLM、空 Qdrant、关闭 E2E、开启限流；不继承同名宿主值。
- 文档检查只引用现存的 `docs/developer/reports`、`docs/concepts/planning`、`docs/developer/specs` 路径。
- 矩阵报告包含 40 位 `git.head_sha`、`git.is_dirty`、`git.status_short`，且命令输出继续脱敏。
- `rc_final_gate.py` 拒绝矩阵 SHA 缺失、SHA 不匹配和脏工作树。
- Commercial RC 工作流中的 Codex/Hermes 矩阵没有 `continue-on-error: true`。
- 三个根目录审计探针不再请求已删除路由，也不再发送 `message`/`arguments` 旧字段。
- 在干净工作树的同一 HEAD 上运行完整矩阵，所有 required 类别通过，且 `full_parity_claimed=false`。

### 任务 1：固定矩阵执行环境并修复证据路径

**文件：**

- 修改：`tests/test_codex_hermes_gap_matrix.py`
- 修改：`tests/test_settings_production_guard_p119.py`
- 修改：`scripts/codex_hermes_gap_matrix.py`

- [ ] **步骤 1：先写环境和路径失败测试**

在 `tests/test_codex_hermes_gap_matrix.py` 增加：

```python
def test_clean_env_overrides_host_values(monkeypatch) -> None:
    monkeypatch.setenv("XAGENT_QDRANT_URL", "http://stale-qdrant:6333")
    monkeypatch.setenv("XAGENT_LLM_BACKEND", "openai")
    monkeypatch.setenv("XAGENT_E2E", "1")
    monkeypatch.setenv("XAGENT_RATE_LIMIT_ENABLED", "false")

    env = matrix._clean_env()

    assert env["XAGENT_QDRANT_URL"] == ""
    assert env["XAGENT_LLM_BACKEND"] == "mock"
    assert env["XAGENT_E2E"] == "0"
    assert env["XAGENT_RATE_LIMIT_ENABLED"] == "true"


def test_docs_check_uses_current_document_tree() -> None:
    docs_check = next(check for check in build_checks() if check.category == "docs")

    assert docs_check.evidence_paths == (
        "docs/developer/reports/CODEX_HERMES_GAP_CLOSURE_REPORT.md",
        "docs/concepts/planning/IDE_EXTENSION_ROADMAP.md",
        "docs/developer/specs/vscode-extension-mvp.md",
    )
```

在 `tests/test_settings_production_guard_p119.py` 增加：

```python
class TestRateLimitModePolicy:
    def test_development_defaults_to_rate_limit_disabled(self):
        assert Settings(app_mode="development").rate_limit_active is False

    def test_production_defaults_to_rate_limit_enabled(self):
        settings = Settings(**_production_kwargs(**_POSTGRES_KWARGS))
        assert settings.rate_limit_active is True

    def test_explicit_override_wins_in_development(self):
        assert Settings(app_mode="development", rate_limit_enabled=True).rate_limit_active is True
```

- [ ] **步骤 2：运行测试并确认当前实现失败**

运行：

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_codex_hermes_gap_matrix.py tests/test_settings_production_guard_p119.py -o addopts= -p no:cov -q
```

预期：矩阵环境覆盖和现行文档路径用例失败；限流模式策略用例通过，证明问题在矩阵执行环境而不是生产默认策略。

- [ ] **步骤 3：做最小实现**

把 `_clean_env()` 的三个 `setdefault` 改为显式赋值，并增加限流值：

```python
env["XAGENT_QDRANT_URL"] = ""
env["XAGENT_LLM_BACKEND"] = "mock"
env["XAGENT_E2E"] = "0"
env["XAGENT_RATE_LIMIT_ENABLED"] = "true"
```

把 docs 检查的三条路径改为：

```python
required = [
    "docs/developer/reports/CODEX_HERMES_GAP_CLOSURE_REPORT.md",
    "docs/concepts/planning/IDE_EXTENSION_ROADMAP.md",
    "docs/developer/specs/vscode-extension-mvp.md",
]
```

同时同步 `evidence_paths`，不要保留旧路径兼容分支。

- [ ] **步骤 4：运行定向验证**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_codex_hermes_gap_matrix.py tests/test_settings_production_guard_p119.py -o addopts= -p no:cov -q
$env:XAGENT_RATE_LIMIT_ENABLED='true'; .\venv\Scripts\python.exe -m pytest tests/test_first_release_entrypoints.py tests/test_security.py -o addopts= -p no:cov -q; Remove-Item Env:XAGENT_RATE_LIMIT_ENABLED
```

预期：全部通过；第二条命令应得到 `27 passed`，不再出现登录 401/注册 400 取代 429 的矩阵假失败。

- [ ] **步骤 5：提交任务 1**

```powershell
git add -- scripts/codex_hermes_gap_matrix.py tests/test_codex_hermes_gap_matrix.py tests/test_settings_production_guard_p119.py
git commit -m "fix: 固定竞品矩阵执行环境"
```

### 任务 2：把矩阵证据绑定到 Git HEAD 和工作树

**文件：**

- 修改：`tests/test_codex_hermes_gap_matrix.py`
- 修改：`scripts/codex_hermes_gap_matrix.py`

- [ ] **步骤 1：写 Git 元数据失败测试**

增加对真实仓库的只读契约测试：

```python
def test_git_status_records_head_sha_and_dirty_flag() -> None:
    status = matrix.collect_git_status(matrix.ROOT)

    assert status["available"] is True
    assert len(status["head_sha"]) == 40
    assert status["is_dirty"] is bool(status["status_short"])
```

在 dry-run 报告测试中增加：

```python
assert report["schema_version"] == "2026-08-07.codex-hermes-gap-matrix.v2"
assert "head_sha" in report["git"]
assert "is_dirty" in report["git"]
```

- [ ] **步骤 2：运行并确认失败**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_codex_hermes_gap_matrix.py -o addopts= -p no:cov -q
```

预期：`head_sha`、`is_dirty` 和 v2 schema 断言失败。

- [ ] **步骤 3：扩展 `collect_git_status()`**

新增一次只读命令：

```python
head = subprocess.run(
    ["git", "rev-parse", "HEAD"],
    cwd=root,
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
    timeout=10,
    check=False,
)
```

返回值固定为：

```python
status_short = [line for line in status.stdout.splitlines() if line.strip()]
return {
    "available": branch.returncode == 0 and status.returncode == 0 and head.returncode == 0,
    "branch": branch.stdout.strip() if branch.returncode == 0 else None,
    "head_sha": head.stdout.strip() if head.returncode == 0 else None,
    "is_dirty": bool(status_short),
    "status_short": status_short,
}
```

异常分支也必须返回 `head_sha=None`、`is_dirty=None`、`status_short=[]`。把报告 schema 升为 `2026-08-07.codex-hermes-gap-matrix.v2`。

- [ ] **步骤 4：验证报告字段和脱敏没有回归**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_codex_hermes_gap_matrix.py -o addopts= -p no:cov -q
.\venv\Scripts\python.exe scripts/codex_hermes_gap_matrix.py --dry-run
```

预期：测试通过；dry-run 仍只打印便携命令，不输出本机 Python 绝对路径或密钥。

- [ ] **步骤 5：提交任务 2**

```powershell
git add -- scripts/codex_hermes_gap_matrix.py tests/test_codex_hermes_gap_matrix.py
git commit -m "feat: 绑定竞品矩阵 Git 证据"
```

### 任务 3：最终 RC 门禁拒绝错 SHA 和脏证据

**文件：**

- 修改：`tests/test_rc_final_gate.py`
- 修改：`scripts/rc_final_gate.py`

- [ ] **步骤 1：先让通用 fixture 携带当前 HEAD**

在 `tests/test_rc_final_gate.py` 的 `_inputs()` 中，仅修改 gap matrix fixture：

```python
"git": {
    "available": True,
    "head_sha": subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip(),
    "is_dirty": False,
    "status_short": [],
},
```

补充 `import subprocess`，并从 `scripts.rc_final_gate` 导入 `ROOT`。

- [ ] **步骤 2：增加三种失败测试**

```python
@pytest.mark.parametrize(
    ("git_payload", "message"),
    [
        ({"available": True, "is_dirty": False}, "gap matrix git.head_sha is missing"),
        ({"available": True, "head_sha": "0" * 40, "is_dirty": False}, "does not match current HEAD"),
        ({"available": True, "head_sha": None, "is_dirty": True}, "gap matrix worktree is dirty"),
    ],
)
def test_final_gate_rejects_unbound_gap_matrix(tmp_path: Path, git_payload: dict, message: str) -> None:
    inputs = _inputs(tmp_path, external_checks=[])
    payload = json.loads(inputs["gap_matrix"].read_text(encoding="utf-8"))
    current_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    if git_payload.get("is_dirty") is True:
        git_payload["head_sha"] = current_head
    payload["git"] = git_payload
    _write_json(inputs["gap_matrix"], payload)

    report = run_final_gate(inputs)

    assert report.status == "failed"
    gate = next(item for item in report.local_gates if item.name == "gap_matrix")
    assert message in str(gate.error)
```

- [ ] **步骤 3：运行并确认失败**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_rc_final_gate.py -o addopts= -p no:cov -q
```

预期：新参数化测试失败，因为当前 `_gate_from_report` 只读取 `summary.overall_status`。

- [ ] **步骤 4：实现专用 gap matrix 门禁**

在 `scripts/rc_final_gate.py` 增加 `_current_git_head()` 和 `_gap_matrix_gate()`。核心判断必须等价于：

```python
payload, error = _read_json(path)
problems = [error] if error else []
summary = (payload or {}).get("summary") or {}
git = (payload or {}).get("git") or {}
current_head = _current_git_head(ROOT)
if summary.get("overall_status") != "passed":
    problems.append("gap matrix overall_status is not passed")
if not git.get("head_sha"):
    problems.append("gap matrix git.head_sha is missing")
elif git.get("head_sha") != current_head:
    problems.append("gap matrix git.head_sha does not match current HEAD")
if git.get("is_dirty") is not False:
    problems.append("gap matrix worktree is dirty")
```

返回的 `GateInput` 名称仍为 `gap_matrix`，并在 `details` 中保留 `counts`、`competitive_parity`、`report_head_sha`、`current_head_sha` 和 `is_dirty`。在 `run_final_gate()` 中用 `_gap_matrix_gate(paths["gap_matrix"])` 替换原 `_gate_from_report(...)`。

- [ ] **步骤 5：运行最终门禁回归测试**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_rc_final_gate.py tests/test_rc_release_diff_review_gate.py -o addopts= -p no:cov -q
```

预期：全部通过；原有 `full_parity_claimed=true` 拒绝逻辑不变。

- [ ] **步骤 6：提交任务 3**

```powershell
git add -- scripts/rc_final_gate.py tests/test_rc_final_gate.py
git commit -m "fix: 拒绝失配的 RC 矩阵证据"
```

### 任务 4：把竞品矩阵变成 CI 阻断门禁

**文件：**

- 修改：`tests/test_rc_ci_contract.py`
- 修改：`scripts/rc_ci_contract.py`
- 修改：`.github/workflows/commercial-rc.yml`

- [ ] **步骤 1：写 advisory 回归失败测试**

```python
def test_ci_contract_rejects_advisory_gap_matrix(tmp_path: Path) -> None:
    workflow = tmp_path / "commercial-rc.yml"
    current = DEFAULT_WORKFLOW.read_text(encoding="utf-8")
    blocking = "- name: Codex/Hermes gap matrix\n        run: python scripts/codex_hermes_gap_matrix.py --write-report"
    advisory = (
        "- name: Codex/Hermes gap matrix\n"
        "        continue-on-error: true\n"
        "        run: python scripts/codex_hermes_gap_matrix.py --write-report"
    )
    current = current.replace(advisory, blocking)
    workflow.write_text(current.replace(blocking, advisory), encoding="utf-8")

    report = validate_workflow(workflow)

    assert report.status == "failed"
    assert any(finding.id == "blocking_gap_matrix" for finding in report.findings)
```

- [ ] **步骤 2：运行并确认失败**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_rc_ci_contract.py -o addopts= -p no:cov -q
```

预期：当前校验器不能识别步骤级 `continue-on-error`，新测试失败。

- [ ] **步骤 3：实现步骤级校验并修复 workflow**

在 `rc_ci_contract.py` 增加一个窄范围检查：从 `- name: Codex/Hermes gap matrix` 起读取到下一个同缩进 `- name:`，若块内含 `continue-on-error: true`，返回 `ContractFinding(id="blocking_gap_matrix", kind="forbidden", ...)`。

在 `.github/workflows/commercial-rc.yml` 删除矩阵步骤的：

```yaml
continue-on-error: true
```

不得修改 runtime smoke 和 refresh chain 的 advisory 状态；它们属于后续计划。

- [ ] **步骤 4：验证 CI 契约**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_rc_ci_contract.py -o addopts= -p no:cov -q
.\venv\Scripts\python.exe scripts/rc_ci_contract.py
```

预期：测试通过，脚本输出 `Commercial RC CI contract status: passed`。

- [ ] **步骤 5：提交任务 4**

```powershell
git add -- .github/workflows/commercial-rc.yml scripts/rc_ci_contract.py tests/test_rc_ci_contract.py
git commit -m "ci: 阻断竞品矩阵失败"
```

### 任务 5：刷新根目录审计探针契约

**文件：**

- 新增：`tests/test_audit_probes_contract.py`
- 修改：`_audit_probe_routes.py`
- 修改：`_audit_probe_auth.py`
- 修改：`_audit_probe_agentrun.py`
- 修改：`AUDIT_2026-08-02_独立深度审计.md`

- [ ] **步骤 1：写静态契约失败测试**

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_audit_probes_use_current_routes_and_payload_fields() -> None:
    routes = (ROOT / "_audit_probe_routes.py").read_text(encoding="utf-8")
    auth = (ROOT / "_audit_probe_auth.py").read_text(encoding="utf-8")
    agentrun = (ROOT / "_audit_probe_agentrun.py").read_text(encoding="utf-8")

    assert '"/api/v1/audit-logs"' in routes
    assert '"/api/v1/audit-logs"' in auth
    assert '"/api/v1/sandbox/tasks"' in auth
    assert '"/api/skills"' in auth
    assert 'json={"task":' in agentrun
    assert 'json={"parameters": {"text": "probe"}}' in agentrun
    for stale in ('"/api/v1/audit/logs"', '"/api/v1/sandbox/status"', '"/api/v1/skills"'):
        assert stale not in routes + auth
    assert 'json={"message":' not in agentrun
    assert 'json={"arguments":' not in agentrun
```

- [ ] **步骤 2：运行并确认失败**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_audit_probes_contract.py -o addopts= -p no:cov -q
```

预期：旧路由和旧请求体断言失败。

- [ ] **步骤 3：只更新已确认漂移的字段**

执行以下精确替换：

- `_audit_probe_routes.py`：`/api/v1/audit` → `/api/v1/audit-logs`。
- `_audit_probe_auth.py`：`/api/v1/audit/logs` → `/api/v1/audit-logs`；`/api/v1/sandbox/status` → `/api/v1/sandbox/tasks`；`/api/v1/skills` → `/api/skills`。
- `_audit_probe_agentrun.py`：Agent body 的 `message` → `task`；工具 body 的 `arguments` → `parameters`。

在审计文档三个探针命令后补一句：`2026-08-07 已按当前 OpenAPI 路由与请求体刷新。`

- [ ] **步骤 4：运行静态和真实探针验证**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_audit_probes_contract.py -o addopts= -p no:cov -q
.\venv\Scripts\python.exe _audit_probe_routes.py
.\venv\Scripts\python.exe _audit_probe_auth.py
.\venv\Scripts\python.exe _audit_probe_agentrun.py mock
```

预期：pytest 通过；三个探针退出码为 0；Agent run 不再返回 422；工具 test 不再因字段名返回请求验证错误。可选依赖降级日志必须如实保留，不把它改写成通过。

- [ ] **步骤 5：提交任务 5**

```powershell
git add -- _audit_probe_routes.py _audit_probe_auth.py _audit_probe_agentrun.py tests/test_audit_probes_contract.py AUDIT_2026-08-02_独立深度审计.md
git commit -m "test: 刷新审计探针契约"
```

### 任务 6：生成同一 HEAD 的完整 RC-TRUTH 证据

**文件：**

- 运行时生成（不提交）：`.xagent_runtime/reports/codex-hermes-gap-closure.json`
- 运行时生成（不提交）：`.xagent_runtime/reports/rc-ci-contract.json`
- 运行时生成（不提交）：`.xagent_runtime/reports/rc-final-gate.json`

- [ ] **步骤 1：确认代码工作树干净**

```powershell
git status --short
git rev-parse HEAD
```

预期：`git status --short` 无输出。若存在无关用户改动，停止生成可发布证据并报告，不清理用户改动。

- [ ] **步骤 2：运行全部 M1 RC-TRUTH 测试**

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_codex_hermes_gap_matrix.py tests/test_settings_production_guard_p119.py tests/test_rc_final_gate.py tests/test_rc_release_diff_review_gate.py tests/test_rc_ci_contract.py tests/test_audit_probes_contract.py -o addopts= -p no:cov -q
.\venv\Scripts\python.exe -m ruff check scripts/codex_hermes_gap_matrix.py scripts/rc_final_gate.py scripts/rc_ci_contract.py tests/test_codex_hermes_gap_matrix.py tests/test_rc_final_gate.py tests/test_rc_ci_contract.py tests/test_audit_probes_contract.py
git diff --check
```

预期：全部通过且无 whitespace error。

- [ ] **步骤 3：运行完整竞品矩阵并写报告**

```powershell
.\venv\Scripts\python.exe scripts/codex_hermes_gap_matrix.py --write-report
```

预期：退出码 0；九个 required 类别全部 `passed`；报告中的 `git.head_sha` 等于步骤 1 的 HEAD，`git.is_dirty=false`，`full_parity_claimed=false`。

- [ ] **步骤 4：运行 CI 契约和最终聚合门禁**

```powershell
.\venv\Scripts\python.exe scripts/rc_ci_contract.py
.\venv\Scripts\python.exe scripts/rc_final_gate.py
```

预期：CI 契约为 `passed`。最终门禁不得因 gap matrix 失败或 SHA 失配而失败；若仍有真实 owner/external gate，则保持 `ready_with_owner_gates`，不得改写为 `ready_for_rc_tag`。

- [ ] **步骤 5：记录交付证据**

交付时列出：HEAD、定向测试计数、矩阵九类状态、CI contract 状态、final gate 状态以及仍需 owner 控制的外部门禁。不要提交 `.xagent_runtime` 运行产物，除非版本治理或发布清单明确要求。
