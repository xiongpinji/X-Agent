# X-Agent 常见问题解答 (FAQ)

完整的常见问题和解答集合，涵盖安装、功能、故障排除、性能和安全等方面。

## 目录

- [安装和配置 (10个问题)](#安装和配置)
- [功能使用 (15个问题)](#功能使用)
- [故障排除 (10个问题)](#故障排除)
- [性能优化 (5个问题)](#性能优化)
- [安全和隐私 (5个问题)](#安全和隐私)
- [集成和扩展 (5个问题)](#集成和扩展)
- [高级主题 (5个问题)](#高级主题)

---

## 安装和配置

### 1. X-Agent 的系统要求是什么？

**答**：最低要求：
- Python 3.11 或更高版本
- PostgreSQL 14 或更高版本
- 4GB RAM（推荐 8GB）
- 2GB 磁盘空间
- Linux、macOS 或 Windows 10+

推荐配置：
- Python 3.12+
- PostgreSQL 15+
- 8GB+ RAM
- SSD 存储
- 4+ CPU 核心

### 2. 我可以在 Windows 上运行 X-Agent 吗？

**答**：可以。我们推荐两种方式：
1. **WSL2（推荐）**：在 Windows 上运行 Linux 子系统
2. **原生 Windows**：直接安装 Python 和 PostgreSQL

WSL2 提供更好的兼容性和性能。详见 [安装指南](../setup/INSTALL.md)。

### 3. Docker 是必需的吗？

**答**：不是必需的，但强烈推荐。Docker 提供：
- 快速数据库设置（无需手动安装 PostgreSQL）
- 一致的开发环境
- 简化的生产部署
- 隔离的测试环境

如果不使用 Docker，需要手动安装 PostgreSQL 和 Qdrant。

### 4. 如何升级 X-Agent 到最新版本？

**答**：
```bash
# 拉取最新代码
git pull origin main

# 更新依赖
pip install -e ".[dev]" --upgrade

# 运行数据库迁移
python -m backend.app.core.migration init

# 重启服务
docker-compose restart
```

### 5. 我可以使用现有的 PostgreSQL 数据库吗？

**答**：可以。在 `.env` 文件中配置连接字符串：
```bash
DATABASE_URL=postgresql://user:password@your-host:5432/your-db
```

确保数据库用户有创建表和索引的权限。

### 6. 如何配置多个 LLM 提供商？

**答**：在 `.env` 中配置多个 API 密钥：
```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
DEEPSEEK_API_KEY=sk-...
```

然后在 Agent 配置中指定使用哪个提供商。LLM Router 会自动选择最优提供商。

### 7. 环境变量有哪些？

**答**：关键环境变量：

| 变量 | 说明 | 必需 |
|------|------|------|
| `DATABASE_URL` | PostgreSQL 连接字符串 | 是 |
| `QDRANT_URL` | Qdrant 向量数据库 URL | 是 |
| `OPENAI_API_KEY` | OpenAI API 密钥 | 否 |
| `ANTHROPIC_API_KEY` | Anthropic API 密钥 | 否 |
| `SECRET_KEY` | JWT 密钥 | 是 |
| `SERVER_PORT` | 服务器端口 | 否（默认 8000） |
| `DEBUG` | 调试模式 | 否（默认 false） |

详见 [环境配置指南](../setup/ENVIRONMENT.md)。

### 8. 如何在生产环境中部署 X-Agent？

**答**：推荐步骤：
1. 使用 Gunicorn 或 uWSGI 作为 ASGI 服务器
2. 配置 Nginx 作为反向代理
3. 使用 SSL/TLS 加密
4. 配置数据库备份和恢复
5. 设置监控和告警

详见 [部署指南](../deployment/DEPLOYMENT_GUIDE.md)。

### 9. 如何重置数据库？

**答**：
```bash
# 删除所有数据（谨慎！）
docker-compose down -v

# 重新初始化
docker-compose up -d
python -m backend.app.core.migration init
```

### 10. 支持哪些数据库版本？

**答**：
- PostgreSQL 14+ （推荐 15+）
- Qdrant 1.0+
- Redis 6.0+（可选，用于缓存）

---

## 功能使用

### 11. 什么是 Agent？

**答**：Agent 是 X-Agent 的核心概念，代表一个自主执行任务的实体。每个 Agent 具有：
- 特定的能力和配置
- 访问工具和记忆的权限
- 独立的执行上下文
- 可配置的 LLM 模型

### 12. 如何创建一个 Agent？

**答**：
```python
import requests

agent_data = {
    "name": "MyAgent",
    "description": "My custom agent",
    "capabilities": ["reasoning", "planning", "tool_use"],
    "model": "gpt-4",
    "temperature": 0.7
}

response = requests.post(
    "http://localhost:8000/api/v1/agents",
    json=agent_data
)
agent = response.json()
```

### 13. Agent 的生命周期是什么？

**答**：Agent 状态流转：
1. **created** - 新创建的 Agent
2. **idle** - 等待任务
3. **running** - 执行中
4. **paused** - 暂停（等待批准）
5. **completed** - 任务完成
6. **failed** - 执行失败
7. **archived** - 已归档

### 14. 什么是 Workflow（工作流）？

**答**：Workflow 是多步骤任务的编排系统，支持：
- DAG（有向无环图）结构
- 条件分支和循环
- 并行执行
- 错误处理和重试
- 人工审批

### 15. 如何定义一个工作流？

**答**：
```python
workflow_data = {
    "name": "DataProcessingWorkflow",
    "steps": [
        {
            "id": "step1",
            "type": "agent_task",
            "agent_id": "agent1",
            "task": "Extract data from source"
        },
        {
            "id": "step2",
            "type": "agent_task",
            "agent_id": "agent2",
            "task": "Transform data",
            "depends_on": ["step1"]
        },
        {
            "id": "step3",
            "type": "approval",
            "depends_on": ["step2"]
        }
    ]
}

response = requests.post(
    "http://localhost:8000/api/v1/workflows",
    json=workflow_data
)
```

### 16. 什么是 Memory（记忆）系统？

**答**：Memory 系统提供：
- 持久化知识存储
- 语义搜索和相似度匹配
- 关系图谱（Neo4j）
- 向量嵌入（Qdrant）
- 跨会话信息保留

### 17. 如何在 Agent 中使用记忆？

**答**：
```python
# 存储信息
memory_data = {
    "content": "User prefers JSON format",
    "type": "preference",
    "tags": ["user_preference", "format"]
}

response = requests.post(
    f"http://localhost:8000/api/v1/agents/{agent_id}/memory",
    json=memory_data
)

# 检索信息
response = requests.get(
    f"http://localhost:8000/api/v1/agents/{agent_id}/memory/search",
    params={"query": "user preferences"}
)
```

### 18. 支持哪些工具和集成？

**答**：内置工具包括：
- 浏览器自动化（Playwright）
- 文件系统操作
- 数据库查询
- API 调用
- 代码执行
- 邮件发送

可以通过插件系统扩展。

### 19. 如何添加自定义工具？

**答**：创建工具插件：
```python
from backend.app.core.tools import BaseTool

class MyCustomTool(BaseTool):
    name = "my_tool"
    description = "My custom tool"
    
    def execute(self, **kwargs):
        # 实现工具逻辑
        return result
```

详见 [工具开发指南](../../developer/plugins/PLUGIN_DEVELOPMENT_GUIDE.md)。

### 20. 什么是多 Agent 协作？

**答**：多 Agent 协作允许多个 Agent 协同工作：
- 任务委派和分配
- 能力匹配和负载均衡
- 消息传递和通信
- 结果聚合和综合

### 21. 如何启用多 Agent 协作？

**答**：
```python
collaboration_config = {
    "enabled": True,
    "agents": ["agent1", "agent2", "agent3"],
    "strategy": "capability_matching",
    "load_balancing": "round_robin"
}

response = requests.post(
    "http://localhost:8000/api/v1/collaboration",
    json=collaboration_config
)
```

### 22. 什么是 Approval Workflow（审批工作流）？

**答**：审批工作流用于敏感操作，需要人工确认：
- 数据删除操作
- 系统配置更改
- 高成本操作
- 安全相关操作

### 23. 如何配置审批流程？

**答**：
```python
approval_config = {
    "operation": "delete_data",
    "approvers": ["admin@company.com"],
    "timeout": 3600,  # 1小时
    "require_all": True  # 需要所有审批者同意
}

response = requests.post(
    "http://localhost:8000/api/v1/approvals",
    json=approval_config
)
```

### 25. 如何监控 Agent 执行？

**答**：使用 Langfuse 集成进行完整的链路追踪：
```bash
# 在 .env 中配置
LANGFUSE_PUBLIC_KEY=your_key
LANGFUSE_SECRET_KEY=your_secret
LANGFUSE_HOST=https://cloud.langfuse.com
```

然后访问 Langfuse 仪表板查看执行详情。

---

## 故障排除

### 26. 端口 8000 已被占用，怎么办？

**答**：
```bash
# 方法1：使用不同的端口
uvicorn backend.app.web:app --port 8001

# 方法2：查找并杀死占用端口的进程
# Linux/macOS:
lsof -i :8000
kill -9 <PID>

# Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### 27. 数据库连接失败，怎么办？

**答**：
```bash
# 1. 检查 Docker 容器状态
docker-compose ps

# 2. 查看 PostgreSQL 日志
docker-compose logs postgres

# 3. 测试连接
psql -U xagent -h localhost -d xagent_db

# 4. 重启 PostgreSQL
docker-compose restart postgres

# 5. 检查 .env 中的 DATABASE_URL
```

### 28. 模块导入错误，怎么办？

**答**：
```bash
# 1. 确保虚拟环境已激活
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate  # Windows

# 2. 重新安装依赖
pip install -e ".[dev]" --force-reinstall

# 3. 清除缓存
pip cache purge

# 4. 检查 Python 版本
python --version  # 应为 3.11+
```

### 29. API 返回 500 错误，怎么办？

**答**：
```bash
# 1. 查看服务器日志
# 在运行 uvicorn 的终端中查看错误信息

# 2. 启用调试模式
DEBUG=true uvicorn backend.app.web:app --reload

# 3. 检查数据库连接
curl http://localhost:8000/health

# 4. 查看详细错误
# 访问 http://localhost:8000/docs 查看 API 文档
```

### 30. Agent 任务卡住不动，怎么办？

**答**：
```bash
# 1. 检查任务状态
curl http://localhost:8000/api/v1/agents/{agent_id}/tasks/{task_id}

# 2. 查看执行日志
# 在 Langfuse 仪表板中查看链路追踪

# 3. 手动取消任务
curl -X POST http://localhost:8000/api/v1/agents/{agent_id}/tasks/{task_id}/cancel

# 4. 重启 Agent
curl -X POST http://localhost:8000/api/v1/agents/{agent_id}/restart
```

### 31. 内存使用过高，怎么办？

**答**：
```bash
# 1. 检查内存使用
docker stats

# 2. 清理旧数据
python -m backend.app.core.maintenance cleanup_old_tasks --days 30

# 3. 优化数据库
docker-compose exec postgres psql -U xagent -d xagent_db -c "VACUUM ANALYZE;"

# 4. 增加容器内存限制
# 编辑 docker-compose.yml，添加 mem_limit
```

### 32. Qdrant 连接失败，怎么办？

**答**：
```bash
# 1. 检查 Qdrant 状态
curl http://localhost:6333/health

# 2. 查看日志
docker-compose logs qdrant

# 3. 重启 Qdrant
docker-compose restart qdrant

# 4. 检查 .env 中的 QDRANT_URL
```

### 33. 测试失败，怎么办？

**答**：
```bash
# 1. 运行单个测试
pytest tests/test_specific.py -v

# 2. 查看详细输出
pytest -vv --tb=long

# 3. 运行特定测试类
pytest tests/test_agents.py::TestAgentCreation -v

# 4. 生成覆盖率报告
pytest --cov=backend --cov-report=html
```

### 34. 虚拟环境问题，怎么办？

**答**：
```bash
# 1. 删除旧虚拟环境
rm -rf venv  # Linux/macOS
rmdir /s venv  # Windows

# 2. 创建新虚拟环境
python -m venv venv

# 3. 激活虚拟环境
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate  # Windows

# 4. 重新安装依赖
pip install -e ".[dev]"
```

### 35. 权限被拒绝错误，怎么办？

**答**：
```bash
# Linux/macOS:
# 1. 检查文件权限
ls -la

# 2. 修改权限
chmod +x script.sh

# 3. 使用 sudo（如需要）
sudo chown -R $USER:$USER .

# Windows:
# 以管理员身份运行 PowerShell 或 CMD
```

---

## 性能优化

### 36. 如何提高 Agent 执行速度？

**答**：
1. **使用更快的 LLM 模型**：gpt-3.5-turbo 比 gpt-4 快
2. **启用缓存**：配置 Redis 缓存
3. **优化提示**：减少提示长度
4. **并行执行**：使用工作流的并行步骤
5. **增加资源**：更多 CPU 和内存

### 37. 如何优化数据库性能？

**答**：
```bash
# 1. 创建索引
docker-compose exec postgres psql -U xagent -d xagent_db -c "
CREATE INDEX idx_memory_embedding ON memory USING ivfflat (embedding);
CREATE INDEX idx_tasks_status ON tasks(status);
"

# 2. 运行 VACUUM
docker-compose exec postgres psql -U xagent -d xagent_db -c "VACUUM ANALYZE;"

# 3. 调整连接池
# 在 .env 中设置
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10
```

### 38. 如何减少 API 响应时间？

**答**：
1. **启用 Redis 缓存**：缓存频繁查询
2. **使用 CDN**：缓存静态资源
3. **启用 gzip 压缩**：减少传输大小
4. **优化查询**：避免 N+1 查询问题
5. **使用异步操作**：非阻塞 I/O

### 39. 如何监控性能指标？

**答**：
```bash
# 1. 启用 Prometheus 指标
# 在 .env 中设置
PROMETHEUS_ENABLED=true

# 2. 访问指标端点
curl http://localhost:8000/metrics

# 3. 配置 Grafana 仪表板
# 连接到 Prometheus 数据源

# 4. 设置告警规则
# 在 Prometheus 中配置告警
```

### 40. 如何处理大规模数据？

**答**：
1. **分批处理**：将大任务分成小批次
2. **流式处理**：使用流式 API
3. **分片存储**：将数据分片存储
4. **异步处理**：使用后台任务队列
5. **增加资源**：扩展数据库和服务器

---

## 安全和隐私

### 41. X-Agent 如何保护数据安全？

**答**：
- **加密传输**：使用 HTTPS/TLS
- **加密存储**：敏感数据加密
- **访问控制**：基于角色的权限管理
- **审计日志**：记录所有操作
- **定期备份**：自动备份和恢复

### 42. 如何配置 SSL/TLS？

**答**：
```bash
# 1. 生成自签名证书（开发用）
openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365

# 2. 配置 Nginx
# 在 nginx.conf 中添加
ssl_certificate /path/to/cert.pem;
ssl_certificate_key /path/to/key.pem;

# 3. 使用 Let's Encrypt（生产用）
# 使用 Certbot 自动配置
```

### 43. 如何管理 API 密钥？

**答**：
```bash
# 1. 使用环境变量（不要硬编码）
export OPENAI_API_KEY=sk-...

# 2. 使用密钥管理服务
# AWS Secrets Manager、Azure Key Vault 等

# 3. 定期轮换密钥
# 每 90 天更换一次

# 4. 限制密钥权限
# 只授予必要的权限
```

### 44. 如何实施访问控制？

**答**：
```python
# 配置基于角色的访问控制 (RBAC)
rbac_config = {
    "roles": {
        "admin": ["read", "write", "delete", "manage_users"],
        "user": ["read", "write"],
        "viewer": ["read"]
    },
    "users": {
        "user@example.com": "admin"
    }
}
```

### 45. 如何审计操作日志？

**答**：
```bash
# 1. 启用审计日志
AUDIT_LOG_ENABLED=true
AUDIT_LOG_PATH=/var/log/xagent/audit.log

# 2. 查看审计日志
tail -f /var/log/xagent/audit.log

# 3. 分析审计日志
grep "DELETE" /var/log/xagent/audit.log
```

---

## 集成和扩展

### 46. 如何集成外部 API？

**答**：
```python
# 创建自定义工具集成
class ExternalAPITool(BaseTool):
    name = "external_api"
    
    def execute(self, endpoint, method="GET", **kwargs):
        import requests
        response = requests.request(method, endpoint, **kwargs)
        return response.json()
```

### 47. 如何开发自定义插件？

**答**：详见 [插件开发指南](../../developer/plugins/PLUGIN_DEVELOPMENT_GUIDE.md)。基本步骤：
1. 创建插件目录结构
2. 实现插件接口
3. 编写测试
4. 打包和发布

### 48. 支持哪些第三方集成？

**答**：
- **数据库**：PostgreSQL、MongoDB、MySQL
- **消息队列**：RabbitMQ、Kafka
- **监控**：Prometheus、Grafana、Datadog
- **日志**：ELK Stack、Splunk
- **CI/CD**：GitHub Actions、GitLab CI

### 49. 如何与 Slack 集成？

**答**：
```python
# 创建 Slack 集成
slack_config = {
    "webhook_url": "https://hooks.slack.com/services/...",
    "channel": "#xagent-notifications",
    "events": ["task_completed", "task_failed"]
}

# 在 Agent 中使用
agent.add_integration("slack", slack_config)
```

### 50. 如何与 GitHub 集成？

**答**：
```python
# 配置 GitHub 集成
github_config = {
    "token": "ghp_...",
    "owner": "your-org",
    "repo": "your-repo",
    "actions": ["create_issue", "create_pr"]
}

# 在工作流中使用
workflow.add_step({
    "type": "github_action",
    "action": "create_issue",
    "title": "Task completed"
})
```

---

## 高级主题

### 51. 如何实现自定义 LLM 路由策略？

**答**：
```python
class CustomRouter(BaseLLMRouter):
    def select_provider(self, task):
        if task.cost_sensitive:
            return "gpt-3.5-turbo"  # 便宜
        elif task.requires_reasoning:
            return "gpt-4"  # 强大
        else:
            return "claude"  # 平衡
```

### 52. 如何实现自定义记忆后端？

**答**：
```python
class CustomMemory(BaseMemory):
    def store(self, key, value):
        # 自定义存储逻辑
        pass
    
    def retrieve(self, key):
        # 自定义检索逻辑
        pass
```

### 53. 如何扩展工作流引擎？

**答**：
```python
class CustomWorkflowStep(BaseWorkflowStep):
    def execute(self):
        # 自定义步骤逻辑
        pass
    
    def on_error(self, error):
        # 自定义错误处理
        pass
```

### 54. 如何实现自定义审批流程？

**答**：
```python
class CustomApprovalFlow(BaseApprovalFlow):
    def get_approvers(self, operation):
        # 自定义审批者选择逻辑
        pass
    
    def notify_approvers(self, approvers):
        # 自定义通知逻辑
        pass
```

### 55. 如何贡献代码到 X-Agent？

**答**：
1. Fork 仓库
2. 创建特性分支：`git checkout -b feature/my-feature`
3. 提交更改：`git commit -am 'Add feature'`
4. 推送到分支：`git push origin feature/my-feature`
5. 创建 Pull Request

详见 [贡献指南](../../developer/contributing/CONTRIBUTING_DOCS.md)。

---

## 获取更多帮助

- 📖 完整文档：[docs/README.md](./README.md)
- 🚀 快速入门：[QUICK_START_GUIDE.md](../setup/QUICK_START_GUIDE.md)
- 🔧 故障排除：[TROUBLESHOOTING_GUIDE.md](./TROUBLESHOOTING_GUIDE.md)
- 🐛 报告问题：[GitHub Issues](https://github.com/x-agent/x-agent-core/issues)
- 💬 讨论：[GitHub Discussions](https://github.com/x-agent/x-agent-core/discussions)
- 📧 联系支持：support@x-agent.dev

---

**最后更新**：2026年5月29日
