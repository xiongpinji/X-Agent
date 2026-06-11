import {
  cleanupPandaTsProbeTempDir,
  createPandaTsProbeTempDir,
  importProbeModule,
  rewriteProbeImports,
  transpilePandaTsFile,
} from './panda-ts-probe-utils.mjs'

const outputJson = process.argv.includes('--json')

function loadResourceValidationModule() {
  const tempDir = createPandaTsProbeTempDir('panda-resource-validation-probe')

  for (const fileName of ['resourceKeys.ts', 'resourcesValidation.ts']) {
    transpilePandaTsFile(tempDir, `src/panda/api/${fileName}`, fileName.replace(/\.ts$/, '.mjs'))
  }

  rewriteProbeImports(tempDir, 'resourcesValidation.mjs', [
    [/from ['"]\.\/resourceKeys['"]/g, "from './resourceKeys.mjs'"],
  ])

  return importProbeModule(tempDir, 'resourcesValidation.mjs').finally(() => {
    cleanupPandaTsProbeTempDir(tempDir)
  })
}

function expectPass(name, run) {
  try {
    run()
    return { name, status: 'passed' }
  } catch (error) {
    return {
      name,
      status: 'failed',
      error: error instanceof Error ? error.message : String(error),
    }
  }
}

function expectValidationError(name, ValidationError, run) {
  try {
    run()
    return {
      name,
      status: 'failed',
      error: 'Expected PandaResourceValidationError, but validation passed.',
    }
  } catch (error) {
    return {
      name,
      status: error instanceof ValidationError ? 'passed' : 'failed',
      error: error instanceof Error ? error.message : String(error),
    }
  }
}

const validationModule = await loadResourceValidationModule()
const {
  PandaResourceValidationError,
  pandaResourceValidationKeys,
  validatePandaResourceSnapshot,
} = validationModule

const validSnapshot = Object.fromEntries(pandaResourceValidationKeys.map((key) => [key, []]))
const checks = [
  expectPass('valid-array-fields', () => {
    const validated = validatePandaResourceSnapshot(validSnapshot)
    if (validated !== validSnapshot) {
      throw new Error('Validator should return the original validated snapshot reference.')
    }
  }),
  expectPass('partial-snapshot', () => {
    validatePandaResourceSnapshot({ tasks: [], projects: [] })
  }),
  expectValidationError('non-object-root', PandaResourceValidationError, () => {
    validatePandaResourceSnapshot(null)
  }),
  expectValidationError('array-root', PandaResourceValidationError, () => {
    validatePandaResourceSnapshot([])
  }),
  expectValidationError('non-array-resource-field', PandaResourceValidationError, () => {
    validatePandaResourceSnapshot({ tasks: {} })
  }),
  expectValidationError('non-object-resource-item', PandaResourceValidationError, () => {
    validatePandaResourceSnapshot({ tasks: [null] })
  }),
  expectValidationError('unknown-resource-field', PandaResourceValidationError, () => {
    validatePandaResourceSnapshot({ taskz: [] })
  }),
]

const failedChecks = checks.filter((check) => check.status !== 'passed')
const result = {
  productName: 'Panda Agent',
  technicalCore: 'X-Agent Autonomous Framework',
  status: failedChecks.length === 0 ? 'passed' : 'failed',
  checkedAt: new Date().toISOString(),
  validation: 'src/panda/api/resourcesValidation.ts',
  validationKeys: pandaResourceValidationKeys,
  checks,
}

if (outputJson) {
  console.log(JSON.stringify(result, null, 2))
} else {
  console.log(`Panda resources validation: ${result.status}`)
  console.log(`Validation source: ${result.validation}`)
  console.log(`Checks: ${checks.filter((check) => check.status === 'passed').length}/${checks.length} passed`)
  for (const check of failedChecks) {
    console.log(`- [failed] ${check.name}: ${check.error}`)
  }
}

if (process.env.PANDA_RESOURCE_VALIDATION_RESULT_PATH) {
  writeFileSync(process.env.PANDA_RESOURCE_VALIDATION_RESULT_PATH, `${JSON.stringify(result, null, 2)}\n`)
}

if (failedChecks.length > 0) {
  process.exit(1)
}
