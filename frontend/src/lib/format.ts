export const n = (value: unknown) =>
  typeof value === 'number' ? value.toLocaleString() : value == null ? '—' : String(value)

export const severityClass = (s?: string) => `severity severity-${(s || 'unknown').toLowerCase()}`

export const errorText = (error: unknown) =>
  error instanceof Error ? error.message : 'Something went wrong. Please try again.'
