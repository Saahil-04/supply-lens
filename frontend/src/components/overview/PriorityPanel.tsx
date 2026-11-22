import { ArrowRight, Info } from 'lucide-react'
import { reachabilityMetadata, summaryExtras, type Analysis, type PriorityCounts } from '../../api'
import { PRIORITY, REACHABILITY, UNKNOWN_REASON, formatNumber } from '../../lib/format'
import type { TabId } from '../../lib/tabs'
import { Badge } from '../ui/Badge'
import { Panel } from '../ui/Panel'
import { ProgressBar } from '../ui/ProgressBar'

const LEVELS: Array<keyof PriorityCounts> = ['P1', 'P2', 'P3', 'P4']

/** Severity-only ranking beside the context-aware ranking, so the effect of reachability is visible. */
export function PriorityPanel({ analysis, onNavigate }: { analysis: Analysis; onNavigate: (tab: TabId) => void }) {
  const extras = summaryExtras(analysis)
  const after = extras.priority_counts
  const before = extras.baseline_priority_counts
  if (!after || !before) return null

  const meta = reachabilityMetadata(analysis)
  const enabled = !!meta?.enabled
  const usage = Object.entries(extras.reachability ?? {})
  const unknownReasons = Object.entries(meta?.unknown_reasons ?? {})
  const total = LEVELS.reduce((sum, level) => sum + (after[level] || 0), 0)
  const largest = Math.max(1, ...LEVELS.map((level) => Math.max(after[level] || 0, before[level] || 0)))

  return (
    <Panel
      title="Remediation priority"
      description={
        enabled
          ? 'Severity alone, compared with severity adjusted for whether each package is actually used'
          : 'Reachability was not checked, so priority follows severity only'
      }
    >
      {total > 0 && (
        <table className="priority-table">
          <thead>
            <tr>
              <th scope="col">Priority</th>
              <th scope="col">Severity only</th>
              <th scope="col">Context-aware</th>
            </tr>
          </thead>
          <tbody>
            {LEVELS.map((level, index) => (
              <tr key={level}>
                <th scope="row">
                  <Badge tone={PRIORITY[index + 1].tone}>
                    {level} · {PRIORITY[index + 1].label}
                  </Badge>
                </th>
                <td className="num">{formatNumber(before[level])}</td>
                <td>
                  <div className="bar-cell">
                    <ProgressBar value={after[level] || 0} max={largest} tone={PRIORITY[index + 1].tone} />
                    <b className="num">{formatNumber(after[level])}</b>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {enabled && usage.length > 0 && (
        <div className="chip-row">
          {usage.map(([status, count]) => (
            <Badge key={status}>
              {REACHABILITY[status]?.label ?? status}: {formatNumber(count)}
            </Badge>
          ))}
        </div>
      )}

      {enabled && unknownReasons.length > 0 && (
        <ul className="bullet-list">
          {unknownReasons.map(([reason, count]) => (
            <li key={reason}>
              <b>{formatNumber(count)}</b> unknown: {UNKNOWN_REASON[reason] ?? reason}
            </li>
          ))}
        </ul>
      )}

      <p className="note note-icon">
        <Info size={15} aria-hidden="true" />
        <span>
          {enabled
            ? `Usage is detected at package level from import statements (${formatNumber(meta?.files_scanned)} source files read), not function level. A lowered priority means “no evidence of use found”, not “safe”. Unknown never lowers priority.`
            : 'Run a new analysis with the reachability check enabled to see context-aware priorities.'}
        </span>
      </p>

      <button type="button" className="btn btn-secondary" onClick={() => onNavigate('vulnerabilities')}>
        Review prioritized findings <ArrowRight size={15} />
      </button>
    </Panel>
  )
}
