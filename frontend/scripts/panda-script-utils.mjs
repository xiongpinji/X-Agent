import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { execFileSync } from 'node:child_process'
import http from 'node:http'

export const pandaScriptRoot = process.cwd()

export function assert(condition, message) {
  if (!condition) {
    throw new Error(message)
  }
}

export function read(relativePath) {
  return readFileSync(resolve(pandaScriptRoot, relativePath), 'utf8')
}

export function readJson(relativePath) {
  return JSON.parse(read(relativePath))
}

export function unique(values) {
  return [...new Set(values)]
}

export function sameMembers(left, right) {
  return left.length === right.length && left.every((item) => right.includes(item))
}

export function extractResourceKeyPairs(source) {
  const body = source.match(/export const pandaResourceKeyPairs = \[([\s\S]*?)\] as const/)?.[1] ?? ''
  return [...body.matchAll(/\['([^']+)', '([^']+)'\]/g)].map((match) => ({
    viewKey: match[1],
    apiKey: match[2],
  }))
}

export function buildResourceKeyBoundary(source) {
  const pairs = extractResourceKeyPairs(source)
  return {
    keyMap: 'src/panda/api/resourceKeys.ts',
    viewKeys: pairs.map((pair) => pair.viewKey),
    apiKeys: pairs.map((pair) => pair.apiKey),
    pairs,
  }
}

export function buildRouteApiResourcesEvidence({ routeRollover, resourceKeyBoundary }) {
  const routeApiResources = unique(routeRollover.routes.flatMap((route) => route.apiResources))
  const unknownRouteApiResources = routeApiResources.filter((apiKey) => !resourceKeyBoundary.apiKeys.includes(apiKey))
  const missingRouteApiResources = resourceKeyBoundary.apiKeys.filter((apiKey) => !routeApiResources.includes(apiKey))

  return {
    status: unknownRouteApiResources.length === 0 && missingRouteApiResources.length === 0 ? 'passed' : 'failed',
    routePlan: routeRollover.sourceScript,
    keyMap: resourceKeyBoundary.keyMap,
    routeApiResources,
    boundaryApiResources: resourceKeyBoundary.apiKeys,
    unknownRouteApiResources,
    missingRouteApiResources,
    diff: {
      unknownRouteApiResources,
      missingRouteApiResources,
    },
    expectedAlignment: 'Every routes[].apiResources entry in the alignment report must be resolved from src/panda/api/resourceKeys.ts, stay inside the backend API resource boundary, and expose unknown/missing key diffs for backend handoff.',
  }
}

export function buildPendingRouteSignature(route) {
  return [
    route.route,
    route.endpoint,
    route.resources,
    route.apiResources,
    route.runtimeFields,
    route.apiNeeds,
  ].join('|')
}

export function extractApiResourcesFromPendingRouteSignatures(signatures) {
  return unique(
    signatures.flatMap((signature) => {
      const apiResources = signature.split('|')[3] ?? ''
      return apiResources
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean)
    }),
  )
}

export function requestStatus(url) {
  return new Promise((resolveRequest) => {
    const req = http.get(url, (res) => {
      res.resume()
      resolveRequest(res.statusCode ?? 0)
    })
    req.on('error', () => resolveRequest(0))
    req.setTimeout(2500, () => {
      req.destroy()
      resolveRequest(0)
    })
  })
}

export function runNodeJson(scriptPath, args = []) {
  const output = execFileSync(process.execPath, [resolve(pandaScriptRoot, scriptPath), ...args], {
    cwd: pandaScriptRoot,
    encoding: 'utf8',
  })
  return JSON.parse(output)
}
