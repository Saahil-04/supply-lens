import { useEffect, useState } from 'react'
import { useAnalysisSession } from './hooks/useAnalysisSession'
import { downloadSbom } from './lib/downloadSbom'
import type { Tab } from './lib/tabs'
import { PageFooter } from './components/layout/PageFooter'
import { Sidebar } from './components/layout/Sidebar'
import { Topbar } from './components/layout/Topbar'
import { EmptyState } from './components/ui/EmptyState'
import { GraphView } from './views/GraphView'
import { OverviewView } from './views/OverviewView'
import { PackagesView } from './views/PackagesView'
import { ProjectsView } from './views/ProjectsView'
import { RecommendationsView } from './views/RecommendationsView'
import { VulnerabilitiesView } from './views/VulnerabilitiesView'

export default function App() {
  const [tab, setTab] = useState<Tab>('Overview')
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    const saved = localStorage.getItem('supplylens-theme')
    return saved === 'dark' ? 'dark' : 'light'
  })

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('supplylens-theme', theme)
  }, [theme])
  const session = useAnalysisSession({ onShowOverview: () => setTab('Overview') })
  const { analysis } = session

  return (
    <div className={`app-shell ${sidebarOpen ? '' : 'sidebar-collapsed'}`}>
      <Sidebar
        tab={tab}
        onTabChange={setTab}
        analysis={analysis}
        apiOnline={session.apiOnline}
        onCheckApi={() => void session.checkApi()}
        onClose={() => setSidebarOpen(false)}
      />

      <main className="main-area">
        <Topbar tab={tab} hasAnalysis={!!analysis} onClose={session.forgetAnalysis} sidebarOpen={sidebarOpen} onOpenSidebar={() => setSidebarOpen(true)} theme={theme} onToggleTheme={() => setTheme((current) => current === 'light' ? 'dark' : 'light')} />

        <div className="page-content">
          {!analysis && tab !== 'Overview' && (
            <EmptyState
              title="No active analysis"
              body="Analyze a GitHub repository first. Your results will appear here."
              action={() => setTab('Overview')}
            />
          )}

          {tab === 'Overview' && (
            <OverviewView
              analysis={analysis}
              analysisId={session.analysisId}
              repositoryUrl={session.repositoryUrl}
              onUrlChange={session.setRepositoryUrl}
              onSubmit={session.runAnalysis}
              loading={session.loading}
              checking={session.checking}
              apiOnline={session.apiOnline}
              error={session.error}
              onDismissError={() => session.setError('')}
              onRefresh={() => analysis && void session.loadAnalysis(analysis.analysis_id)}
              onForget={session.forgetAnalysis}
              onNavigate={setTab}
              onDownload={() => analysis && void downloadSbom(analysis.analysis_id, session.setError)}
            />
          )}

          {analysis && tab === 'Projects' && <ProjectsView id={analysis.analysis_id} />}
          {analysis && tab === 'Packages' && <PackagesView id={analysis.analysis_id} />}
          {analysis && tab === 'Vulnerabilities' && (
            <VulnerabilitiesView id={analysis.analysis_id} onError={session.setError} />
          )}
          {analysis && tab === 'Recommendations' && <RecommendationsView id={analysis.analysis_id} />}
          {analysis && tab === 'Dependency graph' && <GraphView id={analysis.analysis_id} />}

          {analysis && <PageFooter analysis={analysis} />}
        </div>
      </main>
    </div>
  )
}
