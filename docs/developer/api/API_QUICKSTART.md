# X-Agent API 快速开始指南

本指南将帮助你快速开始使用 X-Agent API。

## 前置要求

- X-Agent 服务已启动（默认运行在 `http://localhost:8000`）
- 已获得有效的 API 凭证（用户名和密码）
- 安装了 `curl`、Python 3.8+ 或 Node.js 14+

## 5 分钟快速开始

### 第 1 步：获取 API Token

使用你的凭证登录获取 JWT token。

**Python**:
```python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/auth/login",
    json={
        "username": "user@example.com",
        "password": "your_password"
    }
)

token = response.json()["access_token"]
print(f"Token: {token}")
```

**cURL**:
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "user@example.com",
    "password": "your_password"
  }' | jq '.access_token'
```

**JavaScript**:
```javascript
const response = await fetch("http://localhost:8000/api/v1/auth/login", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    username: "user@example.com",
    password: "your_password"
  })
});

const { access_token } = await response.json();
console.log("Token:", access_token);
```

### 第 2 步：执行你的第一个任务

现在使用 token 执行一个任务。

**Python**:
```python
import requests

TOKEN = "your_token_here"

response = requests.post(
    "http://localhost:8000/api/v1/runs/start",
    headers={"Authorization": f"Bearer {TOKEN}"},
    json={
        "task": "告诉我今天的天气如何",
        "async_run": False
    }
)

result = response.json()
print(f"Status: {result['status']}")
print(f"Result: {result['run']['result']}")
```

**cURL**:
```bash
TOKEN="your_token_here"

curl -X POST http://localhost:8000/api/v1/runs/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "告诉我今天的天气如何",
    "async_run": false
  }' | jq '.run.result'
```

**JavaScript**:
```javascript
const TOKEN = "your_token_here";

const response = await fetch("http://localhost:8000/api/v1/runs/start", {
  method: "POST",
  headers: {
    "Authorization": `Bearer ${TOKEN}`,
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    task: "告诉我今天的天气如何",
    async_run: false
  })
});

const result = await response.json();
console.log("Status:", result.status);
console.log("Result:", result.run.result);
```

### 第 3 步：查看执行历史

列出你执行过的所有任务。

**Python**:
```python
import requests

TOKEN = "your_token_here"

response = requests.get(
    "http://localhost:8000/api/v1/runs",
    headers={"Authorization": f"Bearer {TOKEN}"},
    params={"limit": 10}
)

runs = response.json()["data"]
for run in runs:
    print(f"- {run['task'][:50]}... ({run['status']})")
```

---

## 常见任务

### 创建一个 Agent

```python
import requests

TOKEN = "your_token_here"

response = requests.post(
    "http://localhost:8000/api/v1/agents",
    headers={
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    },
    json={
        "name": "My Custom Agent",
        "status": "active",
        "capabilities": ["run", "trace", "memory", "tools"]
    }
)

agent = response.json()
print(f"Agent created: {agent['id']}")
```

### 执行异步任务

对于长时间运行的任务，使用异步执行。

```python
import requests
import time

TOKEN = "your_token_here"

# 启动异步任务
response = requests.post(
    "http://localhost:8000/api/v1/runs/start",
    headers={"Authorization": f"Bearer {TOKEN}"},
    json={
        "task": "分析大型数据集",
        "async_run": True
    }
)

trace_id = response.json()["trace_id"]
print(f"Task started: {trace_id}")

# 轮询检查状态
while True:
    status_response = requests.get(
        f"http://localhost:8000/api/v1/runs/{trace_id}",
        headers={"Authorization": f"Bearer {TOKEN}"}
    )
    
    status = status_response.json()["status"]
    print(f"Status: {status}")
    
    if status in ["completed", "failed"]:
        break
    
    time.sleep(2)
```

### 搜索记忆

```python
import requests

TOKEN = "your_token_here"

response = requests.get(
    "http://localhost:8000/api/v1/memory/search",
    headers={"Authorization": f"Bearer {TOKEN}"},
    params={
        "query": "之前的分析结果",
        "limit": 5
    }
)

memories = response.json()["results"]
for memory in memories:
    print(f"- {memory['content'][:50]}...")
    print(f"  Similarity: {memory['similarity']:.2f}")
```

### 查看可用工具

```python
import requests

TOKEN = "your_token_here"

response = requests.get(
    "http://localhost:8000/api/v1/tools",
    headers={"Authorization": f"Bearer {TOKEN}"}
)

tools = response.json()["data"]
for tool in tools:
    print(f"- {tool['name']}: {tool['description']}")
```

---

## 环境配置

### 使用环境变量

为了安全起见，建议使用环境变量存储敏感信息。

**Python**:
```python
import os
import requests

