import { X } from 'lucide-react'
import type { Tab } from '../../lib/tabs'

export function Topbar({
  tab,
  hasAnalysis,
  onClose,
}: {
  tab: Tab
  hasAnalysis: boolean
  onClose: () => void
}) {
  return (
    <header className="topbar">
      <div className="breadcrumb">
        Workspace <span>/</span> <b>{tab}</b>
      </div>
      <div className="topbar-right">
        <span className="live-label">
          <span className="status-dot online" /> Repository snapshot analysis
        </span>
        {hasAnalysis && (
          <button className="button button-quiet button-small" onClick={onClose}>
            <X size={14} /> Close scan
          </button>
        )}
      </div>
    </header>
  )
}
