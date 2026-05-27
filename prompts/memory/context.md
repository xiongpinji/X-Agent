---
id: memory_context
name: Memory Context Prompt
version: 1.0.0
purpose: Guidelines for memory management
scope: memory
description: Instructs the agent on memory retrieval and storage
owner: x-agent
tags: [memory, context, retrieval]
deprecated: false
dependencies: [agent_system]
variables:
  max_context_tokens: 4000
  retrieval_limit: 10
---

# Memory Context Prompt

Manage task context and historical information effectively.

## Memory Types

1. **Short-term**: Current execution context
2. **Long-term**: Historical decisions and outcomes
3. **Semantic**: Conceptual relationships
4. **Episodic**: Specific events and traces

## Retrieval Strategy

- Query relevant memories before planning
- Rank by relevance and recency
- Limit to {{retrieval_limit}} most relevant items
- Respect token budget of {{max_context_tokens}}

## Storage Guidelines

- Store successful patterns
- Record failure modes
- Maintain decision rationale
- Update based on outcomes

## Inputs

- query: Memory query or context need
- context: Current execution context
- limit: Maximum items to retrieve

## Outputs

- memories: Retrieved relevant memories
- relevance_scores: Confidence scores
- summary: Condensed context summary
