"""SSO and Enterprise Authentication Configuration Guide."""

# SSO与企业认证系统配置指南

## 概述

X-Agent SSO与企业认证系统提供完整的企业级身份验证和授权解决方案，支持多种SSO协议、MFA方法和会话管理。

## 支持的功能

### 1. SSO集成

#### OAuth 2.0
- **Google**: 支持Google账户登录
- **GitHub**: 支持GitHub账户登录
- **Microsoft**: 支持Microsoft/Azure AD账户登录

#### SAML 2.0
- 企业SSO集成
- 支持多个IdP
- 自动用户配置

#### OpenID Connect
- 标准OIDC提供商支持
- 自动发现配置
- 令牌刷新

#### LDAP/Active Directory
- 企业目录集成
- 用户和组同步
- 密码验证

### 2. 企业认证

#### 多因素认证 (MFA)
- **TOTP**: Google Authenticator、Authy等
- **SMS**: 短信验证码
- **Email**: 邮件验证码

#### 生物识别认证
- **WebAuthn**: FIDO2、YubiKey支持
- 指纹识别
- 面部识别

#### 硬件密钥
- YubiKey支持
- FIDO2兼容设备

### 3. 会话管理

- 分布式会话存储（Redis）
- 可配置的超时设置
- 并发会话限制
- 会话审计日志
- 强制登出

### 4. 条件访问

- IP白名单
- 设备信任
- 地理位置限制
- 异常登录检测

## 配置

### 环境变量

```bash
# OAuth配置
OAUTH_GOOGLE_CLIENT_ID=your_client_id
OAUTH_GOOGLE_CLIENT_SECRET=your_client_secret
OAUTH_GOOGLE_REDIRECT_URI=https://your-domain.com/auth/oauth/callback

OAUTH_GITHUB_CLIENT_ID=your_client_id
OAUTH_GITHUB_CLIENT_SECRET=your_client_secret
OAUTH_GITHUB_REDIRECT_URI=https://your-domain.com/auth/oauth/callback

OAUTH_MICROSOFT_CLIENT_ID=your_client_id
OAUTH_MICROSOFT_CLIENT_SECRET=your_client_secret
OAUTH_MICROSOFT_REDIRECT_URI=https://your-domain.com/auth/oauth/callback

# SAML配置
SAML_ENTITY_ID=https://your-domain.com
SAML_ACS_URL=https://your-domain.com/auth/saml/acs
SAML_IDP_ENTITY_ID=https://idp.example.com
SAML_IDP_SSO_URL=https://idp.example.com/sso
SAML_IDP_CERTIFICATE=path/to/idp_certificate.pem

# OIDC配置
OIDC_CLIENT_ID=your_client_id
OIDC_CLIENT_SECRET=your_client_secret
OIDC_DISCOVERY_URL=https://provider.example.com/.well-known/openid-configuration

# LDAP配置
LDAP_SERVER_URL=ldap://ldap.example.com:389
LDAP_BASE_DN=dc=example,dc=com
LDAP_BIND_DN=cn=admin,dc=example,dc=com
LDAP_BIND_PASSWORD=password

# WebAuthn配置
WEBAUTHN_RP_ID=your-domain.com
WEBAUTHN_RP_NAME=X-Agent
WEBAUTHN_ORIGIN=https://your-domain.com

# 会话配置
SESSION_TIMEOUT=3600
ABSOLUTE_TIMEOUT=86400
IDLE_TIMEOUT=1800
MAX_CONCURRENT_SESSIONS=5

# Redis配置
REDIS_URL=redis://localhost:6379
```

### Python配置

```python
from backend.app.core.sso.oauth_provider import OAuthConfig, OAuthProvider
from backend.app.core.sso.saml_provider import SAMLConfig
from backend.app.core.sso.oidc_provider import OIDCConfig
from backend.app.core.sso.ldap_provider import LDAPConfig
from backend.app.core.sso.mfa_manager import MFAConfig, MFAMethod
from backend.app.core.sso.session_manager import SessionConfig
from backend.app.core.sso.webauthn_provider import WebAuthnConfig

# OAuth配置
oauth_google_config = OAuthConfig(
    provider=OAuthProvider.GOOGLE,
    client_id="your_client_id",
    client_secret="your_client_secret",
    redirect_uri="https://your-domain.com/auth/oauth/callback",
    scopes=["openid", "profile", "email"],
)

# SAML配置
saml_config = SAMLConfig(
    entity_id="https://your-domain.com",
    acs_url="https://your-domain.com/auth/saml/acs",
    idp_entity_id="https://idp.example.com",
    idp_sso_url="https://idp.example.com/sso",
    idp_certificate="path/to/idp_certificate.pem",
)

# OIDC配置
oidc_config = OIDCConfig(
    client_id="your_client_id",
    client_secret="your_client_secret",
    redirect_uri="https://your-domain.com/auth/oidc/callback",
    discovery_url="https://provider.example.com/.well-known/openid-configuration",
)

# LDAP配置
ldap_config = LDAPConfig(
    server_url="ldap://ldap.example.com:389",
    base_dn="dc=example,dc=com",
    bind_dn="cn=admin,dc=example,dc=com",
    bind_password="password",
)

# MFA配置
mfa_config = MFAConfig(
    enabled_methods=[MFAMethod.TOTP, MFAMethod.EMAIL],
    totp_issuer="X-Agent",
    totp_window=1,
    sms_timeout=300,
    email_timeout=600,
    max_attempts=5,
    lockout_duration=900,
)

# 会话配置
session_config = SessionConfig(
    session_timeout=3600,
    absolute_timeout=86400,
    idle_timeout=1800,
    max_concurrent_sessions=5,
    enable_session_audit=True,
    enable_device_tracking=True,
)

# WebAuthn配置
webauthn_config = WebAuthnConfig(
    rp_id="your-domain.com",
    rp_name="X-Agent",
    origin="https://your-domain.com",
    timeout=60000,
    attestation="direct",
    user_verification="preferred",
)
```

