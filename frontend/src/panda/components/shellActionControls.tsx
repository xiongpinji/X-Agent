import { Bell, ChevronDown, Plus } from 'lucide-react'
import { pandaLogoSrc } from '../data/navigation'

export function TopBarActions() {
  return (
    <div className="panda-toolbar">
      <button className="panda-command-button" type="button"><Plus size={17} aria-hidden="true" />新建</button>
      <button className="panda-icon-button" type="button" aria-label="通知"><Bell size={18} /></button>
      <div className="panda-user-chip" role="group" aria-label="当前用户 Panda Agent，超级管理员">
        <img className="panda-avatar" src={pandaLogoSrc} alt="Panda Agent" />
        <div className="min-w-0">
          <div className="truncate text-sm font-medium">Panda Agent</div>
          <div className="truncate text-xs text-slate-400">超级管理员</div>
        </div>
        <ChevronDown size={16} aria-hidden="true" />
      </div>
    </div>
  )
}
