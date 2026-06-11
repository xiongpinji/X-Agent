import React from 'react'
import { loadPandaWorkbenchHome, type PandaWorkbenchDataSource } from '../api/workbenchClient'
import type { PandaWorkbenchHome } from '../types'

export function usePandaHomeWorkbench() {
  const [home, setHome] = React.useState<PandaWorkbenchHome | null>(null)
  const [homeSource, setHomeSource] = React.useState<PandaWorkbenchDataSource>('mock')
  const [isLoading, setIsLoading] = React.useState(true)
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    let cancelled = false

    async function loadHome() {
      try {
        setIsLoading(true)
        const result = await loadPandaWorkbenchHome()
        if (!cancelled) {
          setHome(result.home)
          setHomeSource(result.source)
          setError(result.source === 'mock' ? result.error?.message ?? '本地演示数据已接管' : null)
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false)
        }
      }
    }

    void loadHome()

    return () => {
      cancelled = true
    }
  }, [])

  return { home, homeSource, isLoading, error }
}
