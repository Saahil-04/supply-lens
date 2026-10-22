import { ChevronDown, RefreshCw, ShieldCheck } from 'lucide-react'
import type { Analysis } from '../../api'
import { n } from '../../lib/format'
import { tabs, type Tab } from '../../lib/tabs'
import { Github } from '../icons/Github'

export function Sidebar({
  tab,
  onTabChange,
  analysis,
  apiOnline,
  onCheckApi,
}: {
  tab: Tab
  onTabChange: (tab: Tab) => void
  analysis: Analysis | null
  apiOnline: boolean | null
  onCheckApi: () => void
}) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">
          <ShieldCheck size={21} />
        </div>
        <div>
          <div className="brand-name">SupplyLens</div>
          <div className="brand-subtitle">SOFTWARE SUPPLY CHAIN</div>
        </div>
      </div>

      <div className="workspace-label">WORKSPACE</div>
      <div className="repo-switcher">
        <div className="repo-avatar">
          <Github size={16} />
        </div>
        <div className="repo-switcher-text">
          <b>{analysis?.repository?.name || 'Repository analysis'}</b>
          <span>{analysis?.repository?.owner || 'GitHub repository'}</span>
        </div>
        <ChevronDown size={15} />
      </div>

      <div className="nav-label">ANALYZE</div>
      <nav className="nav-list">
        {tabs.map((item) => {
          const Icon = item.icon
          return (
            <button
              key={item.name}
              className={`nav-item ${tab === item.name ? 'active' : ''}`}
              onClick={() => onTabChange(item.name)}
              disabled={!analysis && item.name !== 'Overview'}
            >
              <Icon size={17} />
              <span>{item.name}</span>
              {item.name === 'Vulnerabilities' &&
                analysis &&
                Number(analysis.summary.vulnerabilities_found) > 0 && (
                  <span className="nav-count">{n(analysis.summary.vulnerabilities_found)}</span>
                )}
            </button>
          )
        })}
      </nav>

      <div className="sidebar-bottom">
        <div className="api-status">
          <span
            className={`status-dot ${apiOnline === true ? 'online' : apiOnline === false ? 'offline' : ''}`}
          />
          <span>
            API {apiOnline === true ? 'connected' : apiOnline === false ? 'unreachable' : 'checking'}
          </span>
          <button title="Check API again" onClick={onCheckApi}>
            <RefreshCw size={13} />
          </button>
        </div>
        <div className="version">SUPPLYLENS MVP · LOCAL</div>
      </div>
    </aside>
  )
}
