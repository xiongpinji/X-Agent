import { InsetInfoBlock } from './common'

export function ModuleDeliverySurface() {
  return (
    <section className="panda-card p-4">
      <h2 className="font-semibold">模块交付面</h2>
      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {['总览', '管理', '详情', '历史/审计'].map((item) => (
          <InsetInfoBlock key={item}>
            <div className="text-sm font-medium">{item}</div>
            <div className="mt-2 text-xs leading-5 text-slate-400">支持加载、错误、空状态和权限状态。</div>
          </InsetInfoBlock>
        ))}
      </div>
    </section>
  )
}
