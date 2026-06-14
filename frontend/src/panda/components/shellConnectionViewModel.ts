export type ShellConnectionViewModel = {
  readonly connectionLabel: string
}

export function buildShellConnectionViewModel({
  isLoading,
  error,
}: {
  readonly isLoading: boolean
  readonly error: string | null
}): ShellConnectionViewModel {
  if (isLoading) {
    return { connectionLabel: '同步工作台数据中' }
  }

  return { connectionLabel: error ? '本地演示数据已接管' : '已连接 X-Agent Core' }
}
