"""
Enterprise implementation guide and integration utilities.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Optional

from pydantic import BaseModel

# SECURITY (P1-05): All outbound HTTP calls to SSO/OAuth providers must have an
# explicit timeout to prevent hanging on unresponsive providers (DoS vector).
_HTTP_TIMEOUT_SECONDS = 30


# ============================================================================
# IMPLEMENTATION GUIDE
# ============================================================================

IMPLEMENTATION_GUIDE = """
# X-Agent 企业版实施指南

## 第一阶段：规划和准备（1-2 周）

### 1.1 需求分析
- [ ] 确定租户数量和用户规模
- [ ] 识别 SSO 提供商
- [ ] 定义权限模型
- [ ] 确定合规需求
- [ ] 评估集成需求

### 1.2 环境准备
- [ ] 准备生产环境
- [ ] 配置数据库
- [ ] 配置缓存系统
- [ ] 配置日志系统
- [ ] 配置监控系统

### 1.3 安全准备
- [ ] 生成 SSL 证书
- [ ] 配置防火墙规则
- [ ] 准备备份策略
- [ ] 准备灾难恢复计划
- [ ] 进行安全审计

---

## 第二阶段：部署和配置（2-3 周）

### 2.1 系统部署
```bash
# 1. 克隆代码
git clone https://github.com/x-agent/x-agent.git
cd x-agent

# 2. 安装依赖
pip install -r requirements.txt

# 3. 初始化数据库
python -m backend.scripts.init_enterprise_db

# 4. 启动服务
docker-compose -f docker-compose.enterprise.yml up -d
```

### 2.2 企业功能配置
```bash
# 1. 配置多租户
python -m backend.scripts.configure_multitenancy

# 2. 配置 SSO
python -m backend.scripts.configure_sso --provider okta

# 3. 配置 RBAC
python -m backend.scripts.configure_rbac

# 4. 配置审计日志
python -m backend.scripts.configure_audit_logging
```

### 2.3 初始租户创建
```bash
# 创建初始租户
python -m backend.scripts.create_tenant \\
  --name "Your Company" \\
  --plan enterprise \\
  --organization-name "Your Organization" \\
  --admin-email admin@yourcompany.com
```

---

## 第三阶段：集成和测试（2-3 周）

### 3.1 SSO 集成
- [ ] 配置 Okta/Azure AD/Google
- [ ] 测试用户登录
- [ ] 测试自动用户配置
- [ ] 测试用户同步
- [ ] 测试登出流程

### 3.2 API 集成
- [ ] 创建 API 密钥
- [ ] 测试 API 调用
- [ ] 配置速率限制
- [ ] 测试错误处理
- [ ] 文档化 API 使用

### 3.3 系统集成
- [ ] 集成监控系统
- [ ] 集成日志系统
- [ ] 集成告警系统
- [ ] 集成备份系统
- [ ] 集成灾难恢复

### 3.4 测试计划
- [ ] 功能测试
- [ ] 性能测试
- [ ] 安全测试
- [ ] 压力测试
- [ ] 用户验收测试 (UAT)

---

## 第四阶段：培训和上线（1-2 周）

### 4.1 管理员培训
- [ ] 系统管理
- [ ] 用户管理
- [ ] 权限管理
- [ ] 审计日志查看
- [ ] 故障排除

### 4.2 用户培训
- [ ] 系统登录
- [ ] 基本功能
- [ ] 工作流使用
- [ ] 报告生成
- [ ] 支持联系

### 4.3 上线准备
- [ ] 数据迁移
- [ ] 用户导入
- [ ] 权限配置
- [ ] 工作流配置
- [ ] 集成测试

### 4.4 上线执行
- [ ] 上线前检查
- [ ] 数据备份
- [ ] 系统切换
- [ ] 监控和支持
- [ ] 上线后评估

---

## 第五阶段：优化和支持（持续）

### 5.1 性能优化
- [ ] 监控系统性能
- [ ] 优化数据库查询
- [ ] 优化缓存策略
- [ ] 优化 API 响应
- [ ] 优化存储使用

### 5.2 安全加固
- [ ] 定期安全审计
- [ ] 漏洞扫描
- [ ] 渗透测试
- [ ] 安全补丁更新
- [ ] 安全培训

### 5.3 持续支持
- [ ] 技术支持
- [ ] 问题解决
- [ ] 功能增强
- [ ] 定期评审
- [ ] 续约管理

---

## 实施时间表示例

```
第 1-2 周：规划和准备
├─ 需求分析
├─ 环境准备
└─ 安全准备

第 3-5 周：部署和配置
├─ 系统部署
├─ 企业功能配置
└─ 初始租户创建

第 6-8 周：集成和测试
├─ SSO 集成
├─ API 集成
├─ 系统集成
└─ 测试计划

第 9-10 周：培训和上线
├─ 管理员培训
├─ 用户培训
├─ 上线准备
└─ 上线执行

第 11+ 周：优化和支持
├─ 性能优化
├─ 安全加固
└─ 持续支持
```

