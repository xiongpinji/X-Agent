import type { ModulePageAction } from '../components/common'

export function moduleActions(
  secondaryLabel: string,
  secondaryIcon: ModulePageAction['icon'],
  primaryLabel: string,
  primaryIcon: ModulePageAction['icon'],
): readonly ModulePageAction[] {
  return [
    { label: secondaryLabel, icon: secondaryIcon },
    { label: primaryLabel, icon: primaryIcon, primary: true },
  ]
}
