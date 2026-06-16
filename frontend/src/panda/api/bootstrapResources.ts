import { getPandaResourcesBffConfig, shouldUsePandaResourcesBff } from './resourcesBffConfig'
import { createPandaResourcesFetchClient } from './resourcesHttpClient'
import { createPandaResourcesApiLoader, setPandaResourcesApiLoader } from './resourcesApiLoader'

export function bootstrapPandaResources(env: ImportMetaEnv = import.meta.env) {
  const config = getPandaResourcesBffConfig(env)

  if (!config.enabled) {
    setPandaResourcesApiLoader(null)
    return
  }

  const client = createPandaResourcesFetchClient({
    endpoint: config.endpoint,
  })
  setPandaResourcesApiLoader(createPandaResourcesApiLoader(client))
}

bootstrapPandaResources()
