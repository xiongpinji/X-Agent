import React from 'react'
import { loadPandaWorkbenchHome, type PandaWorkbenchDataSource } from '../api/workbenchClient'
import type { PandaWorkbenchHome } from '../types'
import { buildPandaHomeWorkbenchViewModel } from './homeWorkbenchViewModel'

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
          const viewModel = buildPandaHomeWorkbenchViewModel(result)
          setHome(viewModel.home)
          setHomeSource(viewModel.homeSource)
          setError(viewModel.error)
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
