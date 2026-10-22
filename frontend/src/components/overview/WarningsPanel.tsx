import { AlertTriangle } from 'lucide-react'
import type { Analysis } from '../../api'

export function WarningsPanel({ analysis }: { analysis: Analysis }) {
  const warningList = Array.isArray(analysis.analysis_metadata?.warnings)
    ? (analysis.analysis_metadata.warnings as Array<string | { message?: string }>)
    : []

  if (warningList.length === 0) return null

  return (
    <section className="panel warning-panel">
      <div className="panel-heading">
        <div className="warning-heading">
          <AlertTriangle size={18} />
          <div>
            <h3>Coverage warnings</h3>
            <p>Resolve these to improve confidence in the results.</p>
          </div>
        </div>
        <span className="warning-count">
          {warningList.length} {warningList.length === 1 ? 'warning' : 'warnings'}
        </span>
      </div>
      <ul className="warning-list">
        {warningList.map((w, i) => (
          <li key={i}>{typeof w === 'string' ? w : w.message || JSON.stringify(w)}</li>
        ))}
      </ul>
    </section>
  )
}
