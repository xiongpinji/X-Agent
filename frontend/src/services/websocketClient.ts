/**
 * WebSocket client for real-time notifications.
 * Connects to /api/v1/notifications/ws and manages reconnection.
 */

export interface Notification {
  type: string
  title: string
  body: string
  timestamp: number
  metadata?: Record<string, any>
}

type NotificationHandler = (notification: Notification) => void

class WebSocketClient {
  private ws: WebSocket | null = null
  private url: string
  private handlers: Set<NotificationHandler> = new Set()
  private reconnectAttempts = 0
  private maxReconnectAttempts = 10
  private reconnectDelay = 1000
  private pingInterval: ReturnType<typeof setInterval> | null = null
  private _connected = false

  constructor() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    this.url = `${protocol}//${window.location.host}/api/v1/notifications/ws`
  }

  get connected(): boolean {
    return this._connected
  }

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) return

    const token = localStorage.getItem('auth_token')
    const params = new URLSearchParams()
    if (token) params.set('token', token)

    try {
      this.ws = new WebSocket(`${this.url}?${params.toString()}`)

      this.ws.onopen = () => {
        this._connected = true
        this.reconnectAttempts = 0
        this.startPing()
        this.notify({ type: 'connected', title: '', body: '', timestamp: Date.now() / 1000 })
      }

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as Notification
          this.notify(data)
        } catch {
          // Ignore malformed messages
        }
      }

      this.ws.onclose = () => {
        this._connected = false
        this.stopPing()
        this.scheduleReconnect()
      }

      this.ws.onerror = () => {
        this._connected = false
      }
    } catch {
      this.scheduleReconnect()
    }
  }

  disconnect(): void {
    this.stopPing()
    if (this.ws) {
      this.ws.onclose = null
      this.ws.close()
      this.ws = null
    }
    this._connected = false
    this.reconnectAttempts = this.maxReconnectAttempts // Prevent reconnect
  }

  subscribe(handler: NotificationHandler): () => void {
    this.handlers.add(handler)
    return () => this.handlers.delete(handler)
  }

  private notify(notification: Notification): void {
    this.handlers.forEach(handler => handler(notification))
  }

  private startPing(): void {
    this.pingInterval = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }))
      }
    }, 30000)
  }

  private stopPing(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval)
      this.pingInterval = null
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) return
    this.reconnectAttempts++
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1)
    setTimeout(() => this.connect(), Math.min(delay, 30000))
  }
}

export const websocketClient = new WebSocketClient()
export default websocketClient
