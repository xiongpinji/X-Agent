import { Bot, Globe2, Send, ShieldCheck, Wrench } from 'lucide-react'

export type TaskComposerProps = {
  value: string
  onChange: (value: string) => void
}

export function TaskComposer({ value, onChange }: TaskComposerProps) {
  return (
    <div className="panda-card panda-composer">
      <textarea
        aria-label="输入任务"
        placeholder="输入任务，@智能体，或粘贴代码/文档..."
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
      <div className="panda-composer-actions">
        <div className="panda-pill-row">
          <button className="panda-pill" type="button"><Bot size={15} />Panda Agent-4</button>
          <button className="panda-pill" type="button"><Globe2 size={15} />联网</button>
          <button className="panda-pill" type="button"><Wrench size={15} />MCP 工具</button>
          <button className="panda-pill" type="button"><ShieldCheck size={15} />人审策略</button>
        </div>
        <button className="panda-send-button" type="button" aria-label="启动任务"><Send size={18} /></button>
      </div>
    </div>
  )
}
