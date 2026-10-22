import type { ReactNode } from 'react'
import { ArrowRight, GitBranch, Package, Sparkles } from 'lucide-react'
import type { Tab } from '../../lib/tabs'

const actions: { tab: Tab; tone: string; icon: ReactNode; title: string; sub: string }[] = [
  {
    tab: 'Packages',
    tone: 'violet',
    icon: <Package size={18} />,
    title: 'Explore packages',
    sub: 'Search the resolved inventory',
  },
  {
    tab: 'Recommendations',
    tone: 'green',
    icon: <Sparkles size={18} />,
    title: 'Review remediation',
    sub: 'Find suggested package updates',
  },
  {
    tab: 'Dependency graph',
    tone: 'blue',
    icon: <GitBranch size={18} />,
    title: 'Trace dependencies',
    sub: 'Inspect a package neighborhood',
  },
]

export function QuickActions({ onNavigate }: { onNavigate: (tab: Tab) => void }) {
  return (
    <div className="quick-actions">
      {actions.map((a) => (
        <button key={a.tab} onClick={() => onNavigate(a.tab)}>
          <span className={`quick-icon quick-${a.tone}`}>{a.icon}</span>
          <span>
            <b>{a.title}</b>
            <small>{a.sub}</small>
          </span>
          <ArrowRight size={16} />
        </button>
      ))}
    </div>
  )
}