# 从环境变量读取
BASE_URL = os.getenv("XAGENT_BASE_URL", "http://localhost:8000")
TOKEN = os.getenv("XAGENT_TOKEN")
USERNAME = os.getenv("XAGENT_USERNAME")
PASSWORD = os.getenv("XAGENT_PASSWORD")

# 如果没有 token，则登录获取
if not TOKEN:
    response = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={"username": USERNAME, "password": PASSWORD}
    )
    TOKEN = response.json()["access_token"]

print(f"Using token: {TOKEN[:20]}...")
```

**Bash**:
```bash
export XAGENT_BASE_URL="http://localhost:8000"
export XAGENT_USERNAME="user@example.com"
export XAGENT_PASSWORD="your_password"

# 获取 token
TOKEN=$(curl -s -X POST $XAGENT_BASE_URL/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"username\": \"$XAGENT_USERNAME\", \"password\": \"$XAGENT_PASSWORD\"}" \
  | jq -r '.access_token')

echo "Token: $TOKEN"
```

### 创建配置文件

创建 `xagent_config.py`:

```python
import os
from dataclasses import dataclass

@dataclass
class XAgentConfig:
    base_url: str = os.getenv("XAGENT_BASE_URL", "http://localhost:8000")
    username: str = os.getenv("XAGENT_USERNAME", "user@example.com")
    password: str = os.getenv("XAGENT_PASSWORD", "")
    token: str = os.getenv("XAGENT_TOKEN", "")
    
    @property
    def api_url(self) -> str:
        return f"{self.base_url}/api/v1"

config = XAgentConfig()
```

然后在你的代码中使用：

```python
from xagent_config import config
import requests

response = requests.get(
    f"{config.api_url}/agents",
    headers={"Authorization": f"Bearer {config.token}"}
)
```

---

## 错误处理

### 处理常见错误

```python
import requests
from requests.exceptions import RequestException

TOKEN = "your_token_here"

try:
    response = requests.post(
        "http://localhost:8000/api/v1/runs/start",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json={"task": ""},  # 空任务会导致错误
        timeout=30
    )
    
    # 检查 HTTP 状态码
    if response.status_code == 400:
        error = response.json()["error"]
        print(f"Validation error: {error['message']}")
        print(f"Details: {error['details']}")
    
    elif response.status_code == 401:
        print("Unauthorized - check your token")
    
    elif response.status_code == 429:
        print("Rate limited - wait before retrying")
    
    elif response.status_code >= 500:
        print("Server error - try again later")
    
    else:
        result = response.json()
        print(f"Success: {result}")

except requests.exceptions.Timeout:
    print("Request timeout")

except requests.exceptions.ConnectionError:
    print("Connection error - is the server running?")

except RequestException as e:
    print(f"Request error: {e}")
```

---

## 调试技巧

### 启用详细日志

**Python**:
```python
import logging
import requests

# 启用 HTTP 调试
logging.basicConfig(level=logging.DEBUG)
requests_log = logging.getLogger("requests.packages.urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True

# 现在所有请求都会被记录
response = requests.get("http://localhost:8000/api/v1/agents")
```

### 检查请求和响应

```python
import requests
import json

TOKEN = "your_token_here"

response = requests.post(
    "http://localhost:8000/api/v1/runs/start",
    headers={"Authorization": f"Bearer {TOKEN}"},
    json={"task": "test"}
)

print("Request URL:", response.request.url)
print("Request Headers:", dict(response.request.headers))
print("Request Body:", response.request.body)
print("\nResponse Status:", response.status_code)
print("Response Headers:", dict(response.headers))
print("Response Body:", json.dumps(response.json(), indent=2))
```

### 使用 cURL 进行测试

```bash
# 启用详细输出
curl -v -X POST http://localhost:8000/api/v1/runs/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"task": "test"}'

# 只显示响应头
curl -i -X POST http://localhost:8000/api/v1/runs/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"task": "test"}'

# 格式化 JSON 输出
curl -s -X POST http://localhost:8000/api/v1/runs/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"task": "test"}' | jq '.'
```

---

## 下一步

- 阅读 [完整 API 参考](./API_COMPLETE_REFERENCE.md)
- 查看 [详细示例](./API_EXAMPLES.md)
- 了解 [SDK 使用](../sdk/SDK_GUIDE.md)
- 探索 [高级功能](../../concepts/features/ADVANCED_FEATURES.md)

---

## 获取帮助

- 查看 [常见问题](../../operations/support/FAQ.md)
- 阅读 [故障排除指南](../../operations/support/TROUBLESHOOTING.md)
- 查看 [API 变更日志](./API_CHANGELOG.md)
