import React from 'react'
import { isPandaPage } from '../pageRegistry'
import type { PandaPage } from '../types'

function getInitialPandaPage(): PandaPage {
  if (typeof window === 'undefined') {
    return 'home'
  }
  const page = window.location.hash.replace('#', '')
  return isPandaPage(page) ? page : 'home'
}

export function usePandaHashRoute() {
  const [activePage, setActivePage] = React.useState<PandaPage>(getInitialPandaPage)

  React.useEffect(() => {
    function syncHashRoute() {
      const page = window.location.hash.replace('#', '')
      setActivePage(isPandaPage(page) ? page : 'home')
    }

    window.addEventListener('hashchange', syncHashRoute)

    return () => {
      window.removeEventListener('hashchange', syncHashRoute)
    }
  }, [])

  const navigateToPage = React.useCallback((page: PandaPage) => {
    setActivePage(page)
    const nextHash = page === 'home' ? '' : `#${page}`
    if (window.location.hash !== nextHash) {
      window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}${nextHash}`)
    }
  }, [])

  return { activePage, navigateToPage }
}
