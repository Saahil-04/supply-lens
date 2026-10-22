import type { FormEvent } from 'react'
import { LoaderCircle, RefreshCw } from 'lucide-react'
import type { Analysis } from '../api'
import type { Tab } from '../lib/tabs'
import { ErrorAlert } from '../components/ui/ErrorAlert'
import { AnalysisOverview } from '../components/overview/AnalysisOverview'
import { ScanForm } from '../components/overview/ScanForm'
import { WelcomePanel } from '../components/overview/WelcomePanel'

export function OverviewView({
  analysis,
  analysisId,
  repositoryUrl,
  onUrlChange,
  onSubmit,
  loading,
  checking,
  apiOnline,
  error,
  onDismissError,
  onRefresh,
  onForget,
  onNavigate,
  onDownload,
}: {
  analysis: Analysis | null
  analysisId: string
  repositoryUrl: string
  onUrlChange: (url: string) => void
  onSubmit: (event: FormEvent) => void
  loading: boolean
  checking: boolean
  apiOnline: boolean | null
  error: string
  onDismissError: () => void
  onRefresh: () => void
  onForget: () => void
  onNavigate: (tab: Tab) => void
  onDownload: () => void
}) {
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">SECURITY POSTURE</div>
          <h1>Repository overview</h1>
          <p>Understand dependency inventory, known vulnerabilities, and remediation priorities.</p>
        </div>
        {analysis && (
          <button className="button button-secondary" onClick={onRefresh} disabled={checking}>
            {checking ? <LoaderCircle className="spin" size={16} /> : <RefreshCw size={16} />} Refresh summary
          </button>
        )}
      </div>

      <ScanForm
        repositoryUrl={repositoryUrl}
        onUrlChange={onUrlChange}
        onSubmit={onSubmit}
        loading={loading}
        apiOnline={apiOnline}
        hasAnalysis={!!analysis}
      />

      {error && (
        <ErrorAlert
          message={error}
          canRestart={!!analysisId}
          onRestart={onForget}
          onDismiss={onDismissError}
        />
      )}

      {!analysis && <WelcomePanel />}

      {analysis && <AnalysisOverview analysis={analysis} onNavigate={onNavigate} onDownload={onDownload} />}
    </>
  )
}
