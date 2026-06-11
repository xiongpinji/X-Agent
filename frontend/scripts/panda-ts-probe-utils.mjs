import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import ts from 'typescript'
import { pandaScriptRoot } from './panda-script-utils.mjs'

export function createPandaTsProbeTempDir(prefix) {
  const tempDir = resolve(tmpdir(), `${prefix}-${Date.now()}-${process.pid}`)
  mkdirSync(tempDir, { recursive: true })
  return tempDir
}

export function transpilePandaTsFile(tempDir, relativePath, outputName = relativePath.split('/').at(-1).replace(/\.ts$/, '.mjs')) {
  const sourcePath = resolve(pandaScriptRoot, relativePath)
  const source = readFileSync(sourcePath, 'utf8')
  const transpiled = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2022,
      importsNotUsedAsValues: ts.ImportsNotUsedAsValues.Remove,
    },
    fileName: sourcePath,
  })
  writeFileSync(resolve(tempDir, outputName), transpiled.outputText)
}

export const pandaApiProbeFileNames = [
  'resourceKeys.ts',
  'runtimeMapping.ts',
  'homeApiContracts.ts',
  'executionApiContracts.ts',
  'organizationApiContracts.ts',
  'knowledgeApiContracts.ts',
  'governanceApiContracts.ts',
  'resourceApiContracts.ts',
  'snapshotApiContracts.ts',
  'apiContracts.ts',
  'agentRoleAdapters.ts',
  'homeAdapters.ts',
  'executionResourceAdapters.ts',
  'organizationResourceAdapters.ts',
  'knowledgeResourceAdapters.ts',
  'governanceResourceAdapters.ts',
  'resourceItemAdapters.ts',
  'resourceSnapshotAdapter.ts',
  'resourcesValidation.ts',
  'adapters.ts',
]

export function transpilePandaApiProbeFiles(tempDir, fileNames = pandaApiProbeFileNames) {
  for (const fileName of fileNames) {
    transpilePandaTsFile(tempDir, `src/panda/api/${fileName}`, fileName.replace(/\.ts$/, '.mjs'))
  }
}

export function rewriteProbeImports(tempDir, fileName, replacements) {
  const filePath = resolve(tempDir, fileName)
  if (!existsSync(filePath)) {
    return
  }
  let source = readFileSync(filePath, 'utf8')
  for (const [from, to] of replacements) {
    source = source.replaceAll(from, to)
  }
  writeFileSync(filePath, source)
}

