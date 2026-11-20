export type Page<T> = { items: T[]; pagination: { offset: number; limit: number; total: number; has_more: boolean }; filters?: Record<string, unknown> }
export type Analysis = {
  analysis_id: string; status: 'complete' | 'partial' | string; inventory_status?: string; vulnerability_analysis_status?: string;
  created_at?: string; expires_at?: string; repository?: { url?: string; owner?: string; name?: string; default_branch?: string; commit_sha?: string };
  summary: Record<string, number | string | undefined>; analysis_metadata?: Record<string, unknown>; links?: Record<string, string>
}
export type Project = { name?: string; path?: string; manifest_path?: string; lockfile_path?: string; has_resolved_graph?: boolean; direct_dependencies?: Array<{ name?: string; version?: string; dependency_type?: string }> }
export type PackageItem = { id: string; name: string; version?: string; path?: string; lockfile?: string; is_direct?: boolean; direct_projects?: string[]; is_dev?: boolean; is_optional?: boolean; resolved?: string; integrity?: string }
export type ReachabilityStatus = 'imported' | 'transitive_of_imported' | 'tests_or_tooling_only' | 'dev_only' | 'not_imported' | 'unknown'
export type Reachability = { status: ReachabilityStatus; confidence?: string; via?: string | null; files?: string[]; note?: string; reason?: string }
export type Diagnostic = { code: string; severity: 'error' | 'warning' | 'info' | string; message: string; path?: string; hint?: string; details?: Record<string, unknown> }
export type PriorityCounts = Record<'P1' | 'P2' | 'P3' | 'P4', number>
/** Extra summary fields added by the hardened backend. Read through `summaryExtras()`. */
export type SummaryExtras = { priority_counts?: PriorityCounts; baseline_priority_counts?: PriorityCounts; reachability?: Record<string, number> }
export type Vulnerability = { finding_id: string; reachability?: Reachability | null; priority?: number | null; priority_label?: string | null; priority_reason?: string | null; baseline_priority?: number | null; id?: string; aliases?: string[]; summary?: string; severity?: string; cvss_score?: number | null; package_id?: string; package_name?: string; installed_version?: string; package_path?: string; lockfile?: string; fixed_versions?: string[]; published?: string; modified?: string; links?: { detail?: string } }
export type Recommendation = { priority?: number | null; package_name?: string; installed_version?: string; fixed_versions?: string[]; recommendation?: string; vulnerability_ids?: string[]; package_id?: string; [key: string]: unknown }
export type Graph = { root_package_id: string; nodes: Array<Record<string, unknown> & { id: string; name?: string; version?: string }>; edges: Array<{ source: string; target: string; dependency_type?: string }>; truncated?: boolean }

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')
export function apiUrl(path: string) { return `${API_BASE}${path.startsWith('/') ? path : `/${path}`}` }

/** Error carrying the backend's structured error contract: `{ error: { code, message, hint, retryable } }`. */
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

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(apiUrl(path), { ...init, headers: { ...(init?.body ? { 'Content-Type': 'application/json' } : {}), ...init?.headers } })
  } catch {
    throw new ApiError('Could not reach the SupplyLens backend. Check that it is running and try again.', 0, 'NETWORK_ERROR', null, true)
  }
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`
    let code: string | undefined
    let hint: string | null | undefined
    let retryable = false
    try {
      const body = await response.json()
      if (body?.error && typeof body.error.message === 'string') {
        message = body.error.message; code = body.error.code; hint = body.error.hint; retryable = !!body.error.retryable
      } else {
        message = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? body)
      }
    } catch { /* non-JSON error */ }
    throw new ApiError(message, response.status, code, hint, retryable)
  }
  return response.json() as Promise<T>
}

export function summaryExtras(analysis: Analysis): SummaryExtras {
  return analysis.summary as unknown as SummaryExtras
}

export function diagnosticsOf(analysis: Analysis): Diagnostic[] {
  const list = analysis.analysis_metadata?.diagnostics
  return Array.isArray(list) ? (list as Diagnostic[]) : []
}
export function qs(values: Record<string, string | number | boolean | undefined | null>) {
  const params = new URLSearchParams()
  Object.entries(values).forEach(([key, value]) => { if (value !== undefined && value !== null && value !== '') params.set(key, String(value)) })
  return params.toString()
}
