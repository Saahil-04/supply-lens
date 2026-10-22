import type { Analysis } from '../../api'
import type { Tab } from '../../lib/tabs'
import { CoveragePanel } from './CoveragePanel'
import { MetricGrid } from './MetricGrid'
import { QuickActions } from './QuickActions'
import { RepoTitleRow } from './RepoTitleRow'
import { StatusBanner } from './StatusBanner'
import { VulnerabilityPosturePanel } from './VulnerabilityPosturePanel'
import { WarningsPanel } from './WarningsPanel'

/** Everything shown on the Overview tab once an analysis exists. */
export function AnalysisOverview({
  analysis,
  onNavigate,
  onDownload,
}: {
  analysis: Analysis
  onNavigate: (tab: Tab) => void
  onDownload: () => void
}) {
  return (
    <>
      <StatusBanner analysis={analysis} />
      <RepoTitleRow analysis={analysis} onDownload={onDownload} />
      <MetricGrid analysis={analysis} />
      <div className="overview-grid">
        <VulnerabilityPosturePanel analysis={analysis} onNavigate={onNavigate} />
        <CoveragePanel analysis={analysis} onNavigate={onNavigate} />
      </div>
      <WarningsPanel analysis={analysis} />
      <QuickActions onNavigate={onNavigate} />
    </>
  )
}
