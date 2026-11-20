import { PRIORITY_LABEL, REACHABILITY_LABEL, REACHABILITY_TONE } from '../../lib/format'

export function PriorityBadge({ priority, reason }: { priority?: number | null; reason?: string | null }) {
  if (!priority) return <span className="muted">—</span>
  return (
    <span className={`priority-badge priority-${priority}`} title={reason || undefined}>
      P{priority} · {PRIORITY_LABEL[priority]}
    </span>
  )
}

export function ReachabilityPill({ status }: { status?: string }) {
  const key = status || 'unknown'
  return <span className={`pill ${REACHABILITY_TONE[key] || 'pill-neutral'}`}>{REACHABILITY_LABEL[key] || key}</span>
}
