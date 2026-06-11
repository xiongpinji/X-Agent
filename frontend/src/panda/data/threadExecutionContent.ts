export const threadExecutionTabs = ['计划', '终端', '文件变更', 'Git diff', '浏览器预览', '审计证据'] as const

export const threadExecutionSteps = [
  '分析 MCPManager 与 MCPToolAdapter 接口契约',
  '运行定向测试并捕获失败证据',
  '生成最小修复 diff 与回归说明',
  '等待人审后创建 PR',
] as const

export const threadExecutionTerminalLines = [
  '$ uv run --isolated --python 3.11 pytest tests/test_mcp_manager.py -q',
  'collecting targeted tests...',
  '3 failed, 18 passed · root cause isolated to adapter contract',
  '$ git diff -- backend/app/core/mcp/manager.py',
] as const

export const threadExecutionControlActions = ['暂停', 'Steer 纠偏', '转交智能体', '请求审批'] as const

export const threadExecutionArtifactActions = ['修复 diff', '测试报告', '审计证据', 'PR 草稿'] as const