---

## 常见问题

**Q: 实施需要多长时间？**
A: 通常 8-10 周，取决于复杂性和团队规模。

**Q: 需要多少人力？**
A: 建议 2-3 名工程师 + 1 名项目经理。

**Q: 如何处理数据迁移？**
A: 我们提供数据迁移工具和支持。

**Q: 如何处理停机时间？**
A: 我们支持零停机部署。

**Q: 如何处理用户培训？**
A: 我们提供在线培训和文档。
"""


# ============================================================================
# INTEGRATION UTILITIES
# ============================================================================

class IntegrationConfig(BaseModel):
    """Integration configuration."""
    name: str
    type: str  # "sso", "api", "webhook", "custom"
    enabled: bool = True
    config: dict[str, Any]


class SSO_OktaIntegration:
    """Okta SSO integration."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.domain = config.get("domain")
        self.client_id = config.get("client_id")
        self.client_secret = config.get("client_secret")
        self.authorization_server = config.get("authorization_server", "default")

    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        """Get Okta authorization URL."""
        return (
            f"{self.domain}/oauth2/{self.authorization_server}/v1/authorize?"
            f"client_id={self.client_id}&"
            f"redirect_uri={redirect_uri}&"
            f"response_type=code&"
            f"scope=openid%20profile%20email&"
            f"state={state}"
        )

    def exchange_code_for_token(self, code: str, redirect_uri: str) -> dict[str, Any]:
        """Exchange authorization code for access token."""
        import requests

        token_url = f"{self.domain}/oauth2/{self.authorization_server}/v1/token"
        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        }

        response = requests.post(token_url, data=data, timeout=_HTTP_TIMEOUT_SECONDS)
        return response.json()

    def get_user_info(self, access_token: str) -> dict[str, Any]:
        """Get user information from Okta."""
        import requests

        userinfo_url = f"{self.domain}/oauth2/{self.authorization_server}/v1/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}

        response = requests.get(userinfo_url, headers=headers, timeout=_HTTP_TIMEOUT_SECONDS)
        return response.json()


