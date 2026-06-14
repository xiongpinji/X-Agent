export type ModuleDeliverySurfaceItem = {
  readonly label: string
  readonly description: string
}

export const moduleDeliverySurfaceItems = [
  { label: '总览', description: '支持加载、错误、空状态和权限状态。' },
  { label: '管理', description: '支持加载、错误、空状态和权限状态。' },
  { label: '详情', description: '支持加载、错误、空状态和权限状态。' },
  { label: '历史/审计', description: '支持加载、错误、空状态和权限状态。' },
] as const satisfies readonly ModuleDeliverySurfaceItem[]
