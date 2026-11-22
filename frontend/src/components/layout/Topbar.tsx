import { Menu, Moon, Sun, X } from 'lucide-react'
import type { Analysis } from '../../api'
import type { Theme } from '../../hooks/useTheme'
import { tabLabel, type TabId } from '../../lib/tabs'

type Props = {
  tab: TabId
  analysis: Analysis | null
  showMenuButton: boolean
  onOpenSidebar: () => void
  theme: Theme
  onToggleTheme: () => void
  onCloseAnalysis: () => void
}

export function Topbar({ tab, analysis, showMenuButton, onOpenSidebar, theme, onToggleTheme, onCloseAnalysis }: Props) {
  const repository = analysis?.repository
  const nextTheme = theme === 'light' ? 'dark' : 'light'

  return (
    <header className="topbar">
      <div className="topbar-left">
        {showMenuButton && (
          <button type="button" className="icon-button" onClick={onOpenSidebar} aria-label="Open navigation">
            <Menu size={18} />
          </button>
        )}
        <nav className="breadcrumb" aria-label="Breadcrumb">
          {repository?.owner && repository.name && (
            <>
              <span className="breadcrumb-repo">
                {repository.owner}/{repository.name}
              </span>
              <span className="breadcrumb-sep" aria-hidden="true">/</span>
            </>
          )}
          <b>{tabLabel(tab)}</b>
        </nav>
      </div>

      <div className="topbar-right">
        <button
          type="button"
          className="icon-button"
          onClick={onToggleTheme}
          aria-label={`Switch to ${nextTheme} theme`}
          title={`Switch to ${nextTheme} theme`}
        >
          {theme === 'light' ? <Moon size={17} /> : <Sun size={17} />}
        </button>
        {analysis && (
          <button type="button" className="btn btn-ghost btn-sm" onClick={onCloseAnalysis}>
            <X size={14} /> Close analysis
          </button>
        )}
      </div>
    </header>
  )
}