class SSO_AzureADIntegration:
    """Azure AD SSO integration."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.tenant_id = config.get("tenant_id")
        self.client_id = config.get("client_id")
        self.client_secret = config.get("client_secret")
        self.authority = config.get("authority")

    def get_authorization_url(self, redirect_uri: str, state: str) -> str:
        """Get Azure AD authorization URL."""
        return (
            f"{self.authority}/oauth2/v2.0/authorize?"
            f"client_id={self.client_id}&"
            f"redirect_uri={redirect_uri}&"
            f"response_type=code&"
            f"scope=openid%20profile%20email&"
            f"state={state}"
        )

    def exchange_code_for_token(self, code: str, redirect_uri: str) -> dict[str, Any]:
        """Exchange authorization code for access token."""
        import requests

        token_url = f"{self.authority}/oauth2/v2.0/token"
        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
            "scope": "openid profile email",
        }

        response = requests.post(token_url, data=data, timeout=_HTTP_TIMEOUT_SECONDS)
        return response.json()

    def get_user_info(self, access_token: str) -> dict[str, Any]:
        """Get user information from Azure AD."""
        import requests

        userinfo_url = "https://graph.microsoft.com/v1.0/me"
        headers = {"Authorization": f"Bearer {access_token}"}

        response = requests.get(userinfo_url, headers=headers, timeout=_HTTP_TIMEOUT_SECONDS)
        return response.json()


class WebhookIntegration:
    """Webhook integration for event notifications."""

    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    def send_event(self, event_type: str, data: dict[str, Any]) -> bool:
        """Send event to webhook."""
        import requests

        payload = {
            "event_type": event_type,
            "timestamp": datetime.now(UTC).isoformat(),
            "data": data,
        }

        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10,
            )
            return response.status_code == 200
        except Exception:
            return False


class SlackIntegration:
    """Slack integration for notifications."""

    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    def send_message(self, message: str, channel: Optional[str] = None) -> bool:
        """Send message to Slack."""
        import requests

        payload = {
            "text": message,
        }

        if channel:
            payload["channel"] = channel

        try:
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            return response.status_code == 200
        except Exception:
            return False

    def send_alert(
        self,
        title: str,
        message: str,
        severity: str = "warning",
        channel: Optional[str] = None,
    ) -> bool:
        """Send alert to Slack."""
        color_map = {
            "info": "#36a64f",
            "warning": "#ff9900",
            "error": "#ff0000",
        }

        payload = {
            "attachments": [
                {
                    "color": color_map.get(severity, "#36a64f"),
                    "title": title,
                    "text": message,
                    "ts": int(datetime.now(UTC).timestamp()),
                }
            ]
        }

        if channel:
            payload["channel"] = channel

        try:
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            return response.status_code == 200
        except Exception:
            return False


class JiraIntegration:
    """Jira integration for issue tracking."""

    def __init__(self, base_url: str, username: str, api_token: str) -> None:
        self.base_url = base_url
        self.username = username
        self.api_token = api_token

    def create_issue(
        self,
        project_key: str,
        issue_type: str,
        summary: str,
        description: str,
        priority: str = "Medium",
    ) -> Optional[str]:
        """Create a Jira issue."""
        import requests
        from base64 import b64encode

        url = f"{self.base_url}/rest/api/3/issues"
        auth = b64encode(f"{self.username}:{self.api_token}".encode()).decode()

        payload = {
            "fields": {
                "project": {"key": project_key},
                "issuetype": {"name": issue_type},
                "summary": summary,
                "description": {"content": [{"content": [{"text": description}], "type": "paragraph"}]},
                "priority": {"name": priority},
            }
        }

        headers = {
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            if response.status_code == 201:
                return response.json().get("key")
        except Exception:
            pass

        return None


# ============================================================================
# MIGRATION UTILITIES
# ============================================================================

class DataMigrationHelper:
    """Helper for migrating data to enterprise version."""

    @staticmethod
    def export_users(users: list[dict[str, Any]]) -> str:
        """Export users to JSON."""
        return json.dumps(users, indent=2, default=str)

    @staticmethod
    def export_workflows(workflows: list[dict[str, Any]]) -> str:
        """Export workflows to JSON."""
        return json.dumps(workflows, indent=2, default=str)

    @staticmethod
    def export_audit_logs(logs: list[dict[str, Any]]) -> str:
        """Export audit logs to JSON."""
        return json.dumps(logs, indent=2, default=str)

    @staticmethod
    def import_users(data: str, tenant_id: str) -> list[dict[str, Any]]:
        """Import users from JSON."""
        users = json.loads(data)
        for user in users:
            user["tenant_id"] = tenant_id
        return users

    @staticmethod
    def import_workflows(data: str, tenant_id: str) -> list[dict[str, Any]]:
        """Import workflows from JSON."""
        workflows = json.loads(data)
        for workflow in workflows:
            workflow["tenant_id"] = tenant_id
        return workflows


# ============================================================================
# MONITORING AND HEALTH CHECK
# ============================================================================

class HealthChecker:
    """Health check utilities."""

    @staticmethod
    def check_database(connection_string: str) -> bool:
        """Check database connectivity."""
        try:
            import psycopg2

            conn = psycopg2.connect(connection_string)
            conn.close()
            return True
        except Exception:
            return False

    @staticmethod
    def check_redis(host: str, port: int) -> bool:
        """Check Redis connectivity."""
        try:
            import redis

            r = redis.Redis(host=host, port=port, socket_connect_timeout=5)
            r.ping()
            return True
        except Exception:
            return False

    @staticmethod
    def check_sso(sso_config: dict[str, Any]) -> bool:
        """Check SSO configuration."""
        try:
            provider = sso_config.get("provider")
            if provider == "okta":
                integration = SSO_OktaIntegration(sso_config.get("config", {}))
                # Try to get authorization URL
                integration.get_authorization_url("http://localhost", "test")
                return True
            elif provider == "azure_ad":
                integration = SSO_AzureADIntegration(sso_config.get("config", {}))
                # Try to get authorization URL
                integration.get_authorization_url("http://localhost", "test")
                return True
        except Exception:
            pass

        return False


# ============================================================================
# CONFIGURATION TEMPLATES
# ============================================================================

OKTA_CONFIG_TEMPLATE = {
    "provider": "okta",
    "config": {
        "domain": "https://your-domain.okta.com",
        "client_id": "YOUR_CLIENT_ID",
        "client_secret": "YOUR_CLIENT_SECRET",
        "authorization_server": "default",
        "scopes": ["openid", "profile", "email"],
    },
}

AZURE_AD_CONFIG_TEMPLATE = {
    "provider": "azure_ad",
    "config": {
        "tenant_id": "YOUR_TENANT_ID",
        "client_id": "YOUR_CLIENT_ID",
        "client_secret": "YOUR_CLIENT_SECRET",
        "authority": "https://login.microsoftonline.com/YOUR_TENANT_ID",
    },
}

GOOGLE_CONFIG_TEMPLATE = {
    "provider": "google_workspace",
    "config": {
        "client_id": "YOUR_CLIENT_ID",
        "client_secret": "YOUR_CLIENT_SECRET",
        "scopes": ["openid", "profile", "email"],
    },
}
