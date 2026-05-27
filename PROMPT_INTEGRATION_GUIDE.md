# Prompt System Integration Guide

## Overview

This guide explains how to integrate the X-Agent Prompt Engineering Platform into existing code components.

## Integration Points

### 1. Agent Initialization (agent.py)

**Current Code Pattern:**
```python
# Hardcoded system prompt
SYSTEM_PROMPT = "You are X-Agent..."
```

**Integration Pattern:**
```python
from backend.app.core.prompt_manager import prompt_manager

class AgentLoop:
    def __init__(self, ...):
        # Initialize prompt manager
        prompt_manager.initialize()
        self.system_prompt_ctx = prompt_manager.get_system_prompt({
            "agent_name": "X-Agent",
            "phase": "Phase 0"
        })
    
    async def run(self, context: RunContext, ...):
        # Use prompt in LLM calls
        system_prompt = self.system_prompt_ctx.render()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task}
        ]
```

### 2. Planning Phase (agent_phases.py)

**Current Code Pattern:**
```python
class PlanningPhase:
    async def execute(self, phase_ctx: PhaseContext) -> list[AgentPlanStep]:
        # Inline planning logic
        plan = await loop._plan(context, trajectory, compact_context)
```

**Integration Pattern:**
```python
from backend.app.core.prompt_manager import prompt_manager

class PlanningPhase:
    async def execute(self, phase_ctx: PhaseContext) -> list[AgentPlanStep]:
        loop = phase_ctx.loop
        context = phase_ctx.context
        
        # Get planner role prompt
        planner_ctx = prompt_manager.get_role_prompt("planner", {
            "max_steps": 10,
            "max_subtasks": 5
        })
        
        # Build messages with role prompt
        messages = prompt_manager.build_messages(
            loop.system_prompt_ctx,
            f"Plan this task: {phase_ctx.task}",
            planner_ctx
        )
        
        # Call LLM with prompts
        response = await loop.llm.chat(messages, tools=[])
        plan = loop._parse_plan(response.content)
```

### 3. Execution Phase

**Integration Pattern:**
```python
class ExecutionPhase:
    async def execute(self, phase_ctx: PhaseContext) -> None:
        loop = phase_ctx.loop
        
        # Get executor role prompt
        executor_ctx = prompt_manager.get_role_prompt("executor", {
            "max_iterations": 10,
            "timeout_seconds": 300
        })
        
        for step in phase_ctx.plan_frame.steps:
            # Get tool-specific prompt if needed
            if step.tool_name:
                tool_ctx = prompt_manager.get_tool_prompt(step.tool_name, {
                    "timeout": 30,
                    "max_retries": 3
                })
            
            # Execute step with prompts
            result = await loop._execute_step(step, executor_ctx)
```

### 4. Verification Phase

**Integration Pattern:**
```python
class CompletionPhase:
    async def execute(self, phase_ctx: PhaseContext) -> AgentRunResponse:
        loop = phase_ctx.loop
        
        # Get verifier role prompt
        verifier_ctx = prompt_manager.get_role_prompt("verifier", {
            "min_confidence": 0.8
        })
        
        # Build verification messages
        messages = prompt_manager.build_messages(
            loop.system_prompt_ctx,
            f"Verify this result: {phase_ctx.answer}",
            verifier_ctx
        )
        
        # Verify with LLM
        response = await loop.llm.chat(messages, tools=[])
```

### 5. Error Recovery (repair_loop.py)

**Integration Pattern:**
```python
from backend.app.core.prompt_manager import prompt_manager

class RepairLoop:
    async def repair(self, error: Exception, context: RunContext):
        # Get recovery prompt
        recovery_ctx = prompt_manager.get_recovery_prompt("retry", {
            "max_retries": 3,
            "backoff_factor": 2
        })
        
        # Build recovery messages
        messages = prompt_manager.build_messages(
            self.system_prompt_ctx,
            f"Recover from error: {error}",
            recovery_ctx
        )
        
        # Get recovery suggestion
        response = await self.llm.chat(messages, tools=[])
```

### 6. Tool Execution (tools.py)

**Integration Pattern:**
```python
from backend.app.core.prompt_manager import prompt_manager

class ToolRegistry:
    async def execute_tool(self, tool_name: str, arguments: dict):
        # Get tool-specific prompt
        try:
            tool_ctx = prompt_manager.get_tool_prompt(tool_name, {
                "timeout": 30,
                "max_retries": 3
            })
            tool_instructions = tool_ctx.render()
        except ValueError:
            # Fallback if no specific prompt
            tool_instructions = f"Execute {tool_name} tool"
        
        # Execute tool with instructions
        result = await self._execute(tool_name, arguments, tool_instructions)
```

### 7. Orchestrator (orchestrator.py)

**Integration Pattern:**
```python
from backend.app.core.prompt_manager import prompt_manager

class CapabilityRouter:
    async def route(self, context: OrchestrationContext) -> CapabilityDecision:
        # Get navigation prompt
        nav_ctx = prompt_manager.get_prompts_by_scope("navigation")[0]
        nav_instructions = nav_ctx.render()
        
        # Route with prompt guidance
        decision = await self._route_with_guidance(context, nav_instructions)
```

