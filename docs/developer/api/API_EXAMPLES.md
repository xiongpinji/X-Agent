# X-Agent API 使用示例

本文档提供了使用 X-Agent API 的详细示例，包括 Python、cURL 和 JavaScript。

## 目录

1. [认证示例](#认证示例)
2. [Agent 管理示例](#agent-管理示例)
3. [Run 执行示例](#run-执行示例)
4. [Memory 操作示例](#memory-操作示例)
5. [Tools 使用示例](#tools-使用示例)
6. [Traces 查询示例](#traces-查询示例)
7. [错误处理示例](#错误处理示例)
8. [高级场景示例](#高级场景示例)

---

## 认证示例

### Python - 获取 Token

```python
import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

# 登录获取 token
response = requests.post(
    f"{BASE_URL}/auth/login",
    json={
        "username": "user@example.com",
        "password": "secure_password"
    }
)

if response.status_code == 200:
    data = response.json()
    token = data["access_token"]
    print(f"Token: {token}")
    print(f"Expires in: {data['expires_in']} seconds")
else:
    print(f"Login failed: {response.text}")
```

### cURL - 获取 Token

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "user@example.com",
    "password": "secure_password"
  }'
```

### JavaScript - 获取 Token

```javascript
const BASE_URL = "http://localhost:8000/api/v1";

async function login() {
  const response = await fetch(`${BASE_URL}/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      username: "user@example.com",
      password: "secure_password"
    })
  });

  if (response.ok) {
    const data = await response.json();
    console.log("Token:", data.access_token);
    return data.access_token;
  } else {
    console.error("Login failed:", response.statusText);
  }
}

const token = await login();
```

---

## Agent 管理示例

### Python - 创建 Agent

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"
TOKEN = "your-jwt-token"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# 创建 Agent
response = requests.post(
    f"{BASE_URL}/agents",
    headers=headers,
    json={
        "name": "Data Analyzer",
        "status": "active",
        "capabilities": ["run", "trace", "memory", "tools"],
        "config": {
            "max_iterations": 100,
            "timeout_seconds": 300,
            "memory_limit_mb": 512
        }
    }
)

if response.status_code == 201:
    agent = response.json()
    print(f"Agent created: {agent['id']}")
    print(f"Name: {agent['name']}")
else:
    print(f"Error: {response.text}")
```

### cURL - 创建 Agent

```bash
TOKEN="your-jwt-token"

curl -X POST http://localhost:8000/api/v1/agents \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Data Analyzer",
    "status": "active",
    "capabilities": ["run", "trace", "memory", "tools"],
    "config": {
      "max_iterations": 100,
      "timeout_seconds": 300,
      "memory_limit_mb": 512
    }
  }'
```

### JavaScript - 创建 Agent

```javascript
const BASE_URL = "http://localhost:8000/api/v1";
const TOKEN = "your-jwt-token";

async function createAgent() {
  const response = await fetch(`${BASE_URL}/agents`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${TOKEN}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      name: "Data Analyzer",
      status: "active",
      capabilities: ["run", "trace", "memory", "tools"],
      config: {
        max_iterations: 100,
        timeout_seconds: 300,
        memory_limit_mb: 512
      }
    })
  });

  if (response.ok) {
    const agent = await response.json();
    console.log("Agent created:", agent.id);
    return agent;
  } else {
    console.error("Error:", response.statusText);
  }
}

const agent = await createAgent();
```

### Python - 列出 Agents

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"
TOKEN = "your-jwt-token"

headers = {"Authorization": f"Bearer {TOKEN}"}

# 列出所有 Agents
response = requests.get(
    f"{BASE_URL}/agents",
    headers=headers,
    params={
        "limit": 10,
        "status": "active"
    }
)

if response.status_code == 200:
    data = response.json()
    print(f"Total agents: {data['total']}")
    for agent in data['data']:
        print(f"- {agent['name']} ({agent['id']})")
else:
    print(f"Error: {response.text}")
```

### Python - 获取 Agent 详情

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"
TOKEN = "your-jwt-token"
AGENT_ID = "agent_a1b2c3d4"

headers = {"Authorization": f"Bearer {TOKEN}"}

response = requests.get(
    f"{BASE_URL}/agents/{AGENT_ID}",
    headers=headers
)

if response.status_code == 200:
    agent = response.json()
    print(f"Agent: {agent['name']}")
    print(f"Status: {agent['status']}")
    print(f"Total runs: {agent['stats']['total_runs']}")
    print(f"Success rate: {agent['stats']['successful_runs'] / agent['stats']['total_runs'] * 100:.1f}%")
else:
    print(f"Error: {response.text}")
```

### Python - 更新 Agent

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"
TOKEN = "your-jwt-token"
AGENT_ID = "agent_a1b2c3d4"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

response = requests.put(
    f"{BASE_URL}/agents/{AGENT_ID}",
    headers=headers,
    json={
        "name": "Updated Agent Name",
        "status": "inactive",
        "config": {
            "max_iterations": 50
        }
    }
)

if response.status_code == 200:
    agent = response.json()
    print(f"Agent updated: {agent['name']}")
else:
    print(f"Error: {response.text}")
```

### Python - 删除 Agent

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"
TOKEN = "your-jwt-token"
AGENT_ID = "agent_a1b2c3d4"

headers = {"Authorization": f"Bearer {TOKEN}"}

response = requests.delete(
    f"{BASE_URL}/agents/{AGENT_ID}",
    headers=headers
)

if response.status_code == 204:
    print("Agent deleted successfully")
else:
    print(f"Error: {response.text}")
```

---

## Run 执行示例

### Python - 启动同步 Run

```python
import requests
import json

BASE_URL = "http://localhost:8000/api/v1"
TOKEN = "your-jwt-token"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# 启动同步 Run
response = requests.post(
    f"{BASE_URL}/runs/start",
    headers=headers,
    json={
        "task": "分析这个数据集并生成报告",
        "extra_context": {
            "dataset_url": "https://example.com/data.csv",
            "format": "json"
        },
        "async_run": False
    }
)

if response.status_code == 200:
    result = response.json()
    print(f"Run completed: {result['status']}")
    print(f"Trace ID: {result['trace_id']}")
    print(f"Result: {json.dumps(result['run']['result'], indent=2)}")
else:
    print(f"Error: {response.text}")
```

### Python - 启动异步 Run

```python
import requests
import time

BASE_URL = "http://localhost:8000/api/v1"
TOKEN = "your-jwt-token"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# 启动异步 Run
response = requests.post(
    f"{BASE_URL}/runs/start",
    headers=headers,
    json={
        "task": "分析这个数据集并生成报告",
        "async_run": True
    }
)

if response.status_code == 200:
    result = response.json()
    trace_id = result["trace_id"]
    print(f"Run started: {trace_id}")
    
    # 轮询检查状态
    while True:
        status_response = requests.get(
            f"{BASE_URL}/runs/{trace_id}",
            headers=headers
        )
        
        if status_response.status_code == 200:
            status = status_response.json()
            print(f"Status: {status['status']}")
            
            if status["status"] in ["completed", "failed"]:
                print(f"Final result: {status.get('result')}")
                break
        
        time.sleep(2)
else:
    print(f"Error: {response.text}")
```

### cURL - 启动 Run

```bash
TOKEN="your-jwt-token"

curl -X POST http://localhost:8000/api/v1/runs/start \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "task": "分析这个数据集并生成报告",
    "extra_context": {
      "dataset_url": "https://example.com/data.csv"
    },
    "async_run": false
  }'
```

### JavaScript - 启动 Run

```javascript
const BASE_URL = "http://localhost:8000/api/v1";
const TOKEN = "your-jwt-token";

async function startRun() {
  const response = await fetch(`${BASE_URL}/runs/start`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${TOKEN}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      task: "分析这个数据集并生成报告",
      extra_context: {
        dataset_url: "https://example.com/data.csv"
      },
      async_run: false
    })
  });

  if (response.ok) {
    const result = await response.json();
    console.log("Run completed:", result.status);
    console.log("Result:", result.run.result);
    return result;
  } else {
    console.error("Error:", response.statusText);
  }
}

const result = await startRun();
```

### Python - 列出 Runs

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"
TOKEN = "your-jwt-token"

headers = {"Authorization": f"Bearer {TOKEN}"}

response = requests.get(
    f"{BASE_URL}/runs",
    headers=headers,
    params={
        "limit": 20,
        "status": "completed"
    }
)

if response.status_code == 200:
    data = response.json()
    print(f"Total runs: {data['total']}")
    for run in data['data']:
        print(f"- {run['task'][:50]}... ({run['status']})")
        print(f"  Duration: {run['duration_ms']}ms")
else:
    print(f"Error: {response.text}")
```

### Python - 获取 Run 详情

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"
TOKEN = "your-jwt-token"
TRACE_ID = "trace_xyz789"

headers = {"Authorization": f"Bearer {TOKEN}"}

response = requests.get(
    f"{BASE_URL}/runs/{TRACE_ID}",
    headers=headers
)

if response.status_code == 200:
    run = response.json()
    print(f"Task: {run['task']}")
    print(f"Status: {run['status']}")
    print(f"Duration: {run['duration_ms']}ms")
    print(f"Result: {run['result']}")
    print(f"\nTimeline:")
    for event in run['timeline']:
        print(f"  {event['timestamp']}: {event['event']}")
else:
    print(f"Error: {response.text}")
```

---

## Memory 操作示例

### Python - 搜索记忆

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"
TOKEN = "your-jwt-token"

headers = {"Authorization": f"Bearer {TOKEN}"}

response = requests.get(
    f"{BASE_URL}/memory/search",
    headers=headers,
    params={
        "query": "数据分析结果",
        "limit": 10,
        "threshold": 0.8
    }
)

if response.status_code == 200:
    data = response.json()
    print(f"Found {data['total']} memories:")
    for memory in data['results']:
        print(f"- {memory['content'][:50]}...")
        print(f"  Similarity: {memory['similarity']:.2f}")
        print(f"  Tags: {', '.join(memory['tags'])}")
else:
    print(f"Error: {response.text}")
```

### Python - 添加记忆

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"
TOKEN = "your-jwt-token"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

response = requests.post(
    f"{BASE_URL}/memory",
    headers=headers,
    json={
        "content": "重要的分析结果：数据显示增长趋势",
        "tags": ["analysis", "important", "growth"],
        "metadata": {
            "source": "run_123",
            "confidence": 0.95,
            "date": "2026-05-27"
        }
    }
)

if response.status_code == 201:
    memory = response.json()
    print(f"Memory added: {memory['id']}")
else:
    print(f"Error: {response.text}")
```

---

## Tools 使用示例

### Python - 列出工具

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"
TOKEN = "your-jwt-token"

headers = {"Authorization": f"Bearer {TOKEN}"}

response = requests.get(
    f"{BASE_URL}/tools",
    headers=headers
)

if response.status_code == 200:
    data = response.json()
    print(f"Available tools: {data['total']}")
    for tool in data['data']:
        print(f"- {tool['name']} ({tool['id']})")
        print(f"  Category: {tool['category']}")
        print(f"  Description: {tool['description']}")
        print(f"  Usage count: {tool.get('usage_count', 0)}")
else:
    print(f"Error: {response.text}")
```

### Python - 获取工具详情

```python
import requests
import json

BASE_URL = "http://localhost:8000/api/v1"
TOKEN = "your-jwt-token"
TOOL_ID = "tool_web_search"

headers = {"Authorization": f"Bearer {TOKEN}"}

response = requests.get(
    f"{BASE_URL}/tools/{TOOL_ID}",
    headers=headers
)

if response.status_code == 200:
    tool = response.json()
    print(f"Tool: {tool['name']}")
    print(f"Description: {tool['description']}")
    print(f"Parameters:")
    print(json.dumps(tool['parameters'], indent=2))
else:
    print(f"Error: {response.text}")
```

---

## Traces 查询示例

### Python - 获取 Trace

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"
TOKEN = "your-jwt-token"
TRACE_ID = "trace_xyz789"

headers = {"Authorization": f"Bearer {TOKEN}"}

response = requests.get(
    f"{BASE_URL}/traces/{TRACE_ID}",
    headers=headers
)

if response.status_code == 200:
    trace = response.json()
    print(f"Trace: {trace['id']}")
    print(f"Status: {trace['status']}")
    print(f"Duration: {(trace['completed_at'] - trace['started_at']).total_seconds()}s")
    print(f"\nEvents:")
    for event in trace['events']:
        print(f"  {event['timestamp']}: {event['type']}")
        if 'details' in event:
            print(f"    Details: {event['details']}")
else:
    print(f"Error: {response.text}")
```

---

## 错误处理示例

### Python - 完整的错误处理

```python
import requests
from requests.exceptions import RequestException, Timeout, ConnectionError

BASE_URL = "http://localhost:8000/api/v1"
TOKEN = "your-jwt-token"

def make_api_call(method, endpoint, **kwargs):
    """
    发起 API 调用，包含完整的错误处理
    """
    url = f"{BASE_URL}{endpoint}"
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {TOKEN}"
    
    try:
        response = requests.request(
            method,
            url,
            headers=headers,
            timeout=30,
            **kwargs
        )
        
        # 检查 HTTP 状态码
        if response.status_code >= 400:
            error_data = response.json()
            error = error_data.get("error", {})
            print(f"API Error: {error.get('code')}")
            print(f"Message: {error.get('message')}")
            print(f"Details: {error.get('details')}")
            return None
        
        return response.json()
    
    except Timeout:
        print("Request timeout - server took too long to respond")
        return None
    
    except ConnectionError:
        print("Connection error - unable to reach server")
        return None
    
    except RequestException as e:
        print(f"Request error: {e}")
        return None
    
    except ValueError:
        print("Invalid JSON response")
        return None

# 使用示例
result = make_api_call(
    "POST",
    "/runs/start",
    json={
        "task": "分析数据",
        "async_run": False
    }
)

if result:
    print(f"Success: {result}")
```

---

## 高级场景示例

### Python - 批量创建 Agents

```python
import requests
import concurrent.futures

BASE_URL = "http://localhost:8000/api/v1"
TOKEN = "your-jwt-token"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

def create_agent(name):
    """创建单个 Agent"""
    response = requests.post(
        f"{BASE_URL}/agents",
        headers=headers,
        json={
            "name": name,
            "status": "active",
            "capabilities": ["run", "trace", "memory", "tools"]
        }
    )
    return response.json() if response.status_code == 201 else None

# 并发创建多个 Agents
agent_names = [
    "Data Analyzer",
    "Report Generator",
    "Quality Checker",
    "Performance Monitor"
]

with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    futures = [executor.submit(create_agent, name) for name in agent_names]
    results = [f.result() for f in concurrent.futures.as_completed(futures)]

print(f"Created {len([r for r in results if r])} agents")
```

### Python - 监控 Run 执行

```python
import requests
import time
from datetime import datetime

BASE_URL = "http://localhost:8000/api/v1"
TOKEN = "your-jwt-token"

headers = {"Authorization": f"Bearer {TOKEN}"}

def monitor_run(trace_id, check_interval=2, max_duration=300):
    """
    监控 Run 执行，定期检查状态
    """
    start_time = time.time()
    
    while True:
        elapsed = time.time() - start_time
        
        # 检查是否超时
        if elapsed > max_duration:
            print(f"Run monitoring timeout after {max_duration}s")
            break
        
        # 获取 Run 状态
        response = requests.get(
            f"{BASE_URL}/runs/{trace_id}",
            headers=headers
        )
        
        if response.status_code == 200:
            run = response.json()
            status = run["status"]
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Status: {status}")
            
            if status in ["completed", "failed"]:
                print(f"Run finished with status: {status}")
                print(f"Total duration: {elapsed:.1f}s")
                return run
        
        time.sleep(check_interval)
    
    return None

# 启动 Run 并监控
start_response = requests.post(
    f"{BASE_URL}/runs/start",
    headers=headers,
    json={"task": "分析数据", "async_run": True}
)

if start_response.status_code == 200:
    trace_id = start_response.json()["trace_id"]
    result = monitor_run(trace_id)
```

### Python - 重试机制

```python
import requests
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def create_session_with_retries(retries=3, backoff_factor=0.5):
    """
    创建带有重试机制的 requests Session
    """
    session = requests.Session()
    
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST", "PUT", "DELETE"]
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session

# 使用带重试的 Session
session = create_session_with_retries()
TOKEN = "your-jwt-token"

response = session.get(
    "http://localhost:8000/api/v1/agents",
    headers={"Authorization": f"Bearer {TOKEN}"}
)

print(f"Response status: {response.status_code}")
```

---

## 最佳实践总结

1. **始终处理错误**: 检查 HTTP 状态码和错误响应
2. **使用异步执行**: 对于长时间运行的任务使用 `async_run: true`
3. **实施重试机制**: 处理临时网络故障
4. **监控速率限制**: 遵守 API 速率限制
5. **记录请求 ID**: 用于调试和追踪
6. **使用连接池**: 提高性能
7. **设置合理的超时**: 避免无限等待
8. **验证输入**: 在发送前验证数据
