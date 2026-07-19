---
id: marketplace_discovery
name: Marketplace Discovery Prompt
version: 1.0.0
purpose: Guidelines for discovering and evaluating tools
scope: marketplace
description: Helps the agent discover and select appropriate tools
owner: x-agent
tags: [marketplace, discovery, tools]
deprecated: false
dependencies: [agent_system]
variables:
  max_tools: 5
  min_rating: 4.0
---

# Marketplace Discovery Prompt

Discover and evaluate tools from the X-Agent marketplace.

## Discovery Process

1. Search marketplace for relevant tools
2. Filter by capability and rating
3. Evaluate compatibility
4. Check dependencies
5. Assess performance impact

## Evaluation Criteria

- **Capability**: Does it solve the problem?
- **Reliability**: Success rate and uptime
- **Performance**: Latency and resource usage
- **Cost**: Pricing and quota limits
- **Support**: Documentation and community

## Selection Strategy

- Prefer well-tested tools
- Consider cost-benefit tradeoff
- Evaluate integration effort
- Plan for fallbacks

## Inputs

- capability: Required capability
- context: Current execution context
- constraints: Performance and cost constraints

## Outputs

- tools: List of matching tools
- recommendations: Top recommendations
- evaluation: Detailed evaluation results
