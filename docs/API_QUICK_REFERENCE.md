# X-Agent API 快速参考

## 认证

### API Key 认证
```bash
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/v1/agents
```

### JWT Token 认证
```bash
curl -H "Authorization: Bearer your-jwt-token" http://localhost:8000/api/v1/agents
```

## 常用端点速查表

| 操作 | 方法 | 端点 | 权限 |
|------|------|------|------|
| 创建 Agent | POST | `/agents` | `security:manage` |
| 列出 Agents | GET | `/agents` | `agent:run` |
| 获取 Agent | GET | `/agents/{id}` | `agent:run` |
| 更新 Agent | PUT | `/agents/{id}` | `security:manage` |
| 删除 Agent | DELETE | `/agents/{id}` | `security:manage` |
| 暂停 Agent | POST | `/agents/{id}/pause` | `security:manage` |
| 创建 Workflow | POST | `/workflows` | `workflow:create` |
| 列出 Workflows | GET | `/workflows` | `workflow:run` |
| 获取 Workflow 状态 | GET | `/workflows/status` | `workflow:run` |
| 启动运行 | POST | `/runs/start` | `agent:run` |
| 列出运行 | GET | `/runs` | `agent:read` |
| 存储记忆 | POST | `/memory` | `memory:write` |
| 搜索记忆 | POST | `/memory/search` | `memory:read` |
| 导出记忆 | GET | `/memory/export` | `memory:read` |
| 列出工具 | GET | `/tools` | `tools:read` |
| 获取工具执行 | GET | `/tools/executions/{id}` | `agent:run` |
| 列出追踪 | GET | `/traces` | `agent:read` |
| 列出审计日志 | GET | `/audit` | `audit:read` |

## 常见请求示例

### 1. 启动 Agent 运行

```bash
curl -X POST http://localhost:8000/api/v1/runs/start \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Analyze sales data",
    "extra_context": {
      "period": "Q1 2025"
    },
    "async_run": false
  }'
```

### 2. 搜索记忆

```bash
curl -X POST http://localhost:8000/api/v1/memory/search \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "user preferences",
    "top_k": 5,
    "layers": [1, 2, 3]
  }'
```

### 3. 创建 Workflow

```bash
curl -X POST http://localhost:8000/api/v1/workflows \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Data Pipeline",
    "description": "ETL workflow",
    "nodes": [
      {"id": "n1", "type": "start", "label": "Start"},
      {"id": "n2", "type": "task", "label": "Process"}
    ],
    "edges": [{"source": "n1", "target": "n2"}]
  }'
```

### 4. 列出 Agents

```bash
curl http://localhost:8000/api/v1/agents \
  -H "X-API-Key: your-api-key"
```

### 5. 获取工具列表

```bash
curl http://localhost:8000/api/v1/tools \
  -H "X-API-Key: your-api-key"
```

## 错误码参考

| 状态码 | 错误码 | 说明 |
|--------|--------|------|
| 400 | INVALID_REQUEST | 请求参数无效 |
| 401 | UNAUTHORIZED | 未授权或 API Key 无效 |
| 403 | FORBIDDEN | 权限不足 |
| 404 | RESOURCE_NOT_FOUND | 资源不存在 |
| 409 | CONFLICT | 资源冲突 |
| 429 | RATE_LIMIT_EXCEEDED | 超过速率限制 |
| 500 | INTERNAL_ERROR | 服务器内部错误 |

## 速率限制

- 登录: 10 请求/60 秒
- 注册: 5 请求/60 秒
- 其他 API: 100 请求/60 秒

## Python 客户端示例

