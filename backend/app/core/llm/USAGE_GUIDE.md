"""
X-Agent Enhanced LLM Routing System - Usage Guide and Best Practices

This document provides comprehensive guidance on using the enhanced LLM routing system.
"""

# Enhanced LLM Routing System - Complete Guide

> **P1-08 订正（2026-07-20）**：本文示例中的 `router.py` / `EnhancedLLMRouter`
> 在代码库中不存在。生产唯一入口为 `backend.app.core.llm.build_llm_router`
> （见 README.md 文末「P1-08 路由收敛」章节，以代码实际为准）。

## Overview

The enhanced LLM routing system provides intelligent model selection, cost optimization, 
performance monitoring, and fallback strategies for managing multiple LLM providers.

## Key Components

### 1. Model Selector (selector.py)
Intelligently selects the best model based on task characteristics and constraints.

**Features:**
- Multiple selection strategies (cost, performance, latency, availability, balanced, A/B testing)
- Task-aware model selection
- Budget and latency constraints
- Performance history tracking
- A/B testing support

**Usage:**
```python
from backend.app.core.llm.selector import ModelSelector, SelectionContext, TaskType, SelectionStrategy

selector = ModelSelector()

# Create selection context
context = SelectionContext(
    task_type=TaskType.CODE_GENERATION,
    strategy=SelectionStrategy.BALANCED,
    budget_usd=0.05,
    input_tokens=1000,
    expected_output_tokens=500,
)

# Select model
result = selector.select(context)
print(f"Selected: {result.selected_model}")
print(f"Reason: {result.reason}")
print(f"Estimated cost: ${result.estimated_cost:.4f}")
```

### 2. Cost Optimizer (cost_optimizer.py)
Tracks and optimizes LLM usage costs.

**Features:**
- Token usage estimation
- Cost tracking by model, provider, task type, and user
- Budget management with alerts
- Cost efficiency analysis
- Optimization recommendations

**Usage:**
```python
from backend.app.core.llm.cost_optimizer import CostTracker, CostBudget

tracker = CostTracker()

# Set budget
budget = CostBudget(total_budget_usd=100.0, period_days=1)
tracker.set_budget("daily", budget)

# Record API calls
tracker.record_call(
    model="gpt-4o",
    provider="openai",
    input_tokens=1000,
    output_tokens=500,
    cost_usd=0.015,
    success=True,
    latency_ms=800,
)

# Get reports
report = tracker.get_report(hours=24)
print(f"Total cost: ${report['total_cost_usd']:.2f}")
print(f"Success rate: {report['success_rate']*100:.1f}%")
```

### 3. Fallback Manager (fallback.py)
Handles errors and implements fallback strategies.

**Features:**
- Circuit breaker pattern
- Exponential backoff retry
- Error classification
- Fallback model selection
- Error statistics

**Usage:**
```python
from backend.app.core.llm.fallback import FallbackManager, FallbackConfig, FallbackStrategy

config = FallbackConfig(
    strategy=FallbackStrategy.EXPONENTIAL_BACKOFF,
    max_retries=3,
    initial_retry_delay_ms=100,
    backoff_multiplier=2.0,
)

manager = FallbackManager(config)

# Execute with fallback
try:
    result = await manager.execute_with_fallback(
        primary_fn=lambda: call_openai(),
        fallback_fns=[
            lambda: call_deepseek(),
            lambda: call_local_model(),
        ],
        model_name="gpt-4o",
    )
except Exception as e:
    print(f"All fallbacks failed: {e}")
```

### 4. Stream Manager (streaming.py)
Manages streaming responses from LLMs.

**Features:**
- Stream creation and tracking
- Chunk buffering
- SSE and JSON Lines output formats
- Stream cleanup
- Statistics

**Usage:**
```python
from backend.app.core.llm.streaming import StreamManager, StreamChunk

manager = StreamManager()

# Create stream
stream = manager.create_stream("gpt-4o", "openai", "req-123")

# Add chunks as they arrive
chunk = StreamChunk(content="Hello ", token_count=1)
manager.add_chunk("req-123", chunk)

# Convert to SSE format
async for sse_line in manager.stream_to_sse("req-123"):
    print(sse_line)
```

### 5. Prompt Optimizer (prompt_optimizer.py)
Optimizes prompts for better performance and cost.

**Features:**
- Prompt templates
- Compression
- Model-specific optimization
- Few-shot example management
- Optimization recommendations

**Usage:**
```python
from backend.app.core.llm.prompt_optimizer import PromptOptimizer, PromptTemplate

optimizer = PromptOptimizer()

# Use template
template = optimizer.get_template("code_generation")
prompt = template.render(language="Python", task="Sort a list")

# Optimize for model
optimized = optimizer.optimize_for_model(prompt, "gpt-4o-mini")

# Add examples
examples = [
    {"input": "Sort [3,1,2]", "output": "[1,2,3]"},
]
enhanced = optimizer.add_few_shot_examples(optimized, examples)
```

