import { InsetInfoBlock } from './common'
import { moduleDeliverySurfaceItems } from './moduleDeliverySurfaceViewModel'

export function ModuleDeliverySurface() {
  return (
    <section className="panda-card p-4">
      <h2 className="font-semibold">模块交付面</h2>
      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {moduleDeliverySurfaceItems.map((item) => (
          <InsetInfoBlock key={item.label}>
            <div className="text-sm font-medium">{item.label}</div>
            <div className="mt-2 text-xs leading-5 text-slate-400">{item.description}</div>
          </InsetInfoBlock>
        ))}
      </div>
    </section>
  )
}
