import { ApiError } from '../api'

export type Tone = 'neutral' | 'info' | 'success' | 'warning' | 'danger' | 'critical' | 'violet'

export const formatNumber = (value: unknown): string => {
  if (typeof value === 'number') return value.toLocaleString()
  return value == null || value === '' ? '—' : String(value)
}

export const pluralize = (count: number, singular: string, plural = `${singular}s`) =>
  `${count.toLocaleString()} ${count === 1 ? singular : plural}`

export const formatDateTime = (iso?: string) =>
  iso ? new Date(iso).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : undefined

/** "14:05" for today, "Nov 22, 14:05" otherwise. */
export function formatExpiry(iso?: string) {
  if (!iso) return undefined
  const date = new Date(iso)
  const time = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  return date.toDateString() === new Date().toDateString()
    ? time
    : `${date.toLocaleDateString([], { month: 'short', day: 'numeric' })}, ${time}`
}

export const packageLabel = (name: string, version?: string) => (version ? `${name}@${version}` : name)

export const truncate = (text: string, max: number) => (text.length > max ? `${text.slice(0, max - 1)}…` : text)

export const errorText = (error: unknown) => {
  if (error instanceof ApiError) return error.hint ? `${error.message} ${error.hint}` : error.message
  return error instanceof Error ? error.message : 'Something went wrong. Please try again.'
}

/* -------------------------------------------------------------------------- */
/*  Domain vocabulary shared by tables, badges and panels                      */
/* -------------------------------------------------------------------------- */

export const REACHABILITY: Record<string, { label: string; tone: Tone }> = {
  imported: { label: 'Imported by your code', tone: 'danger' },
  transitive_of_imported: { label: 'Used via a dependency', tone: 'warning' },
  tests_or_tooling_only: { label: 'Tests / tooling only', tone: 'info' },
  dev_only: { label: 'Dev dependency', tone: 'info' },
  not_imported: { label: 'Not imported', tone: 'success' },
  unknown: { label: 'Unknown', tone: 'neutral' },
}

export const PRIORITY: Record<number, { label: string; tone: Tone }> = {
  1: { label: 'Fix now', tone: 'critical' },
  2: { label: 'Fix soon', tone: 'danger' },
  3: { label: 'Plan', tone: 'warning' },
  4: { label: 'Monitor', tone: 'neutral' },
}

export const SEVERITY_TONE: Record<string, Tone> = {
  CRITICAL: 'critical',
  HIGH: 'danger',
  MEDIUM: 'warning',
  LOW: 'info',
  UNKNOWN: 'neutral',
}

export const SEVERITIES = Object.keys(SEVERITY_TONE)

export function riskTone(level: unknown): Tone {
  switch (String(level ?? '').toLowerCase()) {
    case 'critical':
      return 'critical'
    case 'high':
      return 'danger'
    case 'medium':
    case 'moderate':
      return 'warning'
    case 'low':
    case 'none':
      return 'success'
    default:
      return 'neutral'
  }
}

export const UNKNOWN_REASON: Record<string, string> = {
  not_scanned_budget: 'Not scanned: this project got no share of the source-file budget.',
  scan_incomplete: 'Only part of this project’s source was scanned, and the package was not found in that part.',
  no_source_files: 'No JavaScript/TypeScript source files were found for the owning project.',
  download_failed: 'Some source files could not be downloaded from GitHub.',
  no_direct_owner: 'Could not link this package to a direct dependency of any project.',
}