export function rewritePandaApiProbeImports(tempDir) {
  rewriteProbeImports(tempDir, 'resourcesValidation.mjs', [
    [/from ['"]\.\/resourceKeys['"]/g, "from './resourceKeys.mjs'"],
  ])
  rewriteProbeImports(tempDir, 'adapters.mjs', [
    [/from ['"]\.\/runtimeMapping['"]/g, "from './runtimeMapping.mjs'"],
    [/from ['"]\.\/apiContracts['"]/g, "from './apiContracts.mjs'"],
    [/from ['"]\.\/agentRoleAdapters['"]/g, "from './agentRoleAdapters.mjs'"],
    [/from ['"]\.\/resourceKeys['"]/g, "from './resourceKeys.mjs'"],
    [/from ['"]\.\/homeAdapters['"]/g, "from './homeAdapters.mjs'"],
    [/from ['"]\.\/executionResourceAdapters['"]/g, "from './executionResourceAdapters.mjs'"],
    [/from ['"]\.\/organizationResourceAdapters['"]/g, "from './organizationResourceAdapters.mjs'"],
    [/from ['"]\.\/knowledgeResourceAdapters['"]/g, "from './knowledgeResourceAdapters.mjs'"],
    [/from ['"]\.\/governanceResourceAdapters['"]/g, "from './governanceResourceAdapters.mjs'"],
    [/from ['"]\.\/resourceItemAdapters['"]/g, "from './resourceItemAdapters.mjs'"],
    [/from ['"]\.\/resourceSnapshotAdapter['"]/g, "from './resourceSnapshotAdapter.mjs'"],
  ])
  rewriteProbeImports(tempDir, 'apiContracts.mjs', [
    [/from ['"]\.\/homeApiContracts['"]/g, "from './homeApiContracts.mjs'"],
    [/from ['"]\.\/resourceApiContracts['"]/g, "from './resourceApiContracts.mjs'"],
    [/from ['"]\.\/snapshotApiContracts['"]/g, "from './snapshotApiContracts.mjs'"],
  ])
  rewriteProbeImports(tempDir, 'homeApiContracts.mjs', [
    [/from ['"]\.\/runtimeMapping['"]/g, "from './runtimeMapping.mjs'"],
  ])
  rewriteProbeImports(tempDir, 'resourceApiContracts.mjs', [
    [/from ['"]\.\/runtimeMapping['"]/g, "from './runtimeMapping.mjs'"],
    [/from ['"]\.\/executionApiContracts['"]/g, "from './executionApiContracts.mjs'"],
    [/from ['"]\.\/organizationApiContracts['"]/g, "from './organizationApiContracts.mjs'"],
    [/from ['"]\.\/knowledgeApiContracts['"]/g, "from './knowledgeApiContracts.mjs'"],
    [/from ['"]\.\/governanceApiContracts['"]/g, "from './governanceApiContracts.mjs'"],
  ])
  rewriteProbeImports(tempDir, 'agentRoleAdapters.mjs', [
    [/from ['"]\.\.\/data\/agentRolePortraits['"]/g, "from './agentRolePortraits.mjs'"],
    [/from ['"]\.\/apiContracts['"]/g, "from './apiContracts.mjs'"],
    [/from ['"]\.\/runtimeMapping['"]/g, "from './runtimeMapping.mjs'"],
  ])
  writeFileSync(
    resolve(tempDir, 'agentRolePortraits.mjs'),
    "export function resolveAgentRolePortrait(key) { return `portrait:${key ?? 'ceo'}` }\n",
  )
  for (const fileName of [
    'executionApiContracts.mjs',
    'organizationApiContracts.mjs',
    'knowledgeApiContracts.mjs',
    'governanceApiContracts.mjs',
  ]) {
    rewriteProbeImports(tempDir, fileName, [
      [/from ['"]\.\/runtimeMapping['"]/g, "from './runtimeMapping.mjs'"],
    ])
  }
  rewriteProbeImports(tempDir, 'snapshotApiContracts.mjs', [
    [/from ['"]\.\/homeApiContracts['"]/g, "from './homeApiContracts.mjs'"],
    [/from ['"]\.\/resourceApiContracts['"]/g, "from './resourceApiContracts.mjs'"],
  ])
  rewriteProbeImports(tempDir, 'homeAdapters.mjs', [
    [/from ['"]\.\/runtimeMapping['"]/g, "from './runtimeMapping.mjs'"],
    [/from ['"]\.\/apiContracts['"]/g, "from './apiContracts.mjs'"],
  ])
  for (const fileName of [
    'executionResourceAdapters.mjs',
    'organizationResourceAdapters.mjs',
    'knowledgeResourceAdapters.mjs',
    'governanceResourceAdapters.mjs',
    'resourceItemAdapters.mjs',
  ]) {
    rewriteProbeImports(tempDir, fileName, [
      [/from ['"]\.\/runtimeMapping['"]/g, "from './runtimeMapping.mjs'"],
      [/from ['"]\.\/apiContracts['"]/g, "from './apiContracts.mjs'"],
      [/from ['"]\.\/executionResourceAdapters['"]/g, "from './executionResourceAdapters.mjs'"],
      [/from ['"]\.\/organizationResourceAdapters['"]/g, "from './organizationResourceAdapters.mjs'"],
      [/from ['"]\.\/knowledgeResourceAdapters['"]/g, "from './knowledgeResourceAdapters.mjs'"],
      [/from ['"]\.\/governanceResourceAdapters['"]/g, "from './governanceResourceAdapters.mjs'"],
    ])
  }
  rewriteProbeImports(tempDir, 'resourceSnapshotAdapter.mjs', [
    [/from ['"]\.\/apiContracts['"]/g, "from './apiContracts.mjs'"],
    [/from ['"]\.\/homeAdapters['"]/g, "from './homeAdapters.mjs'"],
    [/from ['"]\.\/resourceKeys['"]/g, "from './resourceKeys.mjs'"],
    [/from ['"]\.\/resourceItemAdapters['"]/g, "from './resourceItemAdapters.mjs'"],
  ])
}

export function importProbeModule(tempDir, fileName) {
  return import(pathToFileURL(resolve(tempDir, fileName)).href)
}

export function cleanupPandaTsProbeTempDir(tempDir) {
  rmSync(tempDir, { recursive: true, force: true })
}
