# X-Agent 安全指南

**版本**: 1.0  
**最后更新**: 2026-05-27  
**文档状态**: Published

---

## 目录

1. [安全概览](#安全概览)
2. [认证与授权](#认证与授权)
3. [数据加密](#数据加密)
4. [API安全](#api安全)
5. [审计日志](#审计日志)
6. [安全检查清单](#安全检查清单)
7. [漏洞报告](#漏洞报告)
8. [常见安全问题](#常见安全问题)

---

## 安全概览

X-Agent 采用多层安全架构，包括：

- **认证层**: JWT令牌、API密钥、OAuth支持
- **授权层**: 基于角色的访问控制(RBAC)
- **加密层**: 数据传输加密、敏感数据存储加密
- **审计层**: 完整的操作审计日志
- **隔离层**: 多租户隔离、资源隔离

### 安全原则

1. **最小权限原则** - 用户仅获得必要的权限
2. **深度防御** - 多层安全控制
3. **审计追踪** - 所有操作都被记录
4. **加密优先** - 敏感数据加密存储和传输
5. **定期审查** - 定期安全审计和更新

---

## 认证与授权

### 认证方式

#### 1. JWT令牌认证

```bash
# 获取令牌
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "user@example.com",
    "password": "secure_password"
  }'

# 使用令牌
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  http://localhost:8000/api/agents
```

**配置**:
```env
JWT_SECRET=your-secret-key-min-32-chars
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
```

#### 2. API密钥认证

```bash
# 使用API密钥
curl -H "X-API-Key: your-api-key" \
  http://localhost:8000/api/agents
```

**生成API密钥**:
```python
from backend.app.core.security import generate_api_key

api_key = generate_api_key()
# 存储到数据库
```

#### 3. OAuth 2.0 (规划中)

支持通过第三方提供商认证：
- Google OAuth
- GitHub OAuth
- Microsoft Azure AD

### 授权模型

#### 基于角色的访问控制(RBAC)

```python
# 定义角色
class Role(str, Enum):
    ADMIN = "admin"           # 系统管理员
    DEVELOPER = "developer"   # 开发者
    OPERATOR = "operator"     # 运维人员
    VIEWER = "viewer"         # 查看者

# 权限映射
ROLE_PERMISSIONS = {
    Role.ADMIN: ["*"],  # 所有权限
    Role.DEVELOPER: [
        "agents:create",
        "agents:read",
        "agents:update",
        "workflows:*",
        "memory:*"
    ],
    Role.OPERATOR: [
        "agents:read",
        "runs:read",
        "metrics:read",
        "logs:read"
    ],
    Role.VIEWER: [
        "agents:read",
        "runs:read",
        "metrics:read"
    ]
}
```

#### 权限检查

```python
from backend.app.dependencies import require_permission

@app.post("/api/agents")
async def create_agent(
    agent: AgentCreate,
    current_user: User = Depends(require_permission("agents:create"))
):
    # 创建Agent
    pass
```

#### 多租户隔离

```python
# 自动隔离租户数据
@app.get("/api/agents")
async def list_agents(
    current_user: User = Depends(get_current_user)
):
    # 只返回当前租户的Agent
    agents = db.query(Agent).filter(
        Agent.tenant_id == current_user.tenant_id
    ).all()
    return agents
```

---

## 数据加密

### 传输加密

#### HTTPS配置

```python
# 生产环境强制HTTPS
if settings.environment == "production":
    app.add_middleware(
        HTTPSRedirectMiddleware
    )
```

#### TLS证书

```bash
# 使用Let's Encrypt
certbot certonly --standalone -d your-domain.com

# 配置Nginx
server {
    listen 443 ssl;
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
}
```

### 存储加密

#### 敏感数据加密

```python
from cryptography.fernet import Fernet

class EncryptedField:
    def __init__(self, key: str):
        self.cipher = Fernet(key.encode())
    
    def encrypt(self, value: str) -> str:
        return self.cipher.encrypt(value.encode()).decode()
    
    def decrypt(self, value: str) -> str:
        return self.cipher.decrypt(value.encode()).decode()

# 使用
encrypted_field = EncryptedField(settings.encryption_key)
encrypted_api_key = encrypted_field.encrypt(api_key)
```

#### 密码哈希

```python
from passlib.context import CryptContext

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12  # 安全轮数
)

# 哈希密码
hashed_password = pwd_context.hash(password)

# 验证密码
is_valid = pwd_context.verify(password, hashed_password)
```

---

## API安全

### CORS配置

```python
# 生产环境配置明确的域名白名单
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://app.example.com",
        "https://admin.example.com"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
    max_age=3600
)
```

### 安全响应头

```python
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    
    # 防止点击劫持
    response.headers["X-Frame-Options"] = "DENY"
    
    # 防止MIME类型嗅探
    response.headers["X-Content-Type-Options"] = "nosniff"
    
    # 启用XSS保护
    response.headers["X-XSS-Protection"] = "1; mode=block"
    
    # 内容安全策略
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'"
    )
    
    return response
```

### 速率限制

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.get("/api/agents")
@limiter.limit("100/minute")
async def list_agents(request: Request):
    pass
```

### 输入验证

```python
from pydantic import BaseModel, validator

class AgentCreate(BaseModel):
    name: str
    description: str
    
    @validator('name')
    def name_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Name cannot be empty')
        return v.strip()
    
    @validator('description')
    def description_length(cls, v):
        if len(v) > 1000:
            raise ValueError('Description too long')
        return v
```

---

## 审计日志

### 审计日志配置

```python
# 启用审计日志
AUDIT_LOG_ENABLED = True
AUDIT_LOG_LEVEL = "INFO"
AUDIT_LOG_RETENTION_DAYS = 90

# 审计日志存储
AUDIT_LOG_BACKEND = "postgresql"  # 或 "file"
AUDIT_LOG_PATH = "/var/log/xagent/audit.log"
```

### 审计事件

```python
from backend.app.core.audit import log_audit_event

# 记录审计事件
await log_audit_event(
    event_type="agent_created",
    user_id=current_user.id,
    resource_id=agent.id,
    resource_type="agent",
    action="create",
    details={
        "name": agent.name,
        "description": agent.description
    },
    status="success"
)
```

### 审计日志查询

```bash
# 查询特定用户的操作
curl -H "Authorization: Bearer TOKEN" \
  "http://localhost:8000/api/audit?user_id=123&limit=100"

# 查询特定资源的操作
curl -H "Authorization: Bearer TOKEN" \
  "http://localhost:8000/api/audit?resource_id=456&resource_type=agent"

# 查询特定时间范围
curl -H "Authorization: Bearer TOKEN" \
  "http://localhost:8000/api/audit?start_date=2026-05-01&end_date=2026-05-31"
```

---

## 安全检查清单

### 部署前检查

- [ ] JWT_SECRET已设置为强密钥(最少32字符)
- [ ] CORS origins已配置为明确的域名(非通配符)
- [ ] HTTPS已启用
- [ ] 数据库密码已更改
- [ ] API密钥已生成并安全存储
- [ ] 敏感文件已从Git历史中移除
- [ ] .env文件已添加到.gitignore
- [ ] 依赖版本已锁定
- [ ] 安全响应头已配置
- [ ] 速率限制已启用

### 运行时检查

- [ ] 审计日志正常记录
- [ ] 没有默认凭证在使用
- [ ] 密码策略已实施
- [ ] 会话超时已配置
- [ ] 日志中没有敏感信息泄露
- [ ] 定期备份已启用
- [ ] 监控告警已配置

### 定期审查

- [ ] 每月审查审计日志
- [ ] 每季度进行安全审计
- [ ] 每年进行渗透测试
- [ ] 及时更新依赖包
- [ ] 监控安全公告

---

## 漏洞报告

### 报告流程

如发现安全漏洞，请按以下步骤报告：

1. **不要公开披露** - 避免在公开渠道讨论
2. **发送邮件** - 发送至 security@xagent.dev
3. **提供详情** - 包含漏洞描述、复现步骤、影响范围
4. **等待回复** - 通常在48小时内回复

### 报告模板

```
主题: [SECURITY] 漏洞报告 - [漏洞类型]

漏洞描述:
[详细描述漏洞]

复现步骤:
1. [步骤1]
2. [步骤2]
3. [步骤3]

影响范围:
[受影响的版本、功能等]

建议修复:
[如有建议]

联系方式:
[你的邮箱]
```

### 漏洞赏金计划

我们感谢安全研究人员的贡献。根据漏洞严重程度：

- **Critical**: $1000-5000
- **High**: $500-1000
- **Medium**: $100-500
- **Low**: $50-100

---

## 常见安全问题

### Q1: 如何安全地存储API密钥？

**A**: 
- 使用环境变量或密钥管理服务(如AWS Secrets Manager)
- 不要在代码中硬编码
- 定期轮换密钥
- 使用最小权限原则

### Q2: 如何防止CSRF攻击？

**A**:
- 使用CSRF令牌
- 配置正确的CORS策略
- 使用SameSite Cookie属性
- 验证Referer头

### Q3: 如何保护敏感数据？

**A**:
- 使用HTTPS传输
- 加密存储
- 最小化日志中的敏感信息
- 实施访问控制

### Q4: 如何处理安全更新？

**A**:
- 订阅安全公告
- 定期更新依赖
- 测试更新
- 及时部署

### Q5: 如何审计用户操作？

**A**:
- 启用审计日志
- 记录所有关键操作
- 定期审查日志
- 设置告警规则

---

## 相关资源

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE Top 25](https://cwe.mitre.org/top25/)
- [NIST 网络安全框架](https://www.nist.gov/cyberframework)
- [API安全最佳实践](https://cheatsheetseries.owasp.org/)

---

**最后更新**: 2026-05-27  
**维护者**: X-Agent 安全团队  
**许可证**: MIT
