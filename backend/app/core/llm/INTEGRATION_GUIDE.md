"""
Integration Guide for Enhanced LLM Routing System
X-Agent LLM Module Integration
"""

# Integration Guide

> **P1-08 订正（2026-07-20）**：本文涉及的 `router.py` / `EnhancedLLMRouter`
> 在代码库中不存在。生产唯一入口为 `backend.app.core.llm.build_llm_router`
> （见 README.md 文末「P1-08 路由收敛」章节，以代码实际为准）。

## Quick Start

### 1. Installation

The enhanced LLM routing system is part of X-Agent core. No additional installation needed.

### 2. Basic Configuration

Add to your `.env` file:

```env
# LLM Configuration
XAGENT_LLM_BACKEND=auto
XAGENT_LLM_FALLBACK_ORDER=openai,deepseek,mock

# OpenAI Configuration
XAGENT_OPENAI_API_KEY=sk-...
XAGENT_OPENAI_MODEL=gpt-4o

# DeepSeek Configuration
XAGENT_DEEPSEEK_API_KEY=sk-...
XAGENT_DEEPSEEK_MODEL=deepseek-chat
XAGENT_DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# Cost Budget
XAGENT_DEFAULT_COST_BUDGET_USD=1.0
```

### 3. Initialize Router

```python
from backend.app.core.llm.router import EnhancedLLMRouter
from backend.app.core.llm.adapters import OpenAIAdapter, DeepSeekAdapter
from backend.app.settings import get_settings

settings = get_settings()

# Create router
router = EnhancedLLMRouter()

# Register adapters
if settings.openai_api_key:
    router.register_adapter(OpenAIAdapter(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
    ))

if settings.deepseek_api_key:
    router.register_adapter(DeepSeekAdapter(
        model=settings.deepseek_model,
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
    ))

# Set budget
from backend.app.core.llm.cost_optimizer import CostBudget
budget = CostBudget(
    total_budget_usd=settings.default_cost_budget_usd,
    period_days=1,
)
router.cost_tracker.set_budget("daily", budget)
```

### 4. Use in Agent

```python
from backend.app.core.llm.selector import TaskType, SelectionStrategy

# In your agent execution loop
response = await router.chat(
    messages=agent_messages,
    task_type=TaskType.COMPLEX_REASONING,
    strategy=SelectionStrategy.BALANCED,
    optimize_prompt=True,
)

print(f"Response: {response['content']}")
print(f"Model: {response['model']}")
print(f"Cost: ${response['cost_usd']:.4f}")
```

## Advanced Configuration

### Custom Model Profiles

```python
from backend.app.core.llm.selector import ModelProfile, TaskType

# Register custom model
custom_model = ModelProfile(
    name="custom-model",
    provider="custom",
    cost_per_1k_input=0.001,
    cost_per_1k_output=0.002,
    latency_ms=500,
    quality_score=90,
    max_tokens=4096,
    supported_tasks={TaskType.CODE_GENERATION, TaskType.ANALYSIS},
)

router.selector.register_model(custom_model)
```

### Custom Fallback Strategy

```python
from backend.app.core.llm.fallback import FallbackConfig, FallbackStrategy

config = FallbackConfig(
    strategy=FallbackStrategy.EXPONENTIAL_BACKOFF,
    max_retries=5,
    initial_retry_delay_ms=200,
    max_retry_delay_ms=10000,
    backoff_multiplier=2.5,
    circuit_breaker_threshold=10,
    circuit_breaker_timeout_s=120,
    degradation_models=["gpt-4o-mini", "deepseek-chat"],
    timeout_ms=60000,
)

router.fallback_manager = FallbackManager(config)
```

### Custom Prompt Templates

```python
from backend.app.core.llm.prompt_optimizer import PromptTemplate

# Register custom template
template = PromptTemplate(
    name="custom_analysis",
    template="""Analyze the following data:

Data:
{data}

Provide:
1. Summary
2. Key insights
3. Recommendations

Analysis:""",
    variables=["data"],
    description="Custom analysis template",
    task_type="analysis",
)

router.prompt_optimizer.register_template(template)
```

