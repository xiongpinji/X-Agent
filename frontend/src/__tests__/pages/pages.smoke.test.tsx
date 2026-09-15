/**
 * Page-level smoke tests
 *
 * Light rendering checks for the core surfaces (ChatPage, the console sub-app
 * and FeedbackDashboard). Heavy dependencies are mocked: apiClient network
 * methods, the workbench bootstrap fetch and the SSE EventSource (stubbed
 * globally in setup.ts).
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { ChatPage } from '@/pages/ChatPage'
import { ConsoleApp } from '@/console/ConsoleApp'
import { FeedbackDashboard } from '@/pages/FeedbackDashboard'
import { apiClient } from '@/services/api'
import { feedbackService } from '@/services/feedback'
import { useAppStore } from '@/store/appStore'
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

describe('FeedbackDashboard smoke', () => {
  const seeded = {
    id: 'fb-1',
    userId: 'u-1',
    type: 'bug' as const,
    category: 'UI',
    title: 'Seeded smoke feedback',
    description: 'Rendered from the mocked listFeedback response.',
    sentiment: 'negative' as const,
    priority: 'high' as const,
    status: 'open' as const,
    tags: ['smoke'],
    createdAt: '2026-09-14T00:00:00Z',
    updatedAt: '2026-09-14T00:00:00Z',
  }

  beforeEach(() => {
    localStorage.clear()
    useAppStore.setState({ isLoading: false, error: null })

    /*
     * The seeded row is load-bearing, not decoration: the dashboard heading
     * renders outside the data region, so an empty payload cannot tell the
     * difference between "load succeeded" and "load blew up". Only a
     * non-empty payload fails when the data never lands.
     */
    vi.spyOn(feedbackService, 'listFeedback').mockResolvedValue({
      items: [seeded],
      total: 1,
      page: 1,
      pageSize: 50,
      hasMore: false,
    })
    vi.spyOn(feedbackService, 'getStats').mockResolvedValue({
      total: 1,
      byType: { bug: 1 },
      byStatus: { open: 1 },
      bySentiment: { negative: 1 },
      byPriority: { high: 1 },
      avgResolutionTime: 0,
      resolutionRate: 0,
    })
    vi.spyOn(feedbackService, 'getTrends').mockResolvedValue([])

    /*
     * Notifications now have real backend endpoints (api/notification_configs.py,
     * mounted 2026-09-14), so the default mock resolves with one seeded channel.
     * The seeded value is load-bearing: asserting on the channel target is what
     * proves the notification payload reached the DOM — an empty payload could
     * not tell "load succeeded" apart from "load never happened".
     */
    vi.spyOn(feedbackService, 'listNotifications').mockResolvedValue([
      {
        id: 'nc-1',
        type: 'email',
        enabled: true,
        target: 'seeded-channel@example.com',
        triggers: ['new_feedback'],
        createdAt: '2026-09-14T00:00:00Z',
        updatedAt: '2026-09-14T00:00:00Z',
      },
    ])
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders feedback data from the core calls', async () => {
    render(
      <I18nProvider defaultLanguage="en">
        <FeedbackDashboard />
      </I18nProvider>
    )

    // The real assertion: data from the core calls actually reached the DOM.
    expect(await screen.findByText('Seeded smoke feedback')).toBeInTheDocument()
    expect(feedbackService.listNotifications).toHaveBeenCalled()
    expect(screen.queryByText('Loading feedbacks...')).not.toBeInTheDocument()
  })

  it('renders the notification channel fetched from the backend', async () => {
    render(
      <I18nProvider defaultLanguage="en">
        <FeedbackDashboard />
      </I18nProvider>
    )

    // NotificationSettings only mounts on the notifications tab, so the seeded
    // target can only appear after a real tab switch — that makes this a
    // end-to-end check of listNotifications -> adaptNotificationConfig -> DOM.
    fireEvent.click(await screen.findByRole('button', { name: /notifications/i }))
    expect(await screen.findByText('seeded-channel@example.com')).toBeInTheDocument()
  })

  it('surfaces a failed channel test instead of the old false success', async () => {
    /*
     * End-to-end guard for the reported bug: the page used to discard
     * testNotification's return value, so a backend 200 + success:false still
     * rendered "Test notification sent successfully". This walks the whole page
     * path — service mock -> handleTestNotification -> NotificationSettings.
     */
    vi.spyOn(feedbackService, 'testNotification').mockResolvedValue({
      success: false,
      message: '未配置真实邮件通道，本次未实际投递。',
    })

    render(
      <I18nProvider defaultLanguage="en">
        <FeedbackDashboard />
      </I18nProvider>
    )

    fireEvent.click(await screen.findByRole('button', { name: /notifications/i }))
    fireEvent.click(await screen.findByText('Test'))

    expect(await screen.findByText('未配置真实邮件通道，本次未实际投递。')).toBeInTheDocument()
    expect(screen.queryByText('Test notification sent successfully')).not.toBeInTheDocument()
  })

  it('still loads and renders its data when the notifications call rejects', async () => {
    // Regression guard for the load-time fail-fast amplifier: the notifications
    // call sits in its own try/catch, so a transient failure must not take the
    // whole page down (nor re-fail on the 30s interval).
    vi.mocked(feedbackService.listNotifications).mockRejectedValue(new Error('network down'))

    render(
      <I18nProvider defaultLanguage="en">
        <FeedbackDashboard />
      </I18nProvider>
    )

    expect(await screen.findByText('Seeded smoke feedback')).toBeInTheDocument()
    expect(screen.queryByText('Loading feedbacks...')).not.toBeInTheDocument()
  })
})
