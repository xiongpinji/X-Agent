import { pandaLogoSrc } from '../data/navigation'

export { TopBarActions, WorkspaceSwitcher } from './shellControls'

export function BrandLockup() {
  return (
    <div className="panda-brand">
      <img className="panda-logo" src={pandaLogoSrc} alt="Panda Agent logo" />
      <div>
        <div className="panda-brand-title">Panda Agent</div>
        <div className="panda-brand-subtitle">熊猫派达智能体应用管理平台</div>
      </div>
    </div>
  )
}
