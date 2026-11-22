import { AlertTriangle, ChevronDown, Info } from 'lucide-react'
import { diagnosticsOf, type Analysis, type Diagnostic } from '../../api'
import { pluralize } from '../../lib/format'
import { Panel } from '../ui/Panel'

function DiagnosticList({ items }: { items: Diagnostic[] }) {
  return (
    <ul className="diagnostic-list">
      {items.map((item, index) => (
        <li key={`${item.code}-${index}`}>
          <p>{item.message}</p>
          {item.hint && <p className="diagnostic-hint">{item.hint}</p>}
          <code>
            {item.code}
            {item.path ? ` · ${item.path}` : ''}
          </code>
        </li>
      ))}
    </ul>
  )
}

/** Coverage warnings (important) and informational notes (collapsed) reported by the analysis. */
export function DiagnosticsPanel({ analysis }: { analysis: Analysis }) {
  const diagnostics = diagnosticsOf(analysis)
  const legacyWarnings = analysis.analysis_metadata?.warnings

  // Older responses carry plain warning strings instead of structured diagnostics.
  const warnings: Diagnostic[] = diagnostics.length
    ? diagnostics.filter((d) => d.severity !== 'info')
    : (Array.isArray(legacyWarnings) ? (legacyWarnings as Array<string | { message?: string }>) : []).map(
        (warning, index) => ({
          code: `WARNING_${index + 1}`,
          severity: 'warning',
          message: typeof warning === 'string' ? warning : (warning.message ?? JSON.stringify(warning)),
        }),
      )
  const notes = diagnostics.filter((d) => d.severity === 'info')

  if (!warnings.length && !notes.length) return null

  return (
    <>
      {warnings.length > 0 && (
        <Panel
          className="panel-warning"
          title={pluralize(warnings.length, 'coverage warning')}
          description="These limit how complete the results are. Resolving them improves confidence."
          action={<AlertTriangle size={18} className="panel-warning-icon" aria-hidden="true" />}
        >
          <DiagnosticList items={warnings} />
        </Panel>
      )}
      {notes.length > 0 && (
        <details className="panel disclosure">
          <summary>
            <Info size={15} aria-hidden="true" />
            {pluralize(notes.length, 'informational note')}
            <ChevronDown size={15} className="disclosure-chevron" aria-hidden="true" />
          </summary>
          <div className="panel-body">
            <DiagnosticList items={notes} />
          </div>
        </details>
      )}
    </>
  )
}
