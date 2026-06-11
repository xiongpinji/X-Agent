import { Cloud, KeyRound, Plus, Users } from 'lucide-react'
import { pandaLogoSrc } from '../data/navigation'

export { TopBarActions } from './shellActionControls'

export function WorkspaceSwitcher() {
  return (
    <section className="panda-workspace-switcher">
      <div className="mb-3 flex items-center justify-between text-sm text-slate-400">
        <span>团队空间</span>
        <Plus size={16} aria-hidden="true" />
      </div>
      <div className="rounded-lg bg-white/[0.055] p-3">
        <div className="flex items-center gap-3">
          <img className="panda-avatar h-8 w-8" src={pandaLogoSrc} alt="Panda Agent 团队" />
          <div className="min-w-0">
            <div className="truncate text-sm font-medium">Panda Agent 团队</div>
            <div className="text-xs text-slate-400">企业版</div>
          </div>
        </div>
      </div>
      <div className="mt-4 space-y-3 text-sm text-slate-400">
        <div className="flex items-center gap-2"><Users size={15} aria-hidden="true" />个人空间</div>
        <div className="flex items-center gap-2"><Cloud size={15} aria-hidden="true" />云端任务</div>
        <div className="flex items-center gap-2"><KeyRound size={15} aria-hidden="true" />权限与密钥</div>
      </div>
    </section>
  )
}
