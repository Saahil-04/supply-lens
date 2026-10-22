import { ArrowRight, CircleHelp, FileCheck2 } from 'lucide-react'
import type { Analysis } from '../../api'
import type { Tab } from '../../lib/tabs'
import { CoverageRow } from './CoverageRow'

export function CoveragePanel({
  analysis,
  onNavigate,
}: {
  analysis: Analysis
  onNavigate: (tab: Tab) => void
}) {
  const summary = analysis.summary || {}
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h3>Analysis coverage</h3>
          <p>What this scan could resolve</p>
        </div>
        <FileCheck2 size={18} className="panel-heading-icon" />
      </div>
      <CoverageRow
        label="Projects with resolved graph"
        value={summary.projects_with_resolved_graph}
        total={summary.projects_discovered}
      />
      <CoverageRow label="Manifests found" value={summary.manifests_found} total={summary.projects_discovered} />
      <CoverageRow label="Lockfiles found" value={summary.lockfiles_found} />
      <div className="coverage-note">
        <CircleHelp size={15} />
        <span>Lockfiles without a matching manifest are not silently assigned to a project.</span>
      </div>
      <button className="button button-quiet full-width" onClick={() => onNavigate('Projects')}>
        Inspect projects <ArrowRight size={15} />
      </button>
    </section>
  )
}
