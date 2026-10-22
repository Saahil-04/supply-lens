import { Boxes, GitBranch, Package, ShieldAlert } from 'lucide-react'
import type { Analysis } from '../../api'
import { n } from '../../lib/format'
import { Metric } from './Metric'

export function MetricGrid({ analysis }: { analysis: Analysis }) {
  const summary = analysis.summary || {}
  return (
    <>
      <div className="section-title-row">
        <div>
          <h3>Inventory at a glance</h3>
          <p>Counts reflect this repository snapshot.</p>
        </div>
        <span className="muted-caption">SCAN SUMMARY</span>
      </div>

      <div className="metric-grid">
        <Metric
          icon={<Boxes size={18} />}
          label="Projects discovered"
          value={summary.projects_discovered}
          sub="Manifest-based projects"
          tone="blue"
        />
        <Metric
          icon={<Package size={18} />}
          label="Packages inventoried"
          value={summary.total_packages}
          sub={`${n(summary.direct_packages)} direct · ${n(summary.transitive_packages)} transitive`}
          tone="violet"
        />
        <Metric
          icon={<ShieldAlert size={18} />}
          label="Vulnerability findings"
          value={summary.vulnerabilities_found}
          sub={`${n(summary.unique_advisories_found)} unique advisories`}
          tone="red"
        />
        <Metric
          icon={<GitBranch size={18} />}
          label="Dependency edges"
          value={summary.dependency_edges}
          sub="Resolved relationships"
          tone="teal"
        />
      </div>
    </>
  )
}
