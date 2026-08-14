# M1 RC 最终门禁状态 — 2026-08-14

执行人： RC 证据链工程师（子代理） · 运行环境： 项目 `venv/` Python + `PYTHONPATH=主仓根`（避免 scripts 解析到 `.worktrees/m1-rc-truth-version` 副本）

## 总结论

- **final gate: `failed`（rc_candidate=false）**，纯本地阻断根因只有 1 个：`supply_chain_gate.npm_audit`（frontend 9 个漏洞，frontend/ 不在本次授权修改范围）。
- 其余本地 gate 全绿（21/23）；`deployment_docs_gate` 与 `evidence_pack` 的失败均为 npm_audit 级联（receipt 未 created → evidence pack 缺 → 文档门禁 artifact_handoff 缺 evidence pack sha）。
- 全部报告位于主仓 `.xagent_runtime/reports/`；最终 artifact：`.xagent_runtime/release/x-agent-commercial-rc-20260814T050802Z.zip`（115 文件，1,776,938 字节，sha256 `b284b2e2f749d92bf466a32987f597248c603154b579d6b8bffae2b8dcf5b7fd`）。

## 各 Gate 状态（证据路径均在 `.xagent_runtime/reports/`，除注明外）

| Gate | 状态 | 证据 |
|---|---|---|
| codex-hermes-gap-closure | pass | `codex-hermes-gap-closure.json` |
| release_audit (`--manifest-candidates`) | pass，115 candidates，0 secret/path/hygiene findings | `rc-release-audit.json` |
| staging_plan | pass（planned，115 文件 / 6 条 git add 命令） | `rc-staging-plan.json` |
| source_bundle | pass（created，115 文件） | `rc-source-bundle.json` |
| artifact_integrity_gate | pass（含 zip 安全扫描） | `rc-artifact-integrity-gate.json` |
| secrets_gate | pass | `rc-secrets-gate.json` |
| supply_chain_gate | **fail — 仅 npm_audit**；python_manifest/python_lockfile(pip-audit)/frontend_lockfile/ci_dependency_contract/release_dependency_evidence 均 pass | `rc-supply-chain-gate.json` |
| install_release_gate | pass（Windows/POSIX installer dry-run + doctor） | `rc-install-release-gate.json` |
| release_diff_review_gate | pass | `rc-release-diff-review-gate.json` |
| deployment_docs_gate | fail — 仅 artifact_handoff_docs（等 evidence pack，npm 级联） | `rc-deployment-docs-gate.json` |
| owner_gate_plan | pass(action_required，本地结构验证通过) | `rc-owner-gate-plan.json` |
| owner_env_template | pass(created) | `rc-owner-env-template.json/.env/.ps1` |
| owner_gate_checklist | pass(action_required) | `rc-owner-gate-checklist.json/.md` |
| owner_handoff_gate | pass | `rc-owner-handoff-gate.json` |
| owner_gate_runner | pass（dry-run, --gate all） | `rc-owner-gate-runner.json` |
| ci_contract | pass | `rc-ci-contract.json` |
| runtime_smoke | pass | `.xagent_runtime/smoke/rc-runtime-smoke.json` |
| external_smoke | pass（本地部分；owner 外部检查 skipped） | `rc-external-smoke.json` |
| refresh_release_chain | 链执行至终点；supply_chain 之后步骤级联 failed | `rc-refresh-release-chain.json` |
| release_receipt | **failed — 仅 supply_chain_gate/npm_audit 及其级联** | `.xagent_runtime/release/x-agent-commercial-rc-receipt.json` |
| evidence_pack | failed — release_receipt 未 created（级联） | `rc-evidence-pack.json` |
| **final_gate** | **failed**（local gate failed: supply_chain + 级联） | `rc-final-gate.json` |

## 本次修复（均未触碰 backend/frontend/tests 源码，无 git 写操作）

1. **scripts/rc_deployment_docs_gate.py**: `DEFAULT_RUNBOOK/DEFAULT_CHECKLIST/DEFAULT_INSTALL_QUICKSTART` 由 `docs/` 顶层改指 `docs/operations/deployment/` 与 `docs/operations/setup/`（docs 重组后脚本默认路径漂移）。
2. **scripts/rc_release_diff_review_gate.py**: `DEFAULT_REVIEW` 同上改指 `docs/operations/deployment/RC_RELEASE_DIFF_REVIEW.md`。
3. **scripts/rc_install_release_gate.py**: `_powershell_executable()` 增加 `%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe` 回退（本环境 PATH 无 powershell 导致 WinError 2）。
4. **.github/workflows/commercial-rc.yml**: 恢复 CI 契约 `npm audit --audit-level=moderate`（原被弱化为 `critical || true`）。注意：漏洞未修前 hosted CI 此步将红——属诚实反映。
5. **requirements-lock.txt**: `h2==4.3.0 → 4.4.1`（PYSEC-2026-3628，pip-audit 唯一 Python 漏洞）；venv 内已安装的 h2 仍为 4.3.0，需 owner 同步重装。
6. **docs/RC_STAGING_MANIFEST.md**: 原为空 stub（Candidate files: 0 根因——非脚本 bug，是清单数据为空）；已重建为 115 文件 post-commit 全量载荷清单（以 `docs/operations/deployment/RC_STAGING_MANIFEST.md` 六月权威版为基，12 个失效路径重映射/剔除）。
7. **docs/operations/deployment/RC_RELEASE_DIFF_REVIEW.md / RC_COMMERCIAL_DEPLOYMENT_CHECKLIST.md**: 证据计数由 6 月快照（117 files / 6 commands）更新为当前真实值（115 files / 6 commands）。

## Owner 待办（不得伪造，均未执行）

1. **frontend 漏洞修复（唯一本地阻断）**: `frontend/` 下 `npm audit fix`；9 个漏洞 = 7 high（minimatch×3，经 typescript-eslint，需 `--force` 破坏性升级至 @typescript-eslint/parser@8.67.0；nanoid<3.3.18）+ 2 moderate（react-router / react-router-dom，GHSA-wrjc-x8rr-h8h6、GHSA-337j-9hxr-rhxg）。修复后重跑 `venv/Scripts/python.exe scripts/rc_refresh_release_chain.py --provider mock --continue-on-failure`（须设 PYTHONPATH=主仓根、PATH 含 venv/Scripts）即可走通 receipt → evidence pack → final gate。
2. **真实凭据 owner gates**（`rc-final-gate.json` owner_gates 均为 action_required）：
   - provider: 设置 `XAGENT_LLM_BACKEND` 为真实 provider 并配置对应 key；
   - feishu_webhook_contract: `XAGENT_FEISHU_APP_ID/APP_SECRET/ENCRYPT_KEY`；
   - github_issue_to_pr_dry_run: `XAGENT_GITHUB_TEST_ISSUE_URL`（一次性测试 issue）；
   - github_issue_to_pr_execute_preflight: `XAGENT_GITHUB_TOKEN` + `--github-execute-preflight`；
   - hosted_github_actions_commercial_rc: 在 hosted GitHub Actions 跑通 commercial-rc.yml，提供 run URL + head SHA（`XAGENT_COMMERCIAL_RC_GITHUB_ACTIONS_RUN_URL/HEAD_SHA`）；
   - 最后以 `--owner-verified` 重跑 `rc_refresh_release_chain.py`。
3. **venv 依赖同步**: `pip install -r requirements-lock.txt`（h2 4.4.1）。
4. 环境提示： 运行门禁需 `venv/Scripts` 在 PATH（pip-audit）且 powershell 可解析（已加脚本回退）。
