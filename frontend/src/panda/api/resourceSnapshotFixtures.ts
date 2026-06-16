import { mapPandaResourceSnapshot, type ApiPandaResourceSnapshot } from './adapters'
import type { PandaResourceSnapshot } from './resourceSnapshotTypes'
import { PandaResourceValidationError, pandaResourceValidationKeys, validatePandaResourceSnapshot } from './resourcesValidation'
import { apiResourceSnapshotFixture } from './resourceAdapterFixtures'

export { apiResourceSnapshotFixture } from './resourceAdapterFixtures'
export { aggregateResourcesBffDryRunFixture } from './resourceDryRunFixtures'
export { workbenchActivityDryRunFixture } from './homeActivityFixtures'
export { runtimeFixture } from './resourceRuntimeFixtures'

export const resourceSnapshotAdapterFixture = mapPandaResourceSnapshot(apiResourceSnapshotFixture) satisfies PandaResourceSnapshot

export const validatedResourceSnapshotFixture = validatePandaResourceSnapshot(apiResourceSnapshotFixture) satisfies ApiPandaResourceSnapshot

export const pandaResourceValidationFixture = {
  keys: pandaResourceValidationKeys,
  error: new PandaResourceValidationError('fixture'),
}
