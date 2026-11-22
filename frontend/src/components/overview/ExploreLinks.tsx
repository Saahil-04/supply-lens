import { ArrowRight, GitBranch, Package, Sparkles, type LucideIcon } from 'lucide-react'
import type { TabId } from '../../lib/tabs'

const LINKS: { tab: TabId; icon: LucideIcon; title: string; body: string }[] = [
  { tab: 'packages', icon: Package, title: 'Explore packages', body: 'Search the resolved inventory' },
  { tab: 'recommendations', icon: Sparkles, title: 'Review remediation', body: 'See suggested package updates' },
  { tab: 'graph', icon: GitBranch, title: 'Trace dependencies', body: 'Inspect a package neighborhood' },
]

export function ExploreLinks({ onNavigate }: { onNavigate: (tab: TabId) => void }) {
  return (
    <div className="explore-grid">
      {LINKS.map(({ tab, icon: Icon, title, body }) => (
        <button key={tab} type="button" className="explore-card" onClick={() => onNavigate(tab)}>
          <span className="explore-icon">
            <Icon size={18} aria-hidden="true" />
          </span>
          <span className="explore-text">
            <b>{title}</b>
            <small>{body}</small>
          </span>
          <ArrowRight size={16} className="explore-arrow" aria-hidden="true" />
        </button>
      ))}
    </div>
  )
}
