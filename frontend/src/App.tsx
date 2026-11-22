import { useEffect, useState } from 'react'
import { Package } from 'lucide-react'
import { useAnalysisSession } from './hooks/useAnalysisSession'
import { useTabRoute } from './hooks/useTabRoute'
import { useTheme } from './hooks/useTheme'
import { tabLabel } from './lib/tabs'
import { PageFooter } from './components/layout/PageFooter'
import { Sidebar } from './components/layout/Sidebar'
import { Topbar } from './components/layout/Topbar'
import { EmptyState } from './components/ui/EmptyState'
import { LoadingState } from './components/ui/LoadingState'
import { GraphView } from './views/GraphView'
import { OverviewView } from './views/OverviewView'
import { PackagesView } from './views/PackagesView'
import { ProjectsView } from './views/ProjectsView'
import { RecommendationsView } from './views/RecommendationsView'
import { VulnerabilitiesView } from './views/VulnerabilitiesView'

const COMPACT_LAYOUT = '(max-width: 960px)'

export default function App() {
  const [tab, navigate] = useTabRoute()
  const { theme, toggleTheme } = useTheme()
  const [sidebarOpen, setSidebarOpen] = useState(() => !window.matchMedia(COMPACT_LAYOUT).matches)
  const session = useAnalysisSession({ onShowOverview: () => navigate('overview') })
  const { analysis } = session

  // Each page starts at the top and is titled in the browser tab.
  useEffect(() => {
    window.scrollTo(0, 0)
    document.title = `${tabLabel(tab)} · SupplyLens`
  }, [tab])

  const go = (next: typeof tab) => {
    navigate(next)
    if (window.matchMedia(COMPACT_LAYOUT).matches) setSidebarOpen(false)
  }

  // Views are keyed by analysis so filters and selections reset for a new analysis.
  const key = analysis?.analysis_id
  const renderPage = () => {
    if (tab === 'overview') return <OverviewView session={session} onNavigate={go} />
    if (!analysis || !key) {
      if (session.refreshing) return <LoadingState>Loading your last analysis…</LoadingState>
      return (
        <EmptyState
          icon={Package}
          title="No active analysis"
          action={
            <button type="button" className="btn btn-primary" onClick={() => go('overview')}>
              Analyze a repository
            </button>
          }
        >
          Analyze a GitHub repository first. Its results will appear here.
        </EmptyState>
      )
    }
    switch (tab) {
      case 'projects': return <ProjectsView key={key} id={key} />
      case 'packages': return <PackagesView key={key} id={key} />
      case 'vulnerabilities': return <VulnerabilitiesView key={key} id={key} />
      case 'recommendations': return <RecommendationsView key={key} id={key} />
      case 'graph': return <GraphView key={key} id={key} />
    }
  }

  return (
    <div className={`app-shell ${sidebarOpen ? 'has-sidebar' : ''}`.trim()}>
      <a className="skip-link" href="#main">Skip to content</a>

      <Sidebar
        tab={tab}
        onTabChange={go}
        analysis={analysis}
        apiOnline={session.apiOnline}
        onCheckApi={() => void session.checkApi()}
        onClose={() => setSidebarOpen(false)}
      />
      <div className="sidebar-scrim" onClick={() => setSidebarOpen(false)} aria-hidden="true" />

      <div className="main-area">
        <Topbar
          tab={tab}
          analysis={analysis}
          showMenuButton={!sidebarOpen}
          onOpenSidebar={() => setSidebarOpen(true)}
          theme={theme}
          onToggleTheme={toggleTheme}
          onCloseAnalysis={session.closeAnalysis}
        />
        <main id="main" className="page-content">
          {renderPage()}
          {analysis && <PageFooter analysis={analysis} />}
        </main>
      </div>
    </div>
  )
}
