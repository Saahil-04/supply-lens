import { AlertTriangle, Info } from 'lucide-react'
import { diagnosticsOf, type Analysis, type Diagnostic } from '../../api'

function DiagnosticItem({ d }: { d: Diagnostic }) {
  return (
    <li>
      <span>{d.message}</span>
      {d.hint && <div className="diag-hint">{d.hint}</div>}
      <div className="diag-code">
        {d.code}
        {d.path ? ` · ${d.path}` : ''}
      </div>
    </li>
  )
}

export function WarningsPanel({ analysis }: { analysis: Analysis }) {
  const diagnostics = diagnosticsOf(analysis)
  const legacy = Array.isArray(analysis.analysis_metadata?.warnings)
    ? (analysis.analysis_metadata.warnings as Array<string | { message?: string }>)
    : []

  // Older backend responses only carry plain warning strings.
  const important: Diagnostic[] = diagnostics.length
    ? diagnostics.filter((d) => d.severity !== 'info')
    : legacy.map((w, i) => ({ code: `WARNING_${i + 1}`, severity: 'warning', message: typeof w === 'string' ? w : w.message || JSON.stringify(w) }))
  const notes = diagnostics.filter((d) => d.severity === 'info')

  if (important.length === 0 && notes.length === 0) return null

  return (
    <>
      {important.length > 0 && (
        <section className="panel warning-panel">
          <div className="panel-heading">
            <div className="warning-heading">
              <AlertTriangle size={18} />
              <div>
                <h3>Coverage warnings</h3>
                <p>These limit how complete the results are. Resolve them to improve confidence.</p>
              </div>
            </div>
            <span className="warning-count">
              {important.length} {important.length === 1 ? 'warning' : 'warnings'}
            </span>
          </div>
          <ul className="warning-list">
            {important.map((d, i) => (
              <DiagnosticItem key={`${d.code}-${i}`} d={d} />
            ))}
          </ul>
        </section>
      )}
      {notes.length > 0 && (
        <details className="panel notes-panel">
          <summary>
            <Info size={14} /> {notes.length} informational {notes.length === 1 ? 'note' : 'notes'}
          </summary>
          <ul className="warning-list">
            {notes.map((d, i) => (
              <DiagnosticItem key={`${d.code}-${i}`} d={d} />
            ))}
          </ul>
        </details>
      )}
    </>
  )
}
