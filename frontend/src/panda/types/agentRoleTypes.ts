import type { StatusTone } from './runtimeTypes'

export type AgentRoleIcon =
  | 'briefcase'
  | 'palette'
  | 'code'
  | 'finance'
  | 'camera'
  | 'pen'
  | 'cart'
  | 'scale'
  | 'megaphone'
  | 'headset'

export type AgentRolePreset = {
  readonly id: string
  readonly name: string
  readonly tagline: string
  readonly description: string
  readonly abilities: readonly string[]
  readonly tools: readonly string[]
  readonly defaultPermissions: readonly string[]
  readonly icon: AgentRoleIcon
  readonly portraitSrc: string
  readonly tone: StatusTone
}
