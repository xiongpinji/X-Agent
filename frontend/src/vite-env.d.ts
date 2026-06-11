/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_PANDA_RESOURCES_BFF?: string
  readonly VITE_PANDA_RESOURCES_BFF_ENDPOINT?: string
}

interface Window {
  __ANALYTICS__?: {
    track: (event: string, payload: Record<string, unknown>) => void
  }
}
