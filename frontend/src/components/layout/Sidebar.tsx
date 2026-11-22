import { PanelLeftClose, RefreshCw, ShieldCheck } from 'lucide-react'
import type { Analysis } from '../../api'
import { formatNumber } from '../../lib/format'
import { TABS, type TabId } from '../../lib/tabs'
import { Github } from '../icons/Github'

type Props = {
  tab: TabId
  onTabChange: (tab: TabId) => void
  analysis: Analysis | null
  apiOnline: boolean | null
  onCheckApi: () => void
  onClose: () => void
}

const SERVICE_STATUS = {
  true: { label: 'Service connected', className: 'online' },
  false: { label: 'Service unreachable', className: 'offline' },
  null: { label: 'Checking service…', className: '' },
} as const

export function Sidebar({ tab, onTabChange, analysis, apiOnline, onCheckApi, onClose }: Props) {
  const findings = Number(analysis?.summary.vulnerabilities_found ?? 0)
  const status = SERVICE_STATUS[String(apiOnline) as keyof typeof SERVICE_STATUS]
  const repository = analysis?.repository

  return (
    <aside className="sidebar" aria-label="Primary">
      <div className="sidebar-brand">
        <span className="brand-mark">
          <ShieldCheck size={20} aria-hidden="true" />
        </span>
        <span className="brand-name">SupplyLens</span>
        <button type="button" className="icon-button sidebar-collapse" onClick={onClose} aria-label="Hide sidebar">
          <PanelLeftClose size={18} />
        </button>
      </div>

      <div className="sidebar-section">Repository</div>
      <div className="repo-card">
        <span className="repo-card-icon">
          <Github size={16} />
        </span>
        <span className="repo-card-text">
          <b>{repository?.name ?? 'No repository yet'}</b>
          <small>{repository?.owner ?? 'Analyze a repository to begin'}</small>
        </span>
      </div>

      <div className="sidebar-section">Explore</div>
      <nav className="nav-list">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            type="button"
            className={`nav-item ${tab === id ? 'is-active' : ''}`.trim()}
            aria-current={tab === id ? 'page' : undefined}
            disabled={!analysis && id !== 'overview'}
            onClick={() => onTabChange(id)}
          >
            <Icon size={17} aria-hidden="true" />
            <span>{label}</span>
            {id === 'vulnerabilities' && findings > 0 && <span className="nav-count">{formatNumber(findings)}</span>}
          </button>
        ))}
      </nav>

      <div className="sidebar-footer">
        <span className={`status-dot ${status.className}`} aria-hidden="true" />
        <span>{status.label}</span>
        <button type="button" className="icon-button" onClick={onCheckApi} aria-label="Check service status" title="Check again">
          <RefreshCw size={13} />
        </button>
      </div>
    </aside>
  )
}
