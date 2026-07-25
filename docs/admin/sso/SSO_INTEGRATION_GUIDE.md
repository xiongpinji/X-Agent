# SSO / SCIM 集成指南 (P1-02 更新, 2026-07-20)

> 本文与代码实际能力保持一致。**OIDC 为 GA; SAML 2.0 为 Beta (fail-closed);
> WebAuthn / 条件访问 / LDAP 未实现 (相关端点显式 501)。**

## 能力矩阵

| 能力 | 状态 | 入口 |
|------|------|------|
| OIDC 授权码流程 (discovery / JWKS 验签 / state+nonce / JIT provisioning) | **GA** | `GET/POST /api/v1/sso/oidc/{provider}/*` |
| SCIM 2.0 用户 provisioning (Users CRUD, bearer + 租户绑定) | **GA** | `/scim/v2/*` |
| 旧版 OAuth (google/github/microsoft, userinfo 流程) | 可用 | `POST /api/v1/auth/sso/oauth/*` |
| MFA (TOTP/SMS/Email challenge) | 可用 | `POST /api/v1/auth/mfa/*` |
| 会话管理 | 可用 | `GET/DELETE /api/v1/auth/sessions*` |
| SAML 2.0 | **Beta, fail-closed (501)** | `/api/v1/sso/saml/{provider}/*` |
| WebAuthn / 条件访问 / LDAP | 未实现 (显式 501) | — |

## 依赖

```bash
pip install -r requirements.txt   # authlib>=1.7.2 (OIDC 验签) 已包含
```

- `authlib` (joserfc): OIDC id_token 签名验证。缺失时代码自动降级为内置
  cryptography 实现 (仅 RS256/HS256), 其余算法显式拒绝 — 生产环境请安装 authlib。
- SAML 需要 python3-saml/signxml 级 XML DSig 验签, **未接入**, 因此 SAML 响应
  处理一律 fail-closed。

## OIDC (GA)

### 配置提供方

方式一 — 环境变量 `XAGENT_SSO_PROVIDERS` (JSON 数组):

```json
[
  {
    "provider_name": "okta",
    "tenant_id": "tenant-a",
    "discovery_url": "https://your-org.okta.com/.well-known/openid-configuration",
    "client_id": "xxx",
    "client_secret": "yyy",
    "redirect_uri": "https://app.example.com/api/v1/sso/oidc/okta/callback",
    "scopes": ["openid", "profile", "email"]
  }
]
```

方式二 — 启动时程序化注册:

```python
from backend.app.api.sso import register_oidc_provider
from backend.app.core.saml_sso import OIDCConfig

register_oidc_provider(OIDCConfig(...))
```

### 登录流程

```
1. GET  /api/v1/sso/oidc/{provider}/authorize?tenant_id=...
   → { authorization_url, state }            (state/nonce 一次性, 10 分钟 TTL)
2. 浏览器重定向至 IdP, 用户完成认证
3. IdP 回调携带 code + state
4. POST /api/v1/sso/oidc/{provider}/callback  { code, state }
   → 校验 state(一次性) → 授权码换 token → JWKS 验签 id_token
     → iss/aud/exp/nonce 校验 → JIT provisioning → 签发本地会话
   ← { access_token, user, sso: { jit_provisioned, storage_mode }, session }
```

安全属性:
- state 一次性消费, 重放/伪造一律 401;
- id_token 验签 fail-closed (无法取得密钥材料即拒绝, 绝不静默解码);
- nonce 校验防重放;
- 本地会话经 `backend.app.api.auth._issue_token` 真实签发, 签发器不可用时
  响应显式标注 `session.issued=false`, 不伪造令牌。

多实例部署注意: state 存储为进程内实现, 需经
`backend.app.core.saml_sso.set_state_store(...)` 注入分布式存储 (如 Redis)。

## SCIM 2.0 (GA)

实现 RFC 7643/7644 的 Users 资源: 创建/查询(过滤+分页)/全量更新/PATCH/停用。
发现端点: `ServiceProviderConfig` / `ResourceTypes` / `Schemas` (内容按真实能力声明)。

### 令牌配置 (bearer + 租户绑定)

环境变量 `XAGENT_SCIM_TOKENS` (JSON 对象):

```json
{
  "<random-token-1>": { "tenant_id": "tenant-a", "description": "Okta provisioning" }
}
```

- 每个令牌绑定一个租户, 所有操作强制限定租户内 (跨租户访问返回 404, 不泄露存在性);
- 未配置任何令牌时所有请求 503 (fail-closed, 不匿名放行);
- 令牌比对为常数时间 (hmac.compare_digest)。

### 端点速查

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/scim/v2/Users?filter=&startIndex=&count=` | 列表 (支持 `userName eq "..."`、`externalId eq "..."`) |
| POST | `/scim/v2/Users` | 创建 (201 + Location; userName 冲突 409) |
| GET | `/scim/v2/Users/{id}` | 单查 |
| PUT | `/scim/v2/Users/{id}` | 全量替换 (userName=email 不可变, 变更返回 mutability 错误) |
| PATCH | `/scim/v2/Users/{id}` | PatchOp: active / externalId / name.* / emails |
| DELETE | `/scim/v2/Users/{id}` | 软停用 (is_active=false, 记录保留用于审计) |

映射约定: `userName` ↔ 平台 email 字段; `externalId`/`emails`/`name` 存于
用户 metadata.scim; SCIM 创建的用户带不可用口令占位 (`!external-managed:*`),
不能走本地口令登录。

## 旧版 OAuth / MFA (保留)

`backend.app.core.sso.*` 子包支撑的端点保留可用:
`POST /api/v1/auth/sso/oauth/authorize|callback` (google/github/microsoft),
`POST /api/v1/auth/mfa/setup|verify`, `GET/DELETE /api/v1/auth/sessions*`。

P1-02 修复: oauth callback 不再返回硬编码假令牌, 改为真实 JIT provisioning +
本地会话签发; WebAuthn 与条件访问端点由空壳假成功改为显式 501。

## SAML 2.0 (Beta)

`/api/v1/sso/saml/{provider}/login|acs` 一律返回 501 及原因说明。
启用条件: 接入 python3-saml/signxml 做真实 XML DSig 验签 (此前"验签"仅检查
Signature 元素存在, 属 P0-05 级假验签, 已 fail-closed 封堵)。

## 测试

- `tests/enterprise/test_oidc_sso_flow.py` — Mock IdP (httpx MockTransport)
  覆盖 discovery/JWKS/state/nonce/签名篡改/audience/过期/重放/JIT/HS256。
- `tests/enterprise/test_scim_api.py` — TestClient 直测 router (自建 app,
  不依赖 main.py): CRUD/鉴权/租户隔离/过滤/分页/错误格式/存储适配接线。
