import type { ComponentProps } from 'react'
import { FileJson, Network, ShieldAlert } from 'lucide-react'
import { AnalyzeForm } from './AnalyzeForm'

const FEATURES = [
  { icon: Network, title: 'Dependency inventory', body: 'Every package and lockfile relationship across your projects.' },
  { icon: ShieldAlert, title: 'Prioritized findings', body: 'Known OSV advisories, ranked by severity and real usage.' },
  { icon: FileJson, title: 'SBOM export', body: 'Download a CycloneDX bill of materials for audits and tooling.' },
]

/** First-run screen: explains the product and puts the analysis form front and centre. */
export function Landing(props: Omit<ComponentProps<typeof AnalyzeForm>, 'variant' | 'hasAnalysis'>) {
  return (
    <section className="landing">
      <h1>Find the risk in your dependencies</h1>
      <p className="landing-lead">
        Paste a GitHub repository to map its npm dependencies, surface known vulnerabilities, and see which ones
        actually matter.
      </p>

      <AnalyzeForm {...props} hasAnalysis={false} variant="hero" />

      <ul className="feature-list">
        {FEATURES.map(({ icon: Icon, title, body }) => (
          <li key={title}>
            <span className="feature-icon">
              <Icon size={18} aria-hidden="true" />
            </span>
            <div>
              <b>{title}</b>
              <p>{body}</p>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
