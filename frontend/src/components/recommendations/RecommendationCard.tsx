import { ArrowRight, ShieldAlert, Sparkles } from 'lucide-react'
import type { Recommendation } from '../../api'
import { n } from '../../lib/format'

export function RecommendationCard({ r }: { r: Recommendation }) {
  return (
    <article className="recommendation-card">
      <div className="recommendation-icon">
        <Sparkles size={18} />
      </div>
      <div className="recommendation-content">
        <div className="recommendation-title">
          <h3>{r.package_name || 'Package update'}</h3>
          <span className="version-code">{String(r.installed_version || 'current version')}</span>
          <ArrowRight size={14} />
          <span className="fix-version">
            {r.fixed_versions?.length ? r.fixed_versions.join(', ') : 'No fixed version listed'}
          </span>
        </div>
        <p>
          {String(
            r.recommendation ||
              'Review the advisory and update to a patched version if a compatible release is available.',
          )}
        </p>
        <div className="recommendation-meta">
          <span>
            <ShieldAlert size={13} />
            {n(r.vulnerability_ids?.length || 0)} linked advisories
          </span>
          {r.package_id && <span className="mono">{r.package_id}</span>}
        </div>
      </div>
    </article>
  )
}
