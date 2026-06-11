export const PANDA_ROUTE_ROLLOVER_SOURCE = 'frontend/scripts/panda-route-rollover-plan.mjs'

export function buildPandaRouteRolloverPlan({ manifest, contracts, apiKeyByViewKey }) {
  const routes = manifest.routes.map((route) => {
    const contract = contracts.get(route)
    if (!contract) {
      throw new Error(`Missing Panda resource contract for route: ${route}`)
    }
    return {
      route,
      readiness: contract.readiness,
      endpoint: contract.bffEndpoint,
      viewResources: contract.resourceKeys,
      apiResources: contract.resourceKeys.map((key) => apiKeyByViewKey.get(key) ?? key),
      runtimeFields: contract.runtimeFields,
      apiNeeds: contract.apiNeeds,
    }
  })
  const pendingRoutes = routes.filter((route) => route.readiness === 'mock-ready')
  const apiWiredRoutes = routes.filter((route) => route.readiness === 'api-wired')
  return {
    sourceScript: PANDA_ROUTE_ROLLOVER_SOURCE,
    routes,
    pendingRoutes,
    apiWiredRoutes,
    routeRolloverPlan: pendingRoutes.map((route) => ({
      route: route.route,
      endpoint: route.endpoint,
      viewResources: route.viewResources,
      apiResources: route.apiResources,
      runtimeFields: route.runtimeFields,
      apiNeeds: route.apiNeeds,
      frontendAcceptance: [
        'response shape validates through the Panda resources BFF validation probe',
        'page continues consuming camelCase Panda view models',
        'route contract can move from mock-ready to api-wired',
        'strict report pending route count decreases without changing high-risk backend policy',
      ],
    })),
    currentApiWiredRoutes: apiWiredRoutes.map((route) => ({
      route: route.route,
      endpoint: route.endpoint,
      resources: route.viewResources,
    })),
  }
}

export function getPandaExpectedStrictFailure({ pendingRoutes, resourcesFlag, resourcesFlagDefault }) {
  const strictFailures = getPandaStrictFailures({ pendingRoutes, resourcesFlag, resourcesFlagDefault })
  if (strictFailures.length > 0) {
    return `${pendingRoutes.length} mock-ready routes and ${resourcesFlag}=${resourcesFlagDefault}`
  }
  return 'none'
}

export function getPandaStrictFailures({ pendingRoutes, resourcesFlag, resourcesFlagDefault }) {
  const strictFailures = []
  if (pendingRoutes.length > 0) {
    strictFailures.push(
      `${pendingRoutes.length} Panda routes are still mock-ready: ${pendingRoutes.map((route) => route.route).join(', ')}`,
    )
  }
  if (resourcesFlagDefault !== 'true') {
    strictFailures.push(`${resourcesFlag} default is still ${resourcesFlagDefault}`)
  }
  return strictFailures
}
