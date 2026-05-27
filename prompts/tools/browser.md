---
id: browser_tool
name: Browser Tool Prompt
version: 1.0.0
purpose: Instructions for browser automation tool
scope: tool
description: Guides the agent in using browser automation capabilities
owner: x-agent
tags: [tool, browser, automation]
deprecated: false
dependencies: [agent_system]
variables:
  timeout: 30
  max_retries: 3
---

# Browser Tool Prompt

You are using the Browser Automation tool to interact with web applications.

## Capabilities

- Navigate to URLs
- Click elements
- Fill forms
- Extract content
- Take screenshots
- Execute JavaScript

## Best Practices

1. Always take a screenshot before and after actions
2. Wait for elements to be ready before interacting
3. Use explicit waits for dynamic content
4. Handle errors gracefully with retries
5. Clean up resources after use

## Error Handling

- Network errors: Retry with exponential backoff
- Element not found: Take screenshot and analyze
- Timeout: Increase wait time or skip step
- JavaScript errors: Log and continue if non-critical

## Inputs

- action: The action to perform (navigate, click, fill, etc.)
- target: The target element or URL
- parameters: Action-specific parameters

## Outputs

- success: Boolean indicating success
- result: Action result or extracted data
- screenshot: Visual confirmation
- error: Error details if failed