```python
import requests
import json

class XAgentClient:
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        }
    
    def start_run(self, task, context=None):
        """启动 Agent 运行"""
        data = {
            "task": task,
            "extra_context": context or {},
            "async_run": False
        }
        response = requests.post(
            f"{self.base_url}/api/v1/runs/start",
            headers=self.headers,
            json=data
        )
        return response.json()
    
    def list_agents(self):
        """列出所有 Agents"""
        response = requests.get(
            f"{self.base_url}/api/v1/agents",
            headers=self.headers
        )
        return response.json()
    
    def search_memory(self, query, top_k=5):
        """搜索记忆"""
        data = {
            "query": query,
            "top_k": top_k,
            "include_scores": True
        }
        response = requests.post(
            f"{self.base_url}/api/v1/memory/search",
            headers=self.headers,
            json=data
        )
        return response.json()
    
    def store_memory(self, content, layer=2, importance=0.5):
        """存储记忆"""
        data = {
            "content": content,
            "layer": layer,
            "importance": importance
        }
        response = requests.post(
            f"{self.base_url}/api/v1/memory",
            headers=self.headers,
            json=data
        )
        return response.json()

# 使用示例
client = XAgentClient("http://localhost:8000", "your-api-key")

# 启动运行
result = client.start_run("Analyze Q1 sales data")
print(json.dumps(result, indent=2))

# 列出 Agents
agents = client.list_agents()
print(json.dumps(agents, indent=2))

# 搜索记忆
memories = client.search_memory("user preferences")
print(json.dumps(memories, indent=2))
```

## JavaScript/Node.js 客户端示例

```javascript
class XAgentClient {
  constructor(baseUrl, apiKey) {
    this.baseUrl = baseUrl;
    this.apiKey = apiKey;
  }

  async request(method, endpoint, data = null) {
    const url = `${this.baseUrl}/api/v1${endpoint}`;
    const options = {
      method,
      headers: {
        "X-API-Key": this.apiKey,
        "Content-Type": "application/json"
      }
    };

    if (data) {
      options.body = JSON.stringify(data);
    }

    const response = await fetch(url, options);
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    return response.json();
  }

  async startRun(task, context = {}) {
    return this.request("POST", "/runs/start", {
      task,
      extra_context: context,
      async_run: false
    });
  }

  async listAgents() {
    return this.request("GET", "/agents");
  }

  async searchMemory(query, topK = 5) {
    return this.request("POST", "/memory/search", {
      query,
      top_k: topK,
      include_scores: true
    });
  }

  async storeMemory(content, layer = 2, importance = 0.5) {
    return this.request("POST", "/memory", {
      content,
      layer,
      importance
    });
  }
}

// 使用示例
const client = new XAgentClient("http://localhost:8000", "your-api-key");

// 启动运行
client.startRun("Analyze Q1 sales data")
  .then(result => console.log(JSON.stringify(result, null, 2)))
  .catch(error => console.error(error));

// 列出 Agents
client.listAgents()
  .then(agents => console.log(JSON.stringify(agents, null, 2)))
  .catch(error => console.error(error));
```

## cURL 常用命令

### 获取 API Key
```bash
# 登录获取 token
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "user@example.com",
    "password": "password"
  }'
```

### 保存 API Key 到环境变量
```bash
export XAGENT_API_KEY="your-api-key"
export XAGENT_BASE_URL="http://localhost:8000"
```

### 使用环境变量的请求
```bash
curl -H "X-API-Key: $XAGENT_API_KEY" \
  $XAGENT_BASE_URL/api/v1/agents
```

## 调试技巧

### 启用详细日志
```bash
curl -v -H "X-API-Key: your-api-key" \
  http://localhost:8000/api/v1/agents
```

### 保存响应到文件
```bash
curl -H "X-API-Key: your-api-key" \
  http://localhost:8000/api/v1/agents > response.json
```

### 格式化 JSON 响应
```bash
curl -s -H "X-API-Key: your-api-key" \
  http://localhost:8000/api/v1/agents | jq .
```

## 更多资源

- [完整 API 参考](./API_REFERENCE.md)
- [API 使用指南](./API_GUIDE.md)
- [Postman 集合](./X-Agent.postman_collection.json)
- [OpenAPI Schema](./openapi.json)
- [架构文档](./ARCHITECTURE.md)
