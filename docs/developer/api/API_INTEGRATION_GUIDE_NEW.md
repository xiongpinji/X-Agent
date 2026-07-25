# X-Agent API 集成指南

本指南介绍如何将 X-Agent API 集成到你的应用中。

## 目录

1. [集成架构](#集成架构)
2. [常见集成场景](#常见集成场景)
3. [第三方集成](#第三方集成)
4. [最佳实践](#最佳实践)
5. [故障排除](#故障排除)

---

## 集成架构

### 典型的集成架构

```
┌─────────────────┐
│  Your App       │
├─────────────────┤
│  API Client     │
│  (SDK/HTTP)     │
└────────┬────────┘
         │
         │ HTTP/REST
         │
┌────────▼────────┐
│  X-Agent API    │
├─────────────────┤
│  Auth Layer     │
│  Rate Limiter   │
│  Router         │
└────────┬────────┘
         │
┌────────▼────────┐
│  Core Services  │
├─────────────────┤
│  Agents         │
│  Runs           │
│  Memory         │
│  Tools          │
└─────────────────┘
```

### 集成点

1. **认证**: 获取和管理 API Token
2. **请求**: 发送 API 请求
3. **响应处理**: 处理响应和错误
4. **事件处理**: 监听和处理事件
5. **数据同步**: 同步数据和状态

---

## 常见集成场景

### 场景 1: Web 应用集成

#### 后端集成 (Python/FastAPI)

```python
from fastapi import FastAPI, HTTPException
from xagent import XAgentClient
import os

app = FastAPI()

# 初始化 X-Agent 客户端
xagent_client = XAgentClient(
    base_url=os.getenv("XAGENT_BASE_URL"),
    token=os.getenv("XAGENT_TOKEN")
)

@app.post("/api/analyze")
async def analyze_data(data: dict):
    """
    分析数据的 API 端点
    """
    try:
        # 调用 X-Agent
        result = xagent_client.runs.start(
            task=f"分析以下数据: {data}",
            async_run=False
        )
        
        return {
            "status": result.status,
            "result": result.run.result,
            "trace_id": result.trace_id
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/status/{trace_id}")
async def get_status(trace_id: str):
    """
    获取任务状态
    """
    try:
        run = xagent_client.runs.get(trace_id)
        return {
            "status": run.status,
            "result": run.result if run.status == "completed" else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

#### 前端集成 (React)

```javascript
import React, { useState } from 'react';

function AnalysisComponent() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [traceId, setTraceId] = useState(null);

  const handleAnalyze = async (data) => {
    setLoading(true);
    try {
      // 调用后端 API
      const response = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });

      const data = await response.json();
      setTraceId(data.trace_id);
      setResult(data.result);
    } catch (error) {
      console.error('Analysis failed:', error);
    } finally {
      setLoading(false);
    }
  };

  const checkStatus = async () => {
    if (!traceId) return;

    try {
      const response = await fetch(`/api/status/${traceId}`);
      const data = await response.json();
      setResult(data.result);
    } catch (error) {
      console.error('Status check failed:', error);
    }
  };

  return (
    <div>
      <button onClick={() => handleAnalyze({ /* data */ })}>
        {loading ? 'Analyzing...' : 'Analyze'}
      </button>
      {traceId && (
        <button onClick={checkStatus}>Check Status</button>
      )}
      {result && <pre>{JSON.stringify(result, null, 2)}</pre>}
    </div>
  );
}

export default AnalysisComponent;
```

### 场景 2: 批处理集成

```python
import asyncio
from xagent import XAgentClient

async def batch_process(items):
    """
    批量处理项目
    """
    client = XAgentClient(token="your-token")
    
    # 启动所有任务
    runs = []
    for item in items:
        run = client.runs.start_async(
            task=f"处理: {item}"
        )
        runs.append(run)
    
    # 等待所有任务完成
    results = []
    for run in runs:
        result = run.wait_for_completion(timeout=300)
        results.append(result)
    
    return results

# 使用
items = ["item1", "item2", "item3"]
results = asyncio.run(batch_process(items))
```

### 场景 3: 实时监控集成

```python
import time
from xagent import XAgentClient

def monitor_run_with_callback(trace_id, callback, interval=2):
    """
    监控 Run 并定期调用回调函数
    """
    client = XAgentClient(token="your-token")
    
    while True:
        run = client.runs.get(trace_id)
        
        # 调用回调函数
        callback({
            "trace_id": trace_id,
            "status": run.status,
            "result": run.result
        })
        
        if run.status in ["completed", "failed"]:
            break
        
        time.sleep(interval)

# 使用
def on_update(data):
    print(f"Status: {data['status']}")
    if data['result']:
        print(f"Result: {data['result']}")

monitor_run_with_callback(
    "trace_xyz789",
    on_update
)
```

### 场景 4: 工作流集成

```python
from xagent import XAgentClient

def execute_workflow(steps):
    """
    执行多步工作流
    """
    client = XAgentClient(token="your-token")
    
    context = {}
    
    for step in steps:
        # 使用前一步的结果作为上下文
        task = step["task"].format(**context)
        
        result = client.runs.start(
            task=task,
            extra_context=context
        )
        
        # 保存结果供下一步使用
        context[step["output_key"]] = result.run.result
    
    return context

# 使用
workflow = [
    {
        "task": "获取数据",
        "output_key": "data"
    },
    {
        "task": "分析数据: {data}",
        "output_key": "analysis"
    },
    {
        "task": "生成报告: {analysis}",
        "output_key": "report"
    }
]

result = execute_workflow(workflow)
print(result["report"])
```

---

## 第三方集成

### Slack 集成

```python
from slack_sdk import WebClient
from xagent import XAgentClient

slack_client = WebClient(token="xoxb-your-token")
xagent_client = XAgentClient(token="your-token")

def analyze_and_post_to_slack(channel, task):
    """
    执行分析并将结果发送到 Slack
    """
    # 执行分析
    result = xagent_client.runs.start(task=task)
    
    # 发送到 Slack
    slack_client.chat_postMessage(
        channel=channel,
        text=f"分析完成: {result.run.result}"
    )

# 使用
analyze_and_post_to_slack("#analysis", "分析销售数据")
```

### 数据库集成

```python
from sqlalchemy import create_engine, Column, String, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from xagent import XAgentClient

Base = declarative_base()

class AnalysisRecord(Base):
    __tablename__ = "analyses"
    
    id = Column(String, primary_key=True)
    task = Column(String)
    result = Column(JSON)
    status = Column(String)

# 初始化数据库
engine = create_engine("postgresql://user:password@localhost/xagent")
Session = sessionmaker(bind=engine)

def save_analysis(task):
    """
    执行分析并保存到数据库
    """
    client = XAgentClient(token="your-token")
    session = Session()
    
    # 执行分析
    result = client.runs.start(task=task)
    
    # 保存到数据库
    record = AnalysisRecord(
        id=result.trace_id,
        task=task,
        result=result.run.result,
        status=result.status
    )
    session.add(record)
    session.commit()
    
    return record
```

---

## 最佳实践

### 1. 错误处理和重试

```python
from xagent.retry import retry_with_backoff
from xagent.exceptions import XAgentError

@retry_with_backoff(max_retries=3, backoff_factor=0.5)
def execute_with_retry(task):
    client = XAgentClient(token="your-token")
    return client.runs.start(task=task)

try:
    result = execute_with_retry("分析数据")
except XAgentError as e:
    print(f"Failed after retries: {e}")
```

### 2. 超时管理

```python
def execute_with_timeout(task, timeout=300):
    """
    执行任务并设置超时
    """
    client = XAgentClient(token="your-token")
    
    run = client.runs.start_async(task=task)
    
    try:
        result = run.wait_for_completion(timeout=timeout)
        return result
    except TimeoutError:
        print(f"Task {run.trace_id} timed out after {timeout}s")
        return None
```

### 3. 资源管理

```python
from contextlib import contextmanager

@contextmanager
def xagent_session():
    """
    上下文管理器用于 X-Agent 会话
    """
    client = XAgentClient(token="your-token")
    try:
        yield client
    finally:
        client.close()

# 使用
with xagent_session() as client:
    result = client.runs.start(task="分析数据")
```

### 4. 日志和监控

```python
import logging
from xagent import XAgentClient

logger = logging.getLogger(__name__)

def execute_with_logging(task):
    """
    执行任务并记录日志
    """
    client = XAgentClient(token="your-token", debug=True)
    
    logger.info(f"Starting task: {task}")
    
    try:
        result = client.runs.start(task=task)
        logger.info(f"Task completed: {result.trace_id}")
        return result
    except Exception as e:
        logger.error(f"Task failed: {e}")
        raise
```

---

## 故障排除

### 常见问题

#### 问题 1: 认证失败

```python
# 检查 token 是否有效
try:
    client = XAgentClient(token="your-token")
    agents = client.agents.list()
except AuthenticationError:
    print("Token is invalid or expired")
    # 重新登录获取新 token
```

#### 问题 2: 速率限制

```python
# 实施退避策略
import time
from xagent.exceptions import RateLimitError

def execute_with_rate_limit_handling(task):
    client = XAgentClient(token="your-token")
    
    while True:
        try:
            return client.runs.start(task=task)
        except RateLimitError:
            print("Rate limited, waiting...")
            time.sleep(60)
```

#### 问题 3: 超时

```python
# 增加超时时间
from xagent import XAgentClient, ClientConfig

config = ClientConfig(
    token="your-token",
    timeout=60  # 增加到 60 秒
)

client = XAgentClient(config=config)
```

---

## 相关资源

- [API 参考文档](./API_COMPLETE_REFERENCE.md)
- [快速开始指南](./API_QUICKSTART.md)
- [使用示例](./API_EXAMPLES.md)
- [SDK 指南](../sdk/SDK_GUIDE.md)
- [变更日志](./API_CHANGELOG.md)
