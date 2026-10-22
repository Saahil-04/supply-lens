import type { Analysis } from '../../api'

export function PageFooter({ analysis }: { analysis: Analysis }) {
  return (
    <footer className="page-footer">
      <span>
        Analysis <code>{analysis.analysis_id.slice(0, 8)}…</code>
      </span>
      <span>
        Results retained until{' '}
        {analysis.expires_at
          ? new Date(analysis.expires_at).toLocaleTimeString([], {
              hour: '2-digit',
              minute: '2-digit',
            })
          : 'expiry'}{' '}
        · in-memory backend storage
      </span>
    </footer>
  )
}
