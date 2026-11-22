import { LoadingState } from '../components/ui/LoadingState'
import { Alert } from '../components/ui/Alert'
import { Panel } from '../components/ui/Panel'
import { AnalysisOverview } from '../components/overview/AnalysisOverview'
import { AnalyzeForm } from '../components/overview/AnalyzeForm'
import { Landing } from '../components/overview/Landing'
import type { AnalysisSession } from '../hooks/useAnalysisSession'
import { downloadSbom } from '../lib/downloadSbom'
import { errorText } from '../lib/format'
import type { TabId } from '../lib/tabs'

export function OverviewView({ session, onNavigate }: { session: AnalysisSession; onNavigate: (tab: TabId) => void }) {
  const { analysis, error } = session

  const formProps = {
    url: session.repositoryUrl,
    onUrlChange: session.setRepositoryUrl,
    includeReachability: session.includeReachability,
    onIncludeReachabilityChange: session.setIncludeReachability,
    onSubmit: session.runAnalysis,
    running: session.running,
    disabled: session.apiOnline === false,
  }

  const errorAlert = error && (
    <Alert
      tone="error"
      title="We couldn’t complete that request"
      onDismiss={session.dismissError}
      action={
        session.canStartOver && (
          <button type="button" className="btn btn-secondary btn-sm" onClick={session.closeAnalysis}>
            Start a new analysis
          </button>
        )
      }
    >
      {error}
    </Alert>
  )

  // Restoring the previous analysis on load: avoid flashing the landing screen.
  if (!analysis && session.refreshing) {
    return <LoadingState>Loading your last analysis…</LoadingState>
  }

  if (!analysis) {
    return (
      <>
        {errorAlert}
        <Landing {...formProps} />
      </>
    )
  }

  return (
    <>
      {errorAlert}
      <Panel className="analyze-panel">
        <AnalyzeForm {...formProps} hasAnalysis />
      </Panel>
      <AnalysisOverview
        analysis={analysis}
        refreshing={session.refreshing}
        onRefresh={() => void session.refresh()}
        onDownload={() => downloadSbom(analysis.analysis_id).catch((e) => session.setError(errorText(e)))}
        onNavigate={onNavigate}
      />
    </>
  )
}
