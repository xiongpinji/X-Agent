// Global window augmentations used by the mounted tree.
interface WindowAnalytics {
  track(event: string, payload?: Record<string, unknown>): void
}

declare global {
  interface Window {
    __ANALYTICS__?: WindowAnalytics
  }
}

export {}
