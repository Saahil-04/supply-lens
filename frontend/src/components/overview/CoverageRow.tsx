import { n } from '../../lib/format'

export function CoverageRow({ label, value, total }: { label: string; value: unknown; total?: unknown }) {
  const number = typeof value === 'number' ? value : 0
  const denom = typeof total === 'number' && total > 0 ? total : number
  const pct = denom > 0 ? Math.min(100, (number / denom) * 100) : 0
  return (
    <div className="coverage-row">
      <div className="coverage-label">
        <span>{label}</span>
        <b>
          {n(value)}
          {typeof total === 'number' ? ` / ${n(total)}` : ''}
        </b>
      </div>
      <div className="progress-track">
        <div className="progress-value" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}
