import type { LucideIcon } from 'lucide-react'
import { Boxes, GitBranch, Package, ShieldAlert } from 'lucide-react'
import type { Analysis } from '../../api'
import { formatNumber } from '../../lib/format'

type Stat = { icon: LucideIcon; tone: string; label: string; value: unknown; caption: string }

export function StatGrid({ analysis }: { analysis: Analysis }) {
  const s = analysis.summary
  const stats: Stat[] = [
    { icon: Boxes, tone: 'blue', label: 'Projects', value: s.projects_discovered, caption: 'Manifest-based projects' },
    {
      icon: Package,
      tone: 'violet',
      label: 'Packages',
      value: s.total_packages,
      caption: `${formatNumber(s.direct_packages)} direct · ${formatNumber(s.transitive_packages)} transitive`,
    },
    {
      icon: ShieldAlert,
      tone: 'red',
      label: 'Vulnerability findings',
      value: s.vulnerabilities_found,
      caption: `${formatNumber(s.unique_advisories_found)} unique advisories`,
    },
    { icon: GitBranch, tone: 'teal', label: 'Dependency edges', value: s.dependency_edges, caption: 'Resolved relationships' },
  ]

  return (
    <div className="stat-grid">
      {stats.map(({ icon: Icon, tone, label, value, caption }) => (
        <div key={label} className="stat-card">
          <span className={`stat-icon tone-${tone}`}>
            <Icon size={17} aria-hidden="true" />
          </span>
          <div className="stat-label">{label}</div>
          <div className="stat-value">{formatNumber(value)}</div>
          <div className="stat-caption">{caption}</div>
        </div>
      ))}
    </div>
  )
}
