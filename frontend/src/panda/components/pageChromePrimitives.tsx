import React from 'react'
import type { PandaPage } from '../types'
import { PageContractStrip } from './pageContractPrimitives'

export function PageHeading({
  title,
  description,
  page,
  actions,
}: {
  title: string
  description: string
  page?: PandaPage
  actions?: React.ReactNode
}) {
  return (
    <>
      <section className="panda-page-heading">
        <div>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
        {actions ? <div className="panda-page-actions">{actions}</div> : null}
      </section>
      {page ? <PageContractStrip page={page} /> : null}
    </>
  )
}

export function PageActionButton({
  icon,
  children,
  primary = false,
}: {
  icon: React.ReactElement<{ size?: number; 'aria-hidden'?: string }>
  children: React.ReactNode
  primary?: boolean
}) {
  return (
    <button className={`panda-command-button ${primary ? 'panda-command-primary' : ''}`} type="button">
      {React.cloneElement(icon, { size: icon.props.size ?? 16, 'aria-hidden': 'true' })}
      {children}
    </button>
  )
}
