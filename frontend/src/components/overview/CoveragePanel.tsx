import { ArrowRight } from 'lucide-react'
import type { Analysis } from '../../api'
import { formatNumber } from '../../lib/format'
import type { TabId } from '../../lib/tabs'
import { Panel } from '../ui/Panel'
import { ProgressBar } from '../ui/ProgressBar'

function CoverageRow({ label, value, total }: { label: string; value: unknown; total?: unknown }) {
  const count = typeof value === 'number' ? value : 0
  const hasTotal = typeof total === 'number'
  return (
    <div className="coverage-row">
      <div className="coverage-label">
        <span>{label}</span>
        <b>
          {formatNumber(value)}
          {hasTotal && <span className="muted"> / {formatNumber(total)}</span>}
        </b>
      </div>
      <ProgressBar value={count} max={hasTotal && total > 0 ? total : count} tone="success" />
    </div>
  )
}

export function CoveragePanel({ analysis, onNavigate }: { analysis: Analysis; onNavigate: (tab: TabId) => void }) {
  const { summary } = analysis
  return (
    <Panel title="Analysis coverage" description="What this analysis could resolve">
      <CoverageRow label="Projects with resolved graph" value={summary.projects_with_resolved_graph} total={summary.projects_discovered} />
      <CoverageRow label="Manifests found" value={summary.manifests_found} total={summary.projects_discovered} />
      <CoverageRow label="Lockfiles found" value={summary.lockfiles_found} />
      <p className="note">Lockfiles without a matching manifest are never silently assigned to a project.</p>
      <button type="button" className="btn btn-secondary btn-block" onClick={() => onNavigate('projects')}>
        Inspect projects <ArrowRight size={15} />
      </button>
    </Panel>
  )
}
