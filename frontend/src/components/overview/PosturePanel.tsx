import { ArrowRight } from 'lucide-react'
import type { Analysis } from '../../api'
import { formatNumber, riskTone } from '../../lib/format'
import type { TabId } from '../../lib/tabs'
import { Badge } from '../ui/Badge'
import { Panel } from '../ui/Panel'

export function PosturePanel({ analysis, onNavigate }: { analysis: Analysis; onNavigate: (tab: TabId) => void }) {
  const { summary } = analysis
  const risk = summary.risk_level

  return (
    <Panel
      title="Vulnerability posture"
      description="Known advisory findings from OSV"
      action={risk ? <span className="capitalize"><Badge tone={riskTone(risk)}>{String(risk)}</Badge></span> : undefined}
    >
      <div className="big-number">
        <strong>{formatNumber(summary.vulnerabilities_found)}</strong>
        <span>finding instances across {formatNumber(summary.unique_advisories_found)} unique advisories</span>
      </div>
      <p className="note">
        One advisory can affect several installed package instances, so the two counts differ by design.
      </p>
      <button type="button" className="btn btn-secondary btn-block" onClick={() => onNavigate('vulnerabilities')}>
        Review findings <ArrowRight size={15} />
      </button>
    </Panel>
  )
}
