# 四形态可安装冒烟报告 (P1-22)

**日期**: 2026-07-26
**执行**: 部署演练收口工程师
**范围**: Web / 桌面 / 浏览器扩展 / 移动端 四形态的可安装冒烟执行记录

## 结果总览

| 形态 | 验证方式 | 结果 | 阻塞项 |
|------|---------|------|--------|
| Web | curl 关键页面 HTTP 状态 | ✅ 通过 | 无 |
| 桌面 (Tauri) | 配置级验证 | ✅ 通过(配置级) | 真实打包安装未执行 |
| 浏览器扩展 (MV3) | `extension/scripts/validate_manifest.py` | ❌ **失败 2 项** | manifest version `0.3.0-alpha` 不符合 Chrome 版本号格式, 且与校验器钉住的 0.2.0 不一致 |
| 移动端 (Expo) | `tsc --noEmit` + `expo export` 尝试 | ⚠️ 部分通过 | `expo export` 被 @expo/cli Windows 缺陷阻塞(mkdir `node:sea` 非法路径); web 目标缺 react-native-web 依赖 |

## 1. Web ✅

本机已有服务运行, 实测 curl 状态码:

| URL | 状态码 |
|-----|--------|
| http://localhost:3000/ (前端首页) | 200 |
| http://localhost:3000/login | 200 |
| http://localhost:8000/health (后端健康) | 200 |
| http://localhost:8000/docs (API 文档) | 200 |
| http://localhost:8000/api/v1/health | 404(路径不存在, 非服务故障; 实际健康端点为 /health) |

## 2. 桌面 ✅(配置级)

- `desktop/tauri.conf.json` 解析通过: productName `X-Agent`, version `0.3.0-alpha`,
  bundle identifier `com.xagent.desktop`, 窗口配置存在。
- `desktop/frontend/package.json` 解析通过: `x-agent-desktop-ui@0.1.0`。
- 未执行真实 `tauri build` 安装包制作与安装(构建耗时长且需 Rust 工具链完整链路,
  本次冒烟按预案记录为配置级已验)。
- 观察项(不在本次范围): tauri.conf.json 未设置 CSP。

## 3. 浏览器扩展 ❌(2 项失败, 需修复)

`python extension/scripts/validate_manifest.py` 输出: 权限/字段检查全部 PASS,
但失败 2 项:

1. `[FAIL] version == 0.2.0 (实际: 0.3.0-alpha)` — 校验器按设计钉住发布版本
   (EXPECTED_VERSION=0.2.0), manifest 已升至 0.3.0-alpha, 二者不一致;
2. `[FAIL] version 符合 Chrome 版本号格式 (1-4 段数字)` — `0.3.0-alpha` 含
   预发布后缀, **Chrome Web Store 不接受**, 真实上传会被拒。

**处置建议**(extension/ 超出本次修改范围, 仅记录): 发布前将 `version` 改为
纯数字段(如 `0.3.0`), 预发布信息放入 `version_name`; 并同步校验器的钉住值。
manifest 本身可解析: `X-Agent Browser Extension`, MV3。

## 4. 移动端 ⚠️

- ✅ `tsc --noEmit` (mobile/node_modules/.bin/tsc): **exit 0**, 类型检查通过,
  依赖已修复可用(node_modules 829 个包)。
- ❌ `expo export --platform web`: 缺 `react-native-web`/`react-dom`/
  `@expo/metro-runtime`(项目未声明 web 目标依赖)。
- ❌ `expo export --platform android`(EXPO_OFFLINE=1): 被 @expo/cli 的
  Windows 缺陷阻塞 — Metro externals 尝试 `mkdir ...\node:sea`, 冒号为
  Windows 非法文件名字符, ENOENT 失败。非应用代码问题; 建议在 WSL/macOS/
  Linux CI 上重试 `expo export`, 或升级 @expo/cli 至修复版本。

## 证据与产物

- 本报告: `commercial_audit/install_smoke_report_2026-07-26.md`
- Helm 渲染证据(P1-15): `commercial_audit/evidence/helm-template-*-2026-07-26.yaml`
- Qdrant 演练证据(P1-17): `commercial_audit/evidence/qdrant-drill-2026-07-26/`
