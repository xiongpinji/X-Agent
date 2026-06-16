import ceoPortrait from '../assets/roles/direct-reference-ceo.png'
import designerPortrait from '../assets/roles/direct-reference-designer.png'
import engineerPortrait from '../assets/roles/direct-reference-engineer.png'
import financePortrait from '../assets/roles/direct-reference-finance.png'
import directorPortrait from '../assets/roles/direct-reference-director.png'
import screenwriterPortrait from '../assets/roles/direct-reference-screenwriter.png'
import procurementPortrait from '../assets/roles/direct-reference-procurement.png'
import legalPortrait from '../assets/roles/direct-reference-legal.png'
import mediaOperatorPortrait from '../assets/roles/direct-reference-media-operator.png'
import supportPortrait from '../assets/roles/direct-reference-support.png'

export type AgentRolePortraitKey =
  | 'ceo'
  | 'designer'
  | 'engineer'
  | 'finance'
  | 'director'
  | 'screenwriter'
  | 'procurement'
  | 'legal'
  | 'media-operator'
  | 'support'

export const agentRolePortraits = {
  ceo: ceoPortrait,
  designer: designerPortrait,
  engineer: engineerPortrait,
  finance: financePortrait,
  director: directorPortrait,
  screenwriter: screenwriterPortrait,
  procurement: procurementPortrait,
  legal: legalPortrait,
  'media-operator': mediaOperatorPortrait,
  support: supportPortrait,
} satisfies Record<AgentRolePortraitKey, string>

export function resolveAgentRolePortrait(key: string | undefined): string {
  return agentRolePortraits[(key ?? 'ceo') as AgentRolePortraitKey] ?? agentRolePortraits.ceo
}
