import { ArrowRight, ShieldAlert } from 'lucide-react'
import type { Recommendation } from '../../api'
import { pluralize } from '../../lib/format'
import { PriorityBadge } from '../ui/Badge'

const FALLBACK_TEXT = 'Review the advisory and update to a patched version if a compatible release is available.'

export function RecommendationCard({ recommendation: r }: { recommendation: Recommendation }) {
  const fixes = r.fixed_versions ?? []
  return (
    <article className="recommendation-card">
      <header className="recommendation-header">
        <h3>{r.package_name || 'Package update'}</h3>
        <PriorityBadge priority={r.priority} />
      </header>

      <div className="upgrade-path">
        <code className="version">{r.installed_version || 'Current version'}</code>
        <ArrowRight size={14} aria-hidden="true" />
        {fixes.length ? (
          fixes.map((version) => (
            <code key={version} className="version version-fix">
              {version}
            </code>
          ))
        ) : (
          <span className="muted">No fixed version listed</span>
        )}
      </div>

      <p className="recommendation-text">{r.recommendation || FALLBACK_TEXT}</p>

      <footer className="recommendation-meta">
        <span>
          <ShieldAlert size={13} aria-hidden="true" /> {pluralize(r.vulnerability_ids?.length ?? 0, 'linked advisory', 'linked advisories')}
        </span>
        {r.package_id && <span className="mono truncate">{r.package_id}</span>}
      </footer>
    </article>
  )
}
