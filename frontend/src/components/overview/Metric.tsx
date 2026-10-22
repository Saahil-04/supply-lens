import type { ReactNode } from 'react'
import { n } from '../../lib/format'

export function Metric({
  icon,
  label,
  value,
  sub,
  tone,
}: {
  icon: ReactNode
  label: string
  value: unknown
  sub: string
  tone: string
}) {
  return (
    <div className="metric-card">
      <div className={`metric-icon tone-${tone}`}>{icon}</div>
      <div className="metric-label">{label}</div>
      <div className="metric-value">{n(value)}</div>
      <div className="metric-sub">{sub}</div>
    </div>
  )
}
