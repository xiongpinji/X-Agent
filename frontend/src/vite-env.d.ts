/// <reference types="vite/client" />

interface Window {
  __ANALYTICS__?: {
    track: (event: string, payload: Record<string, unknown>) => void
  }
}