## Step-by-Step Integration

### Phase 1: Minimal Integration (1-2 hours)

1. Add prompt manager initialization to AgentLoop.__init__()
2. Replace hardcoded system prompt with prompt_manager.get_system_prompt()
3. Test basic functionality

```python
# In agent.py
from backend.app.core.prompt_manager import prompt_manager

class AgentLoop:
    def __init__(self, ...):
        prompt_manager.initialize()
        self.system_prompt_ctx = prompt_manager.get_system_prompt()
```

### Phase 2: Role Integration (2-3 hours)

1. Integrate planner role prompt in PlanningPhase
2. Integrate executor role prompt in ExecutionPhase
3. Integrate verifier role prompt in CompletionPhase
4. Test role-based execution

### Phase 3: Tool Integration (2-3 hours)

1. Integrate tool prompts in ToolRegistry
2. Add tool-specific instructions to tool execution
3. Test tool execution with prompts

### Phase 4: Recovery Integration (1-2 hours)

1. Integrate recovery prompts in RepairLoop
2. Add recovery guidance to error handling
3. Test error recovery

### Phase 5: Full Integration (1-2 hours)

1. Integrate navigation prompts in Orchestrator
2. Add marketplace prompts for tool discovery
3. Add memory prompts for context management
4. Test full pipeline

## Testing Integration

### Unit Tests

```python
def test_agent_with_prompts():
    """Test agent initialization with prompts."""
    from backend.app.core.prompt_manager import prompt_manager
    
    prompt_manager.initialize()
    agent = AgentLoop(...)
    
    assert agent.system_prompt_ctx is not None
    assert len(agent.system_prompt_ctx.render()) > 0
```

### Integration Tests

```python
async def test_planning_with_prompts():
    """Test planning phase with prompts."""
    agent = AgentLoop(...)
    phase = PlanningPhase()
    
    phase_ctx = PhaseContext(...)
    plan = await phase.execute(phase_ctx)
    
    assert len(plan) > 0
    assert all(step.instruction for step in plan)
```

### End-to-End Tests

```python
async def test_full_execution_with_prompts():
    """Test full execution with prompt system."""
    agent = AgentLoop(...)
    context = RunContext(task="Test task")
    
    response = await agent.run(context)
    
    assert response.status == RunStatus.SUCCESS
    assert response.result is not None
```

## Migration Checklist

- [ ] Create prompts/ directory structure
- [ ] Create example prompts for each scope
- [ ] Implement PromptSchema and PromptLoader
- [ ] Implement PromptRegistry and PromptManager
- [ ] Add prompt_manager initialization to AgentLoop
- [ ] Replace hardcoded system prompt
- [ ] Integrate planner role prompt
- [ ] Integrate executor role prompt
- [ ] Integrate verifier role prompt
- [ ] Integrate tool prompts
- [ ] Integrate recovery prompts
- [ ] Add unit tests
- [ ] Add integration tests
- [ ] Update documentation
- [ ] Deploy and monitor

## Rollback Plan

If issues arise during integration:

1. **Revert to hardcoded prompts**: Keep old code as fallback
2. **Use feature flags**: Toggle between old and new system
3. **Gradual rollout**: Integrate one component at a time
4. **Monitor metrics**: Track performance and errors

```python
# Feature flag example
USE_PROMPT_SYSTEM = os.getenv("USE_PROMPT_SYSTEM", "false").lower() == "true"

if USE_PROMPT_SYSTEM:
    system_prompt = prompt_manager.get_system_prompt().render()
else:
    system_prompt = HARDCODED_SYSTEM_PROMPT
```

## Performance Considerations

1. **Caching**: Prompts are cached after first load
2. **Lazy Loading**: Load prompts only when needed
3. **Variable Substitution**: Minimal overhead for variable replacement
4. **Memory**: All prompts loaded into memory (typically < 1MB)

## Troubleshooting

### Prompt Not Found

```python
# Debug: List all available prompts
from backend.app.core.prompt_manager import prompt_manager

prompt_manager.initialize()
all_prompts = prompt_manager.registry.list_all_prompts()
for p in all_prompts:
    print(f"{p.metadata.scope}: {p.metadata.id}")
```

### Variable Substitution Issues

```python
# Debug: Check rendered content
ctx = prompt_manager.get_role_prompt("planner", {"max_steps": 10})
rendered = ctx.render()
print(rendered)
```

### Import Errors

```python
# Ensure prompt_manager is imported correctly
from backend.app.core.prompt_manager import prompt_manager

# Check if prompts directory exists
import os
prompts_dir = "backend/app/../../prompts"
print(f"Prompts directory exists: {os.path.exists(prompts_dir)}")
```

## Next Steps

1. Review this integration guide
2. Start with Phase 1 (minimal integration)
3. Test thoroughly before moving to next phase
4. Update documentation as you integrate
5. Monitor performance and errors
6. Gather feedback from team
7. Plan for future enhancements
