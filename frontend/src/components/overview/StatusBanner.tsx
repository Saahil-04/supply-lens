import { AlertTriangle, ShieldCheck } from 'lucide-react'
import type { Analysis } from '../../api'

export function StatusBanner({ analysis }: { analysis: Analysis }) {
  const isComplete = analysis.status === 'complete'
  return (
    <div className={`scan-status-banner ${isComplete ? 'status-complete' : 'status-partial'}`}>
      <div className="status-banner-icon">
        {isComplete ? <ShieldCheck size={19} /> : <AlertTriangle size={19} />}
      </div>
      <div className="status-banner-copy">
        <b>{isComplete ? 'Analysis complete' : 'Partial analysis'}</b>
        <span>
          {isComplete
            ? 'Inventory and vulnerability analysis stages reported complete.'
            : 'Some coverage is incomplete. Review warnings before treating this as a full assessment.'}
        </span>
      </div>
      <span className={`pill ${isComplete ? 'pill-green' : 'pill-amber'}`}>{analysis.status || 'unknown'}</span>
    </div>
  )
}
