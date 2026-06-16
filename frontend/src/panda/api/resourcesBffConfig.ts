import { resolvePandaResourcesEndpoint } from './resourcesHttpClient'

export const PANDA_RESOURCES_BFF_FLAG = 'true'

export type PandaResourcesBffEnv = Partial<Pick<ImportMetaEnv, 'VITE_PANDA_RESOURCES_BFF' | 'VITE_PANDA_RESOURCES_BFF_ENDPOINT'>>

export function shouldUsePandaResourcesBff(env: PandaResourcesBffEnv | undefined = import.meta.env): boolean {
  return env?.VITE_PANDA_RESOURCES_BFF === PANDA_RESOURCES_BFF_FLAG
}

export function getPandaResourcesBffConfig(env: PandaResourcesBffEnv | undefined = import.meta.env) {
  return {
    enabled: shouldUsePandaResourcesBff(env),
    endpoint: resolvePandaResourcesEndpoint(env?.VITE_PANDA_RESOURCES_BFF_ENDPOINT),
  }
}
