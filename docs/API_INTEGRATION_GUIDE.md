# X-Agent API 集成指南

## 目录
1. [环境设置](#环境设置)
2. [API 集成步骤](#api-集成步骤)
3. [常见集成场景](#常见集成场景)
4. [错误处理和重试](#错误处理和重试)
5. [性能优化](#性能优化)
6. [安全最佳实践](#安全最佳实践)
7. [测试和验证](#测试和验证)

## 环境设置

### 1. 获取 API Key

```bash
# 登录获取 JWT Token
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin@example.com",
    "password": "admin_password"
  }'

# 响应包含 access_token
# {
#   "access_token": "eyJhbGciOiJIUzI1NiIs...",
#   "token_type": "bearer",
#   "expires_in": 3600
# }
```

### 2. 配置环境变量

```bash
# .env 文件
XAGENT_BASE_URL=http://localhost:8000
XAGENT_API_KEY=your-api-key-here
XAGENT_TIMEOUT=30
XAGENT_RETRY_ATTEMPTS=3
```

### 3. 验证连接

```bash
curl -H "X-API-Key: $XAGENT_API_KEY" \
  $XAGENT_BASE_URL/api/v1/agents
```

## API 集成步骤

### 步骤 1: 初始化客户端

```python
import os
import requests
from typing import Dict, Any, Optional

class XAgentAPI:
    def __init__(self):
        self.base_url = os.getenv("XAGENT_BASE_URL", "http://localhost:8000")
        self.api_key = os.getenv("XAGENT_API_KEY")
        self.timeout = int(os.getenv("XAGENT_TIMEOUT", "30"))
        
        if not self.api_key:
            raise ValueError("XAGENT_API_KEY environment variable not set")
        
        self.session = requests.Session()
        self.session.headers.update({
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        })
    
    def _request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """发送 API 请求"""
        url = f"{self.base_url}/api/v1{endpoint}"
        
        try:
            if method == "GET":
                response = self.session.get(url, timeout=self.timeout)
            elif method == "POST":
                response = self.session.post(url, json=data, timeout=self.timeout)
            elif method == "PUT":
                response = self.session.put(url, json=data, timeout=self.timeout)
            elif method == "DELETE":
                response = self.session.delete(url, timeout=self.timeout)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            print(f"API request failed: {e}")
            raise

# 使用
api = XAgentAPI()
```

### 步骤 2: 创建 Agent

```python
def create_agent(api: XAgentAPI, name: str, capabilities: list) -> Dict[str, Any]:
    """创建新 Agent"""
    data = {
        "name": name,
        "status": "active",
        "capabilities": capabilities
    }
    return api._request("POST", "/agents", data)

# 使用
agent = create_agent(api, "DataAnalyzer", ["run", "trace", "memory", "tools"])
print(f"Created agent: {agent['id']}")
```

### 步骤 3: 启动运行

```python
def start_run(api: XAgentAPI, task: str, context: Optional[Dict] = None) -> Dict[str, Any]:
    """启动 Agent 运行"""
    data = {
        "task": task,
        "extra_context": context or {},
        "async_run": False
    }
    return api._request("POST", "/runs/start", data)

# 使用
result = start_run(api, "Analyze Q1 sales data", {"period": "Q1 2025"})
print(f"Run completed: {result['status']}")
print(f"Result: {result['result']}")
```

### 步骤 4: 管理记忆

```python
def store_memory(api: XAgentAPI, content: str, importance: float = 0.5) -> str:
    """存储记忆"""
    data = {
        "content": content,
        "layer": 2,
        "importance": importance,
        "tags": ["integration_test"]
    }
    response = api._request("POST", "/memory", data)
    return response["id"]

def search_memory(api: XAgentAPI, query: str, top_k: int = 5) -> list:
    """搜索记忆"""
    data = {
        "query": query,
        "top_k": top_k,
        "include_scores": True
    }
    response = api._request("POST", "/memory/search", data)
    return response["items"]

# 使用
memory_id = store_memory(api, "User prefers JSON format")
memories = search_memory(api, "user preferences")
print(f"Found {len(memories)} memories")
```

## 常见集成场景

### 场景 1: 数据分析工作流

```python
def data_analysis_workflow(api: XAgentAPI, data_source: str):
    """数据分析工作流"""
    
    # 1. 创建 Workflow
    workflow_data = {
        "name": "Data Analysis Pipeline",
        "description": "Analyze data from various sources",
        "nodes": [
            {"id": "n1", "type": "start", "label": "Start"},
            {"id": "n2", "type": "task", "label": "Extract Data"},
            {"id": "n3", "type": "task", "label": "Transform Data"},
            {"id": "n4", "type": "task", "label": "Analyze Data"},
            {"id": "n5", "type": "end", "label": "End"}
        ],
        "edges": [
            {"source": "n1", "target": "n2"},
            {"source": "n2", "target": "n3"},
            {"source": "n3", "target": "n4"},
            {"source": "n4", "target": "n5"}
        ]
    }
    workflow = api._request("POST", "/workflows", workflow_data)
    
    # 2. 启动运行
    run_result = start_run(api, f"Analyze data from {data_source}", {
        "source": data_source,
        "format": "json"
    })
    
    # 3. 存储结果到记忆
    store_memory(api, f"Analysis of {data_source}: {run_result['result']}", 0.8)
    
    return run_result

# 使用
result = data_analysis_workflow(api, "sales_database")
```

### 场景 2: 多步骤任务执行

```python
def multi_step_task(api: XAgentAPI, steps: list):
    """执行多步骤任务"""
    results = []
    
    for i, step in enumerate(steps):
        print(f"Executing step {i+1}/{len(steps)}: {step['name']}")
        
        result = start_run(api, step["task"], step.get("context", {}))
        results.append({
            "step": step["name"],
            "status": result["status"],
            "result": result.get("result")
        })
        
        # 存储中间结果
        store_memory(api, f"Step {i+1} result: {result.get('result')}", 0.6)
    
    return results

# 使用
steps = [
    {"name": "Extract", "task": "Extract data from source"},
    {"name": "Transform", "task": "Transform data format"},
    {"name": "Load", "task": "Load data to destination"}
]
results = multi_step_task(api, steps)
```

### 场景 3: 实时监控和追踪

```python
def monitor_execution(api: XAgentAPI, run_id: str):
    """监控执行过程"""
    
    # 获取运行状态
    runs = api._request("GET", "/runs")
    run = next((r for r in runs if r["run_id"] == run_id), None)
    
    if not run:
        print(f"Run {run_id} not found")
        return
    
    print(f"Run Status: {run['status']}")
    print(f"Started: {run['started_at']}")
    
    # 获取追踪信息
    traces = api._request("GET", f"/traces?run_id={run_id}")
    print(f"Trace events: {len(traces)}")
    
    # 获取审计日志
    audit_logs = api._request("GET", "/audit?limit=10")
    print(f"Recent audit logs: {len(audit_logs)}")

# 使用
monitor_execution(api, "run_abc123")
```

## 错误处理和重试

### 实现重试机制

```python
import time
from functools import wraps

def retry_on_failure(max_attempts: int = 3, backoff_factor: float = 2.0):
    """重试装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            attempt = 0
            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.RequestException as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        raise
                    
                    wait_time = backoff_factor ** (attempt - 1)
                    print(f"Attempt {attempt} failed. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
        
        return wrapper
    return decorator

@retry_on_failure(max_attempts=3)
def resilient_api_call(api: XAgentAPI, endpoint: str):
    """具有重试机制的 API 调用"""
    return api._request("GET", endpoint)

# 使用
try:
    result = resilient_api_call(api, "/agents")
except Exception as e:
    print(f"Failed after retries: {e}")
```

### 错误处理最佳实践

```python
def safe_api_call(api: XAgentAPI, method: str, endpoint: str, data: Optional[Dict] = None):
    """安全的 API 调用"""
    try:
        return api._request(method, endpoint, data)
    
    except requests.exceptions.Timeout:
        print("Request timeout - server may be overloaded")
        raise
    
    except requests.exceptions.ConnectionError:
        print("Connection error - check network and server status")
        raise
    
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            print("Rate limited - wait before retrying")
        elif e.response.status_code == 401:
            print("Unauthorized - check API key")
        elif e.response.status_code == 403:
            print("Forbidden - insufficient permissions")
        elif e.response.status_code == 404:
            print("Resource not found")
        else:
            print(f"HTTP error: {e.response.status_code}")
        raise
    
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise
```

## 性能优化

### 1. 连接池

```python
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def create_session_with_retries():
    """创建带重试的会话"""
    session = requests.Session()
    
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session
```

### 2. 批量操作

```python
def batch_store_memories(api: XAgentAPI, memories: list):
    """批量存储记忆"""
    results = []
    for memory in memories:
        try:
            result = store_memory(api, memory["content"], memory.get("importance", 0.5))
            results.append({"status": "success", "id": result})
        except Exception as e:
            results.append({"status": "failed", "error": str(e)})
    
    return results
```

### 3. 缓存

```python
from functools import lru_cache
import time

class CachedXAgentAPI(XAgentAPI):
    def __init__(self, cache_ttl: int = 300):
        super().__init__()
        self.cache_ttl = cache_ttl
        self._cache = {}
    
    def get_agents_cached(self):
        """获取 Agents（带缓存）"""
        cache_key = "agents"
        
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return cached_data
        
        data = self._request("GET", "/agents")
        self._cache[cache_key] = (time.time(), data)
        return data
```

## 安全最佳实践

### 1. API Key 管理

```python
import os
from dotenv import load_dotenv

# 从 .env 文件加载
load_dotenv()

api_key = os.getenv("XAGENT_API_KEY")
if not api_key:
    raise ValueError("API key not configured")

# 不要在代码中硬编码 API Key
# ❌ api_key = "sk_live_abc123"  # 错误
# ✅ api_key = os.getenv("XAGENT_API_KEY")  # 正确
```

### 2. 请求签名

```python
import hmac
import hashlib
import json
from datetime import datetime

def sign_request(data: Dict, secret: str) -> str:
    """签名请求"""
    timestamp = datetime.utcnow().isoformat()
    message = f"{timestamp}:{json.dumps(data)}"
    signature = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    return signature
```

### 3. 数据加密

```python
from cryptography.fernet import Fernet

def encrypt_sensitive_data(data: str, key: str) -> str:
    """加密敏感数据"""
    cipher = Fernet(key.encode())
    return cipher.encrypt(data.encode()).decode()

def decrypt_sensitive_data(encrypted_data: str, key: str) -> str:
    """解密敏感数据"""
    cipher = Fernet(key.encode())
    return cipher.decrypt(encrypted_data.encode()).decode()
```

## 测试和验证

### 单元测试

```python
import unittest
from unittest.mock import Mock, patch

class TestXAgentAPI(unittest.TestCase):
    def setUp(self):
        self.api = XAgentAPI()
    
    @patch('requests.Session.get')
    def test_list_agents(self, mock_get):
        """测试列出 Agents"""
        mock_get.return_value.json.return_value = {
            "data": [{"id": "agent_1", "name": "Test Agent"}]
        }
        
        result = self.api._request("GET", "/agents")
        self.assertEqual(len(result["data"]), 1)
    
    @patch('requests.Session.post')
    def test_start_run(self, mock_post):
        """测试启动运行"""
        mock_post.return_value.json.return_value = {
            "run_id": "run_1",
            "status": "completed"
        }
        
        result = self.api._request("POST", "/runs/start", {"task": "test"})
        self.assertEqual(result["status"], "completed")

if __name__ == '__main__':
    unittest.main()
```

### 集成测试

```python
def test_full_workflow():
    """完整工作流测试"""
    api = XAgentAPI()
    
    # 1. 创建 Agent
    agent = create_agent(api, "TestAgent", ["run", "memory"])
    assert agent["id"]
    
    # 2. 启动运行
    result = start_run(api, "Test task")
    assert result["status"] in ["completed", "running"]
    
    # 3. 存储记忆
    memory_id = store_memory(api, "Test memory")
    assert memory_id
    
    # 4. 搜索记忆
    memories = search_memory(api, "test")
    assert len(memories) > 0
    
    print("All tests passed!")

if __name__ == "__main__":
    test_full_workflow()
```

## 更多资源

- [API 参考文档](./API_REFERENCE.md)
- [API 使用指南](./API_GUIDE.md)
- [快速参考](./API_QUICK_REFERENCE.md)
- [Postman 集合](./X-Agent.postman_collection.json)
