import type { ReactNode } from 'react'
import { n } from '../../lib/format'

export function ResourceHeader({
  eyebrow,
  title,
  body,
  total,
  action,
}: {
  eyebrow: string
  title: string
  body: string
  total?: number
  action?: ReactNode
}) {
  return (
    <div className="page-heading resource-heading">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{body}</p>
      </div>
      <div className="resource-heading-right">
        {total !== undefined && <span className="total-badge">{n(total)} total</span>}
        {action}
      </div>
    </div>
  )
}
