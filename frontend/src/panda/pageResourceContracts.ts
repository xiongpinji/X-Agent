import { pandaPageResourceContractCatalog } from './pageResourceContractCatalog'

export { pandaPageResourceContractCatalog } from './pageResourceContractCatalog'

export const pandaPageResourceContracts = pandaPageResourceContractCatalog

export const pandaResourceContractKeys = Object.values(pandaPageResourceContracts).flatMap(
  (contract) => contract.resourceKeys,
)
