/* -------------------------------------------------------------------------- */
/*  Types                                                                      */
/* -------------------------------------------------------------------------- */

export type Page<T> = {
  items: T[]
  pagination: { offset: number; limit: number; total: number; has_more: boolean }
  filters?: Record<string, unknown>
}

export type Analysis = {
  analysis_id: string
  status: 'complete' | 'partial' | string
  inventory_status?: string
  vulnerability_analysis_status?: string
  created_at?: string
  expires_at?: string
  repository?: {
    url?: string
    owner?: string
    name?: string
    default_branch?: string
    commit_sha?: string
  }
  summary: Record<string, number | string | undefined>
  analysis_metadata?: Record<string, unknown>
  links?: Record<string, string>
}

export type Project = {
  name?: string
  path?: string
  manifest_path?: string
  lockfile_path?: string
  has_resolved_graph?: boolean
  direct_dependencies?: Array<{ name?: string; version?: string; dependency_type?: string }>
}

export type PackageItem = {
  id: string
  name: string
  version?: string
  path?: string
  lockfile?: string
  is_direct?: boolean
  direct_projects?: string[]
  is_dev?: boolean
  is_optional?: boolean
  resolved?: string
  integrity?: string
}

export type ReachabilityStatus =
  | 'imported'
  | 'transitive_of_imported'
  | 'tests_or_tooling_only'
  | 'dev_only'
  | 'not_imported'
  | 'unknown'

export type Reachability = {
  status: ReachabilityStatus
  confidence?: string
  via?: string | null
  files?: string[]
  note?: string
  reason?: string
}

export type Diagnostic = {
  code: string
  severity: 'error' | 'warning' | 'info' | string
  message: string
  path?: string
  hint?: string
  details?: Record<string, unknown>
}

export type PriorityCounts = Record<'P1' | 'P2' | 'P3' | 'P4', number>

/** Optional summary fields. Read them through `summaryExtras()`. */
export type SummaryExtras = {
  priority_counts?: PriorityCounts
  baseline_priority_counts?: PriorityCounts
  reachability?: Record<string, number>
}

export type ReachabilityMetadata = {
  enabled?: boolean
  unknown_reasons?: Record<string, number>
  files_scanned?: number
  max_files?: number
  projects_truncated?: number
  method?: string
}

export type Vulnerability = {
  finding_id: string
  reachability?: Reachability | null
  priority?: number | null
  priority_label?: string | null
  priority_reason?: string | null
  baseline_priority?: number | null
  id?: string
  aliases?: string[]
  summary?: string
  severity?: string
  cvss_score?: number | null
  package_id?: string
  package_name?: string
  installed_version?: string
  package_path?: string
  lockfile?: string
  fixed_versions?: string[]
  published?: string
  modified?: string
  links?: { detail?: string }
}

export type VulnerabilityDetail = {
  id?: string
  summary?: string
  details?: string
  severity?: string
  package_name?: string
  installed_version?: string
  package_path?: string
  fixed_versions?: string[]
  references?: Array<{ url?: string; type?: string }>
}

export type Recommendation = {
  priority?: number | null
  package_name?: string
  installed_version?: string
  fixed_versions?: string[]
  recommendation?: string
  vulnerability_ids?: string[]
  package_id?: string
  [key: string]: unknown
}

export type GraphNode = Record<string, unknown> & { id: string; name?: string; version?: string }
export type GraphEdge = { source: string; target: string; dependency_type?: string }
export type Graph = {
  root_package_id: string
  nodes: GraphNode[]
  edges: GraphEdge[]
  truncated?: boolean
}

/* -------------------------------------------------------------------------- */
/*  HTTP client                                                                */
/* -------------------------------------------------------------------------- */

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

export function apiUrl(path: string) {
  return `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`
}

/** Carries the service's structured error contract: `{ error: { code, message, hint, retryable } }`. */
export class ApiError extends Error {
  status: number
  code?: string
  hint?: string | null
  retryable: boolean

  constructor(message: string, status: number, code?: string, hint?: string | null, retryable = false) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.hint = hint
    this.retryable = retryable
  }
}

export const isAbortError = (error: unknown) => error instanceof DOMException && error.name === 'AbortError'

async function toApiError(response: Response): Promise<ApiError> {
  let message = `${response.status} ${response.statusText}`.trim()
  let code: string | undefined
  let hint: string | null | undefined
  let retryable = false

  try {
    const body = await response.json()
    if (typeof body?.error?.message === 'string') {
      ;({ code, hint } = body.error)
      message = body.error.message
      retryable = !!body.error.retryable
    } else if (body?.detail) {
      message = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    }
  } catch {
    /* Non-JSON error body: keep the status text. */
  }
  return new ApiError(message, response.status, code, hint, retryable)
}

/** Fetches `path` and throws an `ApiError` for network failures and non-2xx responses. */
export async function fetchOk(path: string, init?: RequestInit): Promise<Response> {
  let response: Response
  try {
    response = await fetch(apiUrl(path), {
      ...init,
      headers: { ...(init?.body ? { 'Content-Type': 'application/json' } : {}), ...init?.headers },
    })
  } catch (error) {
    if (isAbortError(error)) throw error
    throw new ApiError(
      'Could not reach the SupplyLens service. Check your connection and try again.',
      0,
      'NETWORK_ERROR',
      null,
      true,
    )
  }
  if (!response.ok) throw await toApiError(response)
  return response
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetchOk(path, init)
  return response.json() as Promise<T>
}

/* -------------------------------------------------------------------------- */
/*  Helpers                                                                    */
/* -------------------------------------------------------------------------- */

export function summaryExtras(analysis: Analysis): SummaryExtras {
  return analysis.summary as unknown as SummaryExtras
}

export function reachabilityMetadata(analysis: Analysis): ReachabilityMetadata | undefined {
  return analysis.analysis_metadata?.reachability as ReachabilityMetadata | undefined
}

export function diagnosticsOf(analysis: Analysis): Diagnostic[] {
  const list = analysis.analysis_metadata?.diagnostics
  return Array.isArray(list) ? (list as Diagnostic[]) : []
}

type QueryValue = string | number | boolean | undefined | null

/** Builds a query string, skipping empty values. */
export function qs(values: Record<string, QueryValue>) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value))
  }
  return params.toString()
}
