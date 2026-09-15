/**
 * App shell (Layout) tests
 *
 * Regression cover for the sidebar navigation fix. Layout used to render bare
 * `<a href>` rows and decide the active state from `window.location.pathname`,
 * which made every sidebar click a full document navigation: all lazy chunks
 * were re-fetched and all in-flight requests / component state were dropped.
 * It now uses react-router's NavLink.
 *
 * The core assertion is deliberately behavioural: a router-managed link calls
 * `preventDefault()` on the click, so `dispatchEvent()` returns `false`. A
 * reverted `<a href>` would let the browser navigate and return `true`.
 *
 * Also pinned here:
 *   - Layout now requires a Router ancestor (`useLocation`), so it must not be
 *     rendered standalone;
 *   - nested nav entries must not both highlight at once (the exact-match
 *     `end` flag) — the root route's `end` is deliberately *not* asserted,
 *     because react-router 7's `to="/"` can never prefix-match and such a test
 *     could not fail;
 *   - the role filter that decides which rows exist at all.
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, within, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom'
import Layout from '@/components/Layout'
import { I18nProvider } from '@/i18n/context'
import { useAppStore } from '@/store/appStore'

/** Renders whatever route is current, so navigation can be observed. */
const Probe = () => {
  const { pathname } = useLocation()
  return <div data-testid="probe">{pathname}</div>
}

function renderShell(initialPath = '/') {
  return render(
    <I18nProvider defaultLanguage="en">
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route
            path="*"
            element={
              <Layout>
                <Probe />
              </Layout>
            }
          />
        </Routes>
      </MemoryRouter>
    </I18nProvider>
  )
}

/** The sidebar is the app's only navigation landmark. */
function sidebar() {
  return within(screen.getByRole('navigation', { name: 'Main navigation' }))
}

beforeEach(() => {
  localStorage.clear()
  // The store is persisted, so it must be reset explicitly — clearing
  // localStorage alone leaves the already-hydrated state in place.
  useAppStore.setState({
    user: null,
    theme: 'light',
    sidebarOpen: true,
    isConnected: false,
  })
})

describe('Layout shell', () => {
  it('renders inside a Router without throwing', () => {
    renderShell('/')
    expect(screen.getByRole('navigation', { name: 'Main navigation' })).toBeInTheDocument()
    expect(screen.getByTestId('probe')).toHaveTextContent('/')
  })

  it('navigates sidebar clicks client-side instead of reloading the document', () => {
    renderShell('/')
    const tasks = sidebar().getByRole('link', { name: 'Tasks' })

    // `fireEvent.click` returns the result of `dispatchEvent`, which is false
    // when a handler cancelled the event. react-router's NavLink cancels it;
    // a plain <a href> would not, and the browser would reload the document.
    const notCancelled = fireEvent.click(tasks)
    expect(notCancelled).toBe(false)

    // ...and the route actually advanced.
    expect(screen.getByTestId('probe')).toHaveTextContent('/tasks')
  })

  it('marks the active route with aria-current="page"', () => {
    renderShell('/tasks')

    expect(sidebar().getByRole('link', { name: 'Tasks' })).toHaveAttribute(
      'aria-current',
      'page'
    )
    expect(sidebar().getByRole('link', { name: 'Chat' })).not.toHaveAttribute('aria-current')
  })

  it('highlights only the deepest matching row for nested nav entries', () => {
    // "/workflows" prefix-matches "/workflows/schedules", so without exact
    // matching both rows light up at once — the Schedules page would show
    // Workflows as the current location too.
    renderShell('/workflows/schedules')

    expect(sidebar().getByRole('link', { name: 'Schedules' })).toHaveAttribute(
      'aria-current',
      'page'
    )
    expect(sidebar().getByRole('link', { name: 'Workflows' })).not.toHaveAttribute(
      'aria-current'
    )
  })

  it('still highlights the parent row on its own route', () => {
    renderShell('/workflows')

    expect(sidebar().getByRole('link', { name: 'Workflows' })).toHaveAttribute(
      'aria-current',
      'page'
    )
  })

  it('keeps role-filtered rows out of the sidebar for a plain user', () => {
    localStorage.setItem('user_role', 'user')
    renderShell('/')

    expect(sidebar().getByRole('link', { name: 'Tasks' })).toBeInTheDocument()
    expect(sidebar().queryByRole('link', { name: 'Backup' })).toBeNull()
  })

  it('shows role-filtered rows for an admin', () => {
    localStorage.setItem('user_role', 'admin')
    renderShell('/')

    expect(sidebar().getByRole('link', { name: 'Backup' })).toBeInTheDocument()
  })
})