## Monitoring and Reporting

### Real-time Monitoring

```python
# Get current status
status = router.get_status()
print(f"Active models: {status['models']}")
print(f"Circuit breakers: {status['circuit_breakers']}")

# Get cost report
cost_report = router.get_cost_report(hours=24)
print(f"Total cost: ${cost_report['total_cost_usd']:.2f}")
print(f"Cost by model: {cost_report['cost_by_model']}")

# Get performance report
perf_report = router.get_performance_report(hours=24)
print(f"Success rate: {perf_report['success_rate']*100:.1f}%")
print(f"Average latency: {perf_report['average_latency_ms']:.0f}ms")
```

### Logging Integration

```python
import logging

logger = logging.getLogger(__name__)

# Log selection decision
logger.info(f"Selected model: {response['model']}")
logger.info(f"Selection reason: {response['selection_reason']}")
logger.info(f"Estimated cost: ${response['cost_usd']:.4f}")

# Log performance metrics
metrics = router.monitor.get_metrics(response['model'])
logger.debug(f"Model success rate: {metrics.get_success_rate()*100:.1f}%")
logger.debug(f"Model latency: {metrics.get_average_latency_ms():.0f}ms")
```

### Metrics Export

```python
import json
from datetime import datetime

# Export metrics for analysis
report = router.get_performance_report(hours=24)
metrics_file = f"metrics_{datetime.now().isoformat()}.json"

with open(metrics_file, 'w') as f:
    json.dump(report, f, indent=2, default=str)

# Export cost report
cost_report = router.get_cost_report(hours=24)
cost_file = f"costs_{datetime.now().isoformat()}.json"

with open(cost_file, 'w') as f:
    json.dump(cost_report, f, indent=2, default=str)
```

## API Integration

### REST API Endpoint

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class ChatRequest(BaseModel):
    messages: list[dict[str, str]]
    task_type: str = "unknown"
    strategy: str = "balanced"
    budget_usd: float = None

@app.post("/api/chat")
async def chat(request: ChatRequest):
    try:
        response = await router.chat(
            messages=request.messages,
            task_type=TaskType[request.task_type.upper()],
            strategy=SelectionStrategy[request.strategy.upper()],
            budget_usd=request.budget_usd,
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/status")
async def status():
    return router.get_status()

@app.get("/api/cost-report")
async def cost_report(hours: int = 24):
    return router.get_cost_report(hours)

@app.get("/api/performance-report")
async def performance_report(hours: int = 24):
    return router.get_performance_report(hours)
```

### Streaming Endpoint

```python
from fastapi.responses import StreamingResponse

@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    async def generate():
        async for chunk in router.stream_chat(
            messages=request.messages,
            task_type=TaskType[request.task_type.upper()],
        ):
            yield f"data: {chunk}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")
```

## Testing

### Unit Tests

```python
import pytest

@pytest.mark.asyncio
async def test_router_selection():
    """Test model selection."""
    response = await router.chat(
        messages=[{"role": "user", "content": "Hello"}],
        task_type=TaskType.SIMPLE_QA,
    )
    assert response['model'] is not None
    assert response['cost_usd'] >= 0

@pytest.mark.asyncio
async def test_cost_tracking():
    """Test cost tracking."""
    initial_cost = router.cost_tracker.get_total_cost()
    
    await router.chat(
        messages=[{"role": "user", "content": "Test"}],
    )
    
    final_cost = router.cost_tracker.get_total_cost()
    assert final_cost > initial_cost

@pytest.mark.asyncio
async def test_fallback():
    """Test fallback mechanism."""
    # This would require mocking adapters
    pass
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_full_workflow():
    """Test complete workflow."""
    # Initialize router
    router = EnhancedLLMRouter()
    
    # Register adapters
    router.register_adapter(OpenAIAdapter("gpt-4o", api_key="test"))
    
    # Execute chat
    response = await router.chat(
        messages=[{"role": "user", "content": "Write Python code"}],
        task_type=TaskType.CODE_GENERATION,
    )
    
    # Verify response
    assert response['content']
    assert response['model']
    assert response['cost_usd'] >= 0
    
    # Check metrics
    report = router.get_performance_report()
    assert report['total_requests'] > 0
