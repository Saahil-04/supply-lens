import type { Analysis } from '../../api'
import type { TabId } from '../../lib/tabs'
import { Alert } from '../ui/Alert'
import { CoveragePanel } from './CoveragePanel'
import { DiagnosticsPanel } from './DiagnosticsPanel'
import { ExploreLinks } from './ExploreLinks'
import { PosturePanel } from './PosturePanel'
import { PriorityPanel } from './PriorityPanel'
import { RepoHeader } from './RepoHeader'
import { StatGrid } from './StatGrid'

type Props = {
  analysis: Analysis
  refreshing: boolean
  onRefresh: () => void
  onDownload: () => void
  onNavigate: (tab: TabId) => void
}

/** Everything shown on the Overview tab once an analysis exists. */
export function AnalysisOverview({ analysis, refreshing, onRefresh, onDownload, onNavigate }: Props) {
  return (
    <>
      <RepoHeader analysis={analysis} refreshing={refreshing} onRefresh={onRefresh} onDownload={onDownload} />

      {analysis.status !== 'complete' && (
        <Alert tone="warning" title="Partial analysis">
          Some coverage is incomplete. Review the warnings below before treating this as a full assessment.
        </Alert>
      )}

      <StatGrid analysis={analysis} />

      <div className="two-column">
        <PosturePanel analysis={analysis} onNavigate={onNavigate} />
        <CoveragePanel analysis={analysis} onNavigate={onNavigate} />
      </div>

      <PriorityPanel analysis={analysis} onNavigate={onNavigate} />
      <DiagnosticsPanel analysis={analysis} />
      <ExploreLinks onNavigate={onNavigate} />
    </>
  )
}
