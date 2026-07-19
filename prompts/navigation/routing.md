---
id: navigation_routing
name: Navigation Routing Prompt
version: 1.0.0
purpose: Guidelines for task routing and navigation
scope: navigation
description: Guides the agent in routing tasks to appropriate handlers
owner: x-agent
tags: [navigation, routing, orchestration]
deprecated: false
dependencies: [agent_system]
variables:
  routing_timeout: 5
  max_hops: 3
---

# Navigation Routing Prompt

Route tasks to appropriate handlers and capabilities.

## Routing Strategy

1. Analyze task characteristics
2. Match to available capabilities
3. Consider resource availability
4. Plan routing path
5. Execute with fallbacks

## Routing Criteria

- **Task Type**: Categorize the task
- **Complexity**: Estimate difficulty
- **Resources**: Check availability
- **Priority**: Consider urgency
- **Dependencies**: Identify prerequisites

## Fallback Strategy

- Primary handler unavailable: Use secondary
- Timeout exceeded: Escalate or simplify
- Resource exhausted: Queue or defer
- Capability mismatch: Decompose task

## Inputs

- task: The task to route
- available_handlers: List of available handlers
- constraints: Routing constraints

## Outputs

- handler: Selected handler
- path: Routing path
- fallbacks: Fallback options
- confidence: Routing confidence score
