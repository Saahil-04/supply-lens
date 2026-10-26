import { Menu, Moon, Sun, X } from 'lucide-react'
import type { Tab } from '../../lib/tabs'

export function Topbar({
  tab,
  hasAnalysis,
  onClose,
  sidebarOpen,
  onOpenSidebar,
  theme,
  onToggleTheme,
}: {
  tab: Tab
  hasAnalysis: boolean
  onClose: () => void
  sidebarOpen: boolean
  onOpenSidebar: () => void
  theme: 'light' | 'dark'
  onToggleTheme: () => void
}) {
  return (
    <header className="topbar">
      <div className="topbar-left">
        {!sidebarOpen && (
          <button className="icon-button sidebar-open" onClick={onOpenSidebar} aria-label="Open sidebar" title="Open navigation">
            <Menu size={18} />
          </button>
        )}
        <div className="breadcrumb">
          Workspace <span>/</span> <b>{tab}</b>
        </div>
      </div>
      <div className="topbar-right">
        <span className="live-label">
          <span className="status-dot online" /> Repository snapshot analysis
        </span>
        <button className="theme-toggle" onClick={onToggleTheme} aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} theme`} title={`Switch to ${theme === 'light' ? 'dark' : 'light'} theme`}>
          {theme === 'light' ? <Moon size={16} /> : <Sun size={16} />}
          <span>{theme === 'light' ? 'Dark mode' : 'Light mode'}</span>
        </button>
        {hasAnalysis && (
          <button className="button button-quiet button-small" onClick={onClose}>
            <X size={14} /> Close scan
          </button>
        )}
      </div>
    </header>
  )
}