### 6. Performance Monitor (monitor.py)
Monitors and analyzes model performance.

**Features:**
- Request tracking
- Latency percentiles (p95, p99)
- Success rate calculation
- Cost per token analysis
- Performance trends
- Alerts

**Usage:**
```python
from backend.app.core.llm.monitor import PerformanceMonitor

monitor = PerformanceMonitor()

# Record request
monitor.record_request(
    model_name="gpt-4o",
    provider="openai",
    success=True,
    latency_ms=500,
    tokens_used=1000,
    cost_usd=0.01,
    quality_score=0.95,
)

# Get metrics
metrics = monitor.get_metrics("gpt-4o")
print(f"Success rate: {metrics.get_success_rate()*100:.1f}%")
print(f"P95 latency: {metrics.get_p95_latency_ms():.0f}ms")

# Compare models
comparison = monitor.compare_models(["gpt-4o", "gpt-4o-mini"])
best_speed = monitor.get_best_model_for("speed")
```

### 7. LLM Adapters (adapters/)
Unified interface for different LLM providers.

**Supported Adapters:**
- OpenAIAdapter: For OpenAI models (GPT-4, GPT-4 Mini)
- DeepSeekAdapter: For DeepSeek models
- LocalAdapter: For locally-hosted models

**Usage:**
```python
from backend.app.core.llm.adapters import OpenAIAdapter, DeepSeekAdapter

# Create adapters
openai_adapter = OpenAIAdapter(
    model="gpt-4o",
    api_key="sk-...",
)

deepseek_adapter = DeepSeekAdapter(
    model="deepseek-chat",
    api_key="sk-...",
    base_url="https://api.deepseek.com/v1",
)

# Use adapter
response = await openai_adapter.chat(messages, tools)
print(response.content)
```

### 8. Enhanced LLM Router (router.py)
Orchestrates all components for intelligent routing.

**Features:**
- Intelligent model selection
- Automatic prompt optimization
- Cost tracking and reporting
- Performance monitoring
- Fallback handling
- Streaming support

**Usage:**
```python
from backend.app.core.llm.router import EnhancedLLMRouter
from backend.app.core.llm.adapters import OpenAIAdapter, DeepSeekAdapter
from backend.app.core.llm.selector import TaskType, SelectionStrategy

# Create router
router = EnhancedLLMRouter()

# Register adapters
router.register_adapter(OpenAIAdapter("gpt-4o", api_key="sk-..."))
router.register_adapter(DeepSeekAdapter("deepseek-chat", api_key="sk-..."))

# Execute chat
response = await router.chat(
    messages=[{"role": "user", "content": "Write Python code to sort a list"}],
    task_type=TaskType.CODE_GENERATION,
    strategy=SelectionStrategy.BALANCED,
    budget_usd=0.05,
    optimize_prompt=True,
)

print(f"Response: {response['content']}")
print(f"Model: {response['model']}")
print(f"Cost: ${response['cost_usd']:.4f}")
print(f"Reason: {response['selection_reason']}")

# Get reports
cost_report = router.get_cost_report(hours=24)
perf_report = router.get_performance_report(hours=24)
recommendations = router.get_optimization_recommendations()
```

## Best Practices

### 1. Model Selection Strategy

**For Cost Optimization:**
```python
context = SelectionContext(
    strategy=SelectionStrategy.COST_OPTIMIZED,
    budget_usd=0.01,
)
```

**For Quality:**
```python
context = SelectionContext(
    strategy=SelectionStrategy.PERFORMANCE_OPTIMIZED,
    required_quality_score=0.9,
)
```

**For Speed:**
```python
context = SelectionContext(
    strategy=SelectionStrategy.LATENCY_OPTIMIZED,
    max_latency_ms=1000,
)
```

**For Balanced Approach (Recommended):**
```python
context = SelectionContext(
    strategy=SelectionStrategy.BALANCED,
    budget_usd=0.05,
    max_latency_ms=5000,
)
```

### 2. Budget Management

```python
# Set daily budget
budget = CostBudget(
    total_budget_usd=100.0,
    period_days=1,
    alert_threshold_percent=80.0,
    hard_limit=True,  # Reject requests over budget
)
tracker.set_budget("daily", budget)

# Monitor alerts
alerts = tracker.get_alerts(hours=24)
for alert in alerts:
    print(f"Alert: {alert['message']}")
```

### 3. Error Handling and Fallback

```python
config = FallbackConfig(
    strategy=FallbackStrategy.EXPONENTIAL_BACKOFF,
    max_retries=3,
    degradation_models=["gpt-4o-mini", "deepseek-chat"],
)

manager = FallbackManager(config)

try:
    result = await manager.execute_with_fallback(
        primary_fn=lambda: call_primary(),
        fallback_fns=[
            lambda: call_fallback_1(),
            lambda: call_fallback_2(),
        ],
    )
except Exception as e:
    # Handle final failure
    logger.error(f"Request failed: {e}")
```

