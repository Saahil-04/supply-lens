import { ArrowRight, Info } from 'lucide-react'
import { summaryExtras, type Analysis, type PriorityCounts } from '../../api'
import { PRIORITY_LABEL, REACHABILITY_LABEL, UNKNOWN_REASON, n } from '../../lib/format'
import type { Tab } from '../../lib/tabs'

const LEVELS: Array<keyof PriorityCounts> = ['P1', 'P2', 'P3', 'P4']

/** Severity-only ranking next to the context-aware ranking, so the effect of reachability is visible. */
export function PriorityPanel({ analysis, onNavigate }: { analysis: Analysis; onNavigate: (tab: Tab) => void }) {
  const extras = summaryExtras(analysis)
  const after = extras.priority_counts
  const before = extras.baseline_priority_counts
  if (!after || !before) return null

  const meta = analysis.analysis_metadata?.reachability as
    | { enabled?: boolean; unknown_reasons?: Record<string, number>; files_scanned?: number; max_files?: number; projects_truncated?: number; method?: string }
    | undefined
  const enabled = !!meta?.enabled
  const statusCounts = extras.reachability || {}
  const total = LEVELS.reduce((sum, l) => sum + (after[l] || 0), 0)

  return (
    <section className="panel priority-panel">
      <div className="panel-heading">
        <div>
          <h3>Remediation priority</h3>
          <p>
            {enabled
              ? 'Severity alone vs. severity adjusted for whether the package is actually used'
              : 'Reachability was not checked, so priority follows severity only'}
          </p>
        </div>
      </div>

      {total > 0 && (
        <table className="priority-table">
          <thead>
            <tr>
              <th></th>
              <th>Severity only</th>
              <th>Context-aware</th>
            </tr>
          </thead>
          <tbody>
            {LEVELS.map((level, i) => (
              <tr key={level}>
                <td>
                  <span className={`priority-badge priority-${i + 1}`}>
                    {level} · {PRIORITY_LABEL[i + 1]}
                  </span>
                </td>
                <td>{n(before[level])}</td>
                <td>
                  <b>{n(after[level])}</b>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {enabled && Object.keys(statusCounts).length > 0 && (
        <div className="reach-breakdown">
          {Object.entries(statusCounts).map(([status, count]) => (
            <span key={status} className="pill pill-neutral">
              {REACHABILITY_LABEL[status] || status}: {n(count)}
            </span>
          ))}
        </div>
      )}

      {enabled && meta?.unknown_reasons && Object.keys(meta.unknown_reasons).length > 0 && (
        <ul className="unknown-reasons">
          {Object.entries(meta.unknown_reasons).map(([reason, count]) => (
            <li key={reason}>
              <b>{n(count)}</b> unknown: {UNKNOWN_REASON[reason] || reason}
            </li>
          ))}
        </ul>
      )}
      <div className="advisory-note">
        <Info size={16} />
        <span>
          {enabled
            ? `Method: package-level import scan (${n(meta?.files_scanned)} source files read), not function-level analysis. A lowered priority means “no evidence of use found”, not “safe”. Unknown never lowers priority.`
            : 'Run a new scan with the reachability option enabled to see context-aware priorities.'}
        </span>
      </div>
      <button className="button button-secondary full-width" onClick={() => onNavigate('Vulnerabilities')}>
        Review prioritized findings <ArrowRight size={15} />
      </button>
    </section>
  )
}
