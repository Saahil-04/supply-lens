import { ApiError } from '../api'

export const n = (value: unknown) =>
  typeof value === 'number' ? value.toLocaleString() : value == null ? '—' : String(value)

export const severityClass = (s?: string) => `severity severity-${(s || 'unknown').toLowerCase()}`

export const errorText = (error: unknown) => {
  if (error instanceof ApiError) return error.hint ? `${error.message} ${error.hint}` : error.message
  return error instanceof Error ? error.message : 'Something went wrong. Please try again.'
}

export const REACHABILITY_LABEL: Record<string, string> = {
  imported: 'Imported by your code',
  transitive_of_imported: 'Used via a dependency',
  tests_or_tooling_only: 'Tests / tooling only',
  dev_only: 'Dev dependency',
  not_imported: 'Not imported',
  unknown: 'Unknown',
}
export const REACHABILITY_TONE: Record<string, string> = {
  imported: 'pill-red', transitive_of_imported: 'pill-amber', tests_or_tooling_only: 'pill-blue',
  dev_only: 'pill-blue', not_imported: 'pill-green', unknown: 'pill-neutral',
}
export const PRIORITY_LABEL: Record<number, string> = { 1: 'Fix now', 2: 'Fix soon', 3: 'Plan', 4: 'Monitor' }

export const UNKNOWN_REASON: Record<string, string> = {
  not_scanned_budget: 'Not scanned: this project got no share of the source-file budget.',
  scan_incomplete: 'Only part of this project’s source was scanned, and the package was not found in that part.',
  no_source_files: 'No JavaScript/TypeScript source files were found for the owning project.',
  download_failed: 'Some source files could not be downloaded from GitHub.',
  no_direct_owner: 'Could not link this package to a direct dependency of any project.',
}