## API使用示例

### OAuth登录

```bash
# 1. 获取授权URL
curl -X POST http://localhost:8000/api/v1/auth/sso/oauth/authorize?provider=google

# 响应:
{
  "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?...",
  "state": "state_value"
}

# 2. 用户在浏览器中访问authorization_url进行登录
# 3. 处理回调
curl -X POST http://localhost:8000/api/v1/auth/sso/oauth/callback \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "google",
    "code": "authorization_code",
    "state": "state_value"
  }'

# 响应:
{
  "access_token": "token",
  "refresh_token": "refresh_token",
  "user": {
    "email": "user@example.com",
    "name": "User Name"
  }
}
```

### MFA设置

```bash
# 1. 设置TOTP
curl -X POST http://localhost:8000/api/v1/auth/mfa/setup \
  -H "Authorization: Bearer token" \
  -H "Content-Type: application/json" \
  -d '{
    "method": "totp"
  }'

# 响应:
{
  "secret": "JBSWY3DPEBLW64TMMQ======",
  "provisioning_uri": "otpauth://totp/X-Agent:user@example.com?secret=...",
  "backup_codes": ["XXXX-XXXX-XXXX", ...]
}

# 2. 验证MFA代码
curl -X POST http://localhost:8000/api/v1/auth/mfa/verify \
  -H "Authorization: Bearer token" \
  -H "Content-Type: application/json" \
  -d '{
    "challenge_id": "challenge_id",
    "code": "123456"
  }'

# 响应:
{
  "verified": true
}
```

### 会话管理

```bash
# 获取所有会话
curl -X GET http://localhost:8000/api/v1/auth/sessions \
  -H "Authorization: Bearer token"

# 响应:
{
  "sessions": [
    {
      "session_id": "session_id",
      "created_at": "2026-05-28T10:00:00Z",
      "last_activity": "2026-05-28T10:30:00Z",
      "ip_address": "192.168.1.1",
      "device_name": "Chrome on Windows",
      "mfa_verified": true,
      "trusted_device": false
    }
  ]
}

# 撤销会话
curl -X DELETE http://localhost:8000/api/v1/auth/sessions/session_id \
  -H "Authorization: Bearer token"

# 撤销所有会话
curl -X POST http://localhost:8000/api/v1/auth/sessions/revoke-all \
  -H "Authorization: Bearer token"
```

### WebAuthn注册

```bash
# 1. 开始注册
curl -X POST http://localhost:8000/api/v1/auth/webauthn/register/start \
  -H "Authorization: Bearer token" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "user@example.com"
  }'

# 响应:
{
  "challenge_id": "challenge_id",
  "options": {
    "challenge": "...",
    "rp": {...},
    "user": {...},
    "pubKeyCredParams": [...],
    "timeout": 60000,
    "attestation": "direct"
  }
}

# 2. 完成注册
curl -X POST http://localhost:8000/api/v1/auth/webauthn/register/complete \
  -H "Authorization: Bearer token" \
  -H "Content-Type: application/json" \
  -d '{
    "challenge_id": "challenge_id",
    "credential_id": "credential_id",
    "public_key": "...",
    "device_name": "YubiKey 5"
  }'

# 响应:
{
  "registered": true
}
```

## 安全最佳实践

### 1. 密码策略
- 最少8个字符
- 必须包含大小写字母
- 必须包含至少一个数字
- 建议包含特殊字符

### 2. 登录失败锁定
- 5次失败后锁定账户
- 锁定时间：30分钟
- 支持管理员解锁

### 3. 会话安全
- 使用HTTPS传输
- 设置安全的Cookie标志
- 实现CSRF保护
- 定期更新会话令牌

### 4. MFA强制
- 对管理员强制MFA
- 对敏感操作要求MFA
- 支持备用码恢复

### 5. 审计日志
- 记录所有登录事件
- 记录MFA验证
- 记录会话创建/撤销
- 记录异常登录

## 故障排除

### OAuth登录失败
1. 检查client_id和client_secret
2. 验证redirect_uri配置
3. 检查网络连接
4. 查看日志获取详细错误

### MFA验证失败
1. 检查时间同步（TOTP）
2. 验证验证码未过期
3. 检查备用码
4. 查看审计日志

### 会话问题
1. 检查Redis连接
2. 验证会话超时设置
3. 检查并发会话限制
4. 查看会话审计日志

## 性能优化

### 1. 缓存
- 缓存OAuth提供商配置
- 缓存SAML元数据
- 缓存LDAP查询结果

### 2. 连接池
- 使用HTTP连接池
- 使用LDAP连接池
- 使用Redis连接池

### 3. 异步处理
- 异步发送MFA代码
- 异步审计日志记录
- 异步会话清理

## 监控和告警

### 关键指标
- 登录成功率
- MFA验证成功率
- 会话创建/撤销速率
- 异常登录检测

### 告警规则
- 登录失败率过高
- MFA验证失败率过高
- 异常登录检测
- 会话异常活动

## 合规性

### GDPR
- 用户数据导出
- 用户数据删除
- 隐私政策

### SOC 2
- 访问控制
- 审计日志
- 加密传输

### HIPAA
- 加密存储
- 访问控制
- 审计日志
