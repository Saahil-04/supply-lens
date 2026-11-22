import type { ReactNode } from 'react'
import { formatNumber } from '../../lib/format'

export function PageHeader({
  title,
  description,
  total,
  actions,
}: {
  title: string
  description?: string
  /** Shown as a count next to the title when known. */
  total?: number
  actions?: ReactNode
}) {
  return (
    <header className="page-header">
      <div>
        <h1 className="page-title">
          {title}
          {total !== undefined && <span className="count-chip">{formatNumber(total)}</span>}
        </h1>
        {description && <p className="page-description">{description}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  )
}
