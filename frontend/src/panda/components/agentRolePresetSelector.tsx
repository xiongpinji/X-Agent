import { useState } from 'react'
import { agentRolePresets } from '../data/agentRolePresets'
import { AgentRolePresetCard, AgentRolePresetDetail } from './agentRolePresetCards'

export { AgentRolePresetCard, AgentRolePresetDetail } from './agentRolePresetCards'

export function AgentRolePresetSelector() {
  const [selectedPresetId, setSelectedPresetId] = useState(agentRolePresets[0]?.id ?? '')
  const selectedPreset = agentRolePresets.find((preset) => preset.id === selectedPresetId) ?? agentRolePresets[0]

  return (
    <section className="panda-card panda-role-presets">
      <div className="panda-role-presets-heading">
        <div>
          <h2>创建智能体</h2>
          <p>选择内置角色卡，自动带入能力、工具和默认权限边界。</p>
        </div>
        <button className="panda-state-action" type="button">使用所选角色</button>
      </div>
      <div className="panda-role-presets-layout">
        <div className="panda-role-card-grid">
          {agentRolePresets.map((preset) => (
            <AgentRolePresetCard
              key={preset.id}
              preset={preset}
              selected={preset.id === selectedPreset.id}
              onSelect={() => setSelectedPresetId(preset.id)}
            />
          ))}
        </div>
        <AgentRolePresetDetail preset={selectedPreset} />
      </div>
    </section>
  )
}
