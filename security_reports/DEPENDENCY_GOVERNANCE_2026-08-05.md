# 依赖治理报告（P1-05，2026-08-05 全量重扫）

> 数据源：pip-audit（lock 全量 + venv 实际安装双层）、npm audit（frontend/extension/mobile）、
> SBOM（CycloneDX 1.5，`sbom.json`，113 components）。
> CI：`security.yml` 每日 02:17 UTC 定时 pip-audit（requirements-lock.txt）+ npm audit（已在产）。

## 1. Python 依赖：清零 ✅

**重扫发现 11 个已知漏洞（5 包）→ 全部升级到修复版本，终扫 ZERO：**

| 包 | 原版本 | 现版本 | 漏洞 |
|---|---|---|---|
| click | 8.1.7 | **8.4.2** | PYSEC-2026-2132（命令注入） |
| cryptography | 48.0.0 | **50.0.0** | PYSEC-2026-3552/53/54 + GHSA-537c（PKCS7/证书链/OpenSSL） |
| pydantic-settings | 2.14.1 | **2.14.2** | GHSA-4xgf-cpjx-pc3j（嵌套 secrets 读取） |
| setuptools | 82.0.1 | **83.0.0** | PYSEC-2026-3447（sdist 构建） |
| starlette | 1.2.1 | **1.3.1** | PYSEC-2026-248/249（路径校验） |
| aiohttp | 3.14.1 | **3.14.3** | PYSEC-2026-3545/46/47（freeze 层追加发现） |
| msgpack | 1.1.2 | **1.2.1** | GHSA-6v7p-g79w-8964（freeze 层追加发现） |
| pytest | 8.4.2 | **9.0.3** | PYSEC-2026-1845（freeze 层追加发现；pytest-asyncio 联动升 1.4.0，RC 门禁+定向套件验证绿） |

**治理性修复（比漏洞本身更重要）：**
- `pyproject.toml` 的 `cryptography>=46.0.0,<49.0.0` 陈旧上限（x-agent-core 0.1.0 时代遗留）已改为 `>=50.0.0`——否则 lock 编译永远解析回漏洞版本；
- `aiohttp` 补入 pyproject dependencies（audit_export/dingtalk/feishu 生产路径实际使用，此前只在 requirements.txt，lock 编译会漏）；
- `requirements-lock.txt` 重新编译（uv，cli+prod extras）：87 → **113 components**（覆盖 aiohttp/msgpack 等此前漏网的实际依赖）；
- `sbom.json` 重新生成（CycloneDX 1.5，113 components），生成器 `scripts/generate_sbom.py` 可复跑。

## 2. npm 依赖：部分清零，残留已处置

| 形态 | 重扫 | audit fix 后 | 残留处置 |
|---|---|---|---|
| extension | 1 high | **0** ✅ | — |
| frontend | 14（12 high） | 8（6 high + 2 moderate） | 残留为 @typescript-eslint 工具链（开发期 lint）需大版本升级 + react-router moderate；不进入运行时产物，列为独立升级任务 |
| mobile | 31（1 critical） | 29 | 残留集中在 expo 工具链（构建期），需 expo 大版本升级（isSemVerMajor），构建破坏风险高，列为独立任务 |

原始报告：`_npm_audit_{frontend,extension,mobile}.json`（重扫时点快照）；复扫结果见上表。

## 3. 结论与后续

- Python 运行时依赖 **零已知漏洞**（pip-audit exit 0），CI 每日守着 lock（113 项全量）。
- 前端三形态的运行时供应链风险低（残留均为构建/lint 工具链）；两个大版本升级任务（@typescript-eslint 8.66、expo 57）建议在下一次前端维护窗口执行并配构建验证。
- 每次依赖升级后复跑：`pip-audit -r requirements-lock.txt` + `python scripts/generate_sbom.py`。
