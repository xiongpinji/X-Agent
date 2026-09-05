/**
 * Page-level smoke tests
 *
 * Light rendering checks for the two core surfaces (ChatPage and the console
 * sub-app). Heavy dependencies are mocked: apiClient network methods, the
 * workbench bootstrap fetch and the SSE EventSource (stubbed globally in
 * setup.ts).
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ChatPage } from '@/pages/ChatPage'
import { ConsoleApp } from '@/console/ConsoleApp'
import { apiClient } from '@/services/api'
import { I18nProvider } from '@/i18n/context'

describe('ChatPage smoke', () => {
  beforeEach(() => {
    localStorage.clear()
    // Mount-time data loading: keep both network paths silent and empty.
    vi.spyOn(apiClient, 'listChatSessions').mockResolvedValue([])
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the chat shell (title + composer) without crashing', async () => {
    render(
      <I18nProvider defaultLanguage="en">
        <ChatPage />
      </I18nProvider>
    )

    // en.json maps chat.title -> "Chat"
    expect(await screen.findByText('Chat')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Type your message...')).toBeInTheDocument()
    expect(screen.getByLabelText('Select Agent')).toBeInTheDocument()
  })

  it('seeds the agent selector from the workbench bootstrap', async () => {
    vi.spyOn(apiClient, 'getWorkbenchBootstrap').mockResolvedValue({
      console: {
        tenant_id: 't-1',
        user_id: 'u-1',
        agent_id: 'agent-42',
        session_id: 's-1',
        created_at: new Date().toISOString(),
      },
      entries: [],
    })

    render(
      <I18nProvider defaultLanguage="en">
        <ChatPage />
      </I18nProvider>
    )

    // The selector falls back to "Default Agent" with the bootstrap agent_id
    expect(await screen.findByText('Default Agent')).toBeInTheDocument()
    expect(
      (screen.getByLabelText('Select Agent') as HTMLSelectElement).value
    ).toBe('agent-42')
    expect(apiClient.getWorkbenchBootstrap).toHaveBeenCalled()
  })
})

describe('ConsoleApp smoke', () => {
  beforeEach(() => {
    localStorage.clear()
    // Workbench bootstrap: answer with a non-ok response so the shell falls
    // back to its idle/polling state instead of real network access.
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, json: async () => ({}) }))
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders the console shell with the overview page', async () => {
    render(<ConsoleApp />)

    // Overview page heading from src/console/pages/overview/OverviewPage
    expect(await screen.findByText('统一控制台总览')).toBeInTheDocument()
    expect(document.querySelector('.console-root')).toBeInTheDocument()
  })
})
