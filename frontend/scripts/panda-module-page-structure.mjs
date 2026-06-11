import {
  pandaModulePageResourceHookByPage,
  pandaModulePageResourceTypeByPage,
} from './panda-workbench-verify-config.mjs'

export const PANDA_MODULE_PAGE_STRUCTURE = {
  sourceScript: 'frontend/scripts/panda-module-page-structure.mjs',
  content: 'frontend/src/panda/data/modulePageContent.tsx',
  shell: 'frontend/src/panda/components/modulePagePrimitives.tsx',
  resources: 'frontend/src/panda/state/useModulePageResources.ts',
  standardPages: Object.keys(pandaModulePageResourceHookByPage),
  directSelectorExceptions: ['home', 'threads', 'right-rail'],
  rule:
    'Standard module pages consume Panda view models through focused page resource hooks; home, threads, and right rail keep direct selectors for custom layouts.',
}

export function getPandaModulePageStructure() {
  return {
    ...PANDA_MODULE_PAGE_STRUCTURE,
    standardPages: [...PANDA_MODULE_PAGE_STRUCTURE.standardPages],
    directSelectorExceptions: [...PANDA_MODULE_PAGE_STRUCTURE.directSelectorExceptions],
    resourceHooks: Object.entries(pandaModulePageResourceHookByPage).map(([page, hook]) => ({
      page,
      hook,
      resourceType: pandaModulePageResourceTypeByPage[page],
      source: PANDA_MODULE_PAGE_STRUCTURE.resources,
    })),
    resourceTypes: Object.entries(pandaModulePageResourceTypeByPage).map(([page, resourceType]) => ({
      page,
      resourceType,
      source: PANDA_MODULE_PAGE_STRUCTURE.resources,
    })),
  }
}
