import type { Analysis } from '../../api'
import { formatExpiry } from '../../lib/format'

export function PageFooter({ analysis }: { analysis: Analysis }) {
  const expiry = formatExpiry(analysis.expires_at)
  return (
    <footer className="page-footer">
      <span>
        Analysis <code>{analysis.analysis_id.slice(0, 8)}</code>
      </span>
      {expiry && <span>Results available until {expiry}</span>}
    </footer>
  )
}