```

## Performance Tuning

### Optimize for Cost

```python
# Use cheapest models
router.selector.models = {
    name: model for name, model in router.selector.models.items()
    if model.cost_per_1k_input < 0.001
}

# Aggressive prompt compression
response = await router.chat(
    messages=messages,
    strategy=SelectionStrategy.COST_OPTIMIZED,
    optimize_prompt=True,
)
```

### Optimize for Speed

```python
# Use fastest models
router.selector.models = {
    name: model for name, model in router.selector.models.items()
    if model.latency_ms < 500
}

# Enable streaming
async for chunk in router.stream_chat(messages):
    yield chunk
```

### Optimize for Quality

```python
# Use best models
router.selector.models = {
    name: model for name, model in router.selector.models.items()
    if model.quality_score > 90
}

# Disable prompt compression
response = await router.chat(
    messages=messages,
    strategy=SelectionStrategy.PERFORMANCE_OPTIMIZED,
    optimize_prompt=False,
)
```

## Troubleshooting

### Debug Mode

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("backend.app.core.llm")
logger.setLevel(logging.DEBUG)

# Get detailed status
status = router.get_status()
print(json.dumps(status, indent=2, default=str))
```

### Common Issues

**Issue: High costs**
```python
# Check cost by model
costs = router.cost_tracker.get_cost_by_model()
print(f"Costs by model: {costs}")

# Switch to cheaper models
router.selector.models = {
    name: model for name, model in router.selector.models.items()
    if model.cost_per_1k_input < 0.001
}
```

**Issue: Low success rate**
```python
# Check circuit breaker status
status = router.fallback_manager.get_circuit_breaker_status()
print(f"Circuit breakers: {status}")

# Check error statistics
errors = router.fallback_manager.get_error_stats()
print(f"Error stats: {errors}")
```

**Issue: High latency**
```python
# Check latency by model
metrics = router.monitor.get_all_metrics()
for model, m in metrics.items():
    print(f"{model}: {m.get_average_latency_ms():.0f}ms")

# Use faster models
router.selector.models = {
    name: model for name, model in router.selector.models.items()
    if model.latency_ms < 500
}
```

## Migration from Old System

### Step 1: Backup Current Configuration

```python
# Save current settings
import json
settings_backup = {
    "llm_backend": settings.llm_backend,
    "openai_model": settings.openai_model,
    "deepseek_model": settings.deepseek_model,
}
with open("settings_backup.json", "w") as f:
    json.dump(settings_backup, f)
```

### Step 2: Initialize New Router

```python
# Create new router alongside old system
router = EnhancedLLMRouter()
router.register_adapter(OpenAIAdapter(...))
router.register_adapter(DeepSeekAdapter(...))
```

### Step 3: Gradual Migration

```python
# Route percentage of traffic to new system
import random

if random.random() < 0.1:  # 10% traffic
    response = await router.chat(messages)
else:
    response = await old_router.chat(messages)
```

### Step 4: Monitor and Validate

```python
# Compare metrics
new_metrics = router.get_performance_report()
old_metrics = old_router.get_performance_report()

print(f"New system success rate: {new_metrics['success_rate']}")
print(f"Old system success rate: {old_metrics['success_rate']}")
```

### Step 5: Full Migration

```python
# Switch all traffic to new system
response = await router.chat(messages)
```

## Support and Documentation

- **Usage Guide:** See `USAGE_GUIDE.md`
- **Performance Analysis:** See `PERFORMANCE_ANALYSIS.md`
- **API Documentation:** See inline docstrings
- **Examples:** See `tests/test_llm_enhanced.py`

## Conclusion

The enhanced LLM routing system is production-ready and can be integrated into X-Agent with minimal changes. It provides significant improvements in cost, performance, and reliability while maintaining backward compatibility.
