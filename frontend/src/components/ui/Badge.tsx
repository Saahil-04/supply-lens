import type { ReactNode } from 'react'
import {
  PRIORITY,
  REACHABILITY,
  SEVERITY_TONE,
  type Tone,
} from '../../lib/format'

export function Badge({ tone = 'neutral', title, children }: { tone?: Tone; title?: string; children: ReactNode }) {
  return (
    <span className={`badge badge-${tone}`} title={title}>
      {children}
    </span>
  )
}

export function PriorityBadge({ priority, reason }: { priority?: number | null; reason?: string | null }) {
  const meta = priority ? PRIORITY[priority] : undefined
  if (!priority || !meta) return <span className="muted">—</span>
  return (
    <Badge tone={meta.tone} title={reason ?? undefined}>
      P{priority} · {meta.label}
    </Badge>
  )
}

export function ReachabilityBadge({ status }: { status?: string }) {
  const meta = REACHABILITY[status ?? 'unknown']
  return <Badge tone={meta?.tone ?? 'neutral'}>{meta?.label ?? status}</Badge>
}

export function SeverityBadge({ severity }: { severity?: string }) {
  const label = (severity || 'UNKNOWN').toUpperCase()
  return <Badge tone={SEVERITY_TONE[label] ?? 'neutral'}>{label}</Badge>
}