### 4. Prompt Optimization

```python
# Always optimize prompts for cheaper models
if model == "gpt-4o-mini":
    prompt = optimizer.compress_prompt(prompt, target_tokens=150)
    prompt = optimizer.optimize_for_model(prompt, "gpt-4o-mini")

# Add examples for complex tasks
if task_type == TaskType.CODE_GENERATION:
    examples = [
        {"input": "Sort a list", "output": "def sort_list(lst): return sorted(lst)"},
    ]
    prompt = optimizer.add_few_shot_examples(prompt, examples)
```

### 5. Performance Monitoring

```python
# Record all requests
monitor.record_request(
    model_name=model,
    provider=provider,
    success=success,
    latency_ms=latency,
    tokens_used=tokens,
    cost_usd=cost,
    quality_score=quality,
)

# Regular analysis
report = monitor.get_report(hours=24)
if report["success_rate"] < 0.95:
    logger.warning("Low success rate detected")

# Find best model for use case
best_model = monitor.get_best_model_for("speed")
```

### 6. Streaming Responses

```python
# Create stream
stream = manager.create_stream(model, provider, request_id)

# Stream chunks
async for chunk in adapter.stream_chat(messages):
    manager.add_chunk(request_id, StreamChunk(content=chunk))
    yield chunk  # Send to client

# Complete stream
manager.complete_stream(request_id)

# Cleanup old streams
manager.cleanup_old_streams(max_age_s=3600)
```

## Performance Optimization Tips

1. **Use Task-Specific Models:**
   - Use `deepseek-coder` for code generation
   - Use `gpt-4o-mini` for simple QA
   - Use `gpt-4o` for complex reasoning

2. **Implement Caching:**
   - Cache similar prompts
   - Reuse responses for identical queries
   - Use semantic caching for similar questions

3. **Batch Requests:**
   - Group similar requests
   - Use batch APIs when available
   - Reduce API call overhead

4. **Monitor Costs:**
   - Set daily budgets
   - Track cost per task type
   - Identify expensive operations

5. **Optimize Prompts:**
   - Remove filler words
   - Use clear structure
   - Add relevant examples
   - Compress long prompts

## Troubleshooting

### High Costs
1. Check cost by model: `tracker.get_cost_by_model()`
2. Switch to cheaper models for simple tasks
3. Compress prompts to reduce token usage
4. Implement caching

### Low Success Rate
1. Check circuit breaker status: `manager.get_circuit_breaker_status()`
2. Review error statistics: `manager.get_error_stats()`
3. Increase retry attempts
4. Add more fallback models

### High Latency
1. Check latency by model: `monitor.get_metrics(model).get_average_latency_ms()`
2. Switch to faster models
3. Reduce prompt size
4. Use streaming for long responses

## Configuration Examples

### Development Environment
```python
router = EnhancedLLMRouter()
router.register_adapter(OpenAIAdapter("gpt-4o-mini", api_key="sk-..."))
router.register_adapter(LocalAdapter("llama-2"))
```

### Production Environment
```python
router = EnhancedLLMRouter()
router.register_adapter(OpenAIAdapter("gpt-4o", api_key="sk-..."))
router.register_adapter(DeepSeekAdapter("deepseek-chat", api_key="sk-..."))
router.register_adapter(OpenAIAdapter("gpt-4o-mini", api_key="sk-..."))

# Set budgets
budget = CostBudget(total_budget_usd=1000.0, period_days=1, hard_limit=True)
router.cost_tracker.set_budget("daily", budget)
```

## Metrics and Reporting

### Key Metrics
- **Success Rate:** Percentage of successful API calls
- **Average Latency:** Mean response time
- **P95/P99 Latency:** 95th/99th percentile response times
- **Cost per Token:** Average cost per 1000 tokens
- **Quality Score:** User-provided quality rating

### Reports
- **Cost Report:** Breakdown by model, provider, task type, user
- **Performance Report:** Latency, success rate, quality metrics
- **Trend Analysis:** Performance over time
- **Recommendations:** Optimization suggestions

## Integration with X-Agent

The enhanced LLM routing system integrates seamlessly with X-Agent:

```python
# In agent initialization
from backend.app.core.llm.router import EnhancedLLMRouter

router = EnhancedLLMRouter()
# ... register adapters ...

# In agent execution
response = await router.chat(
    messages=agent_messages,
    task_type=TaskType.COMPLEX_REASONING,
    strategy=SelectionStrategy.BALANCED,
)

# Track performance
agent_metrics = router.get_performance_report()
```

## Future Enhancements

1. **Semantic Caching:** Cache responses for semantically similar queries
2. **Multi-Modal Support:** Handle images, audio, and video
3. **Fine-tuning:** Support for fine-tuned models
4. **Custom Models:** Integration with custom LLM endpoints
5. **Advanced Analytics:** ML-based cost and performance prediction
6. **Rate Limiting:** Per-user and per-model rate limits
7. **Request Queuing:** Intelligent request queuing and prioritization
