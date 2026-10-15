export type Page<T> = { items: T[]; pagination: { offset: number; limit: number; total: number; has_more: boolean }; filters?: Record<string, unknown> }
export type Analysis = {
  analysis_id: string; status: 'complete' | 'partial' | string; inventory_status?: string; vulnerability_analysis_status?: string;
  created_at?: string; expires_at?: string; repository?: { url?: string; owner?: string; name?: string; default_branch?: string; commit_sha?: string };
  summary: Record<string, number | string | undefined>; analysis_metadata?: Record<string, unknown>; links?: Record<string, string>
}
export type Project = { name?: string; path?: string; manifest_path?: string; lockfile_path?: string; has_resolved_graph?: boolean; direct_dependencies?: Array<{ name?: string; version?: string; dependency_type?: string }> }
export type PackageItem = { id: string; name: string; version?: string; path?: string; lockfile?: string; is_direct?: boolean; direct_projects?: string[]; is_dev?: boolean; is_optional?: boolean; resolved?: string; integrity?: string }
export type Vulnerability = { finding_id: string; id?: string; aliases?: string[]; summary?: string; severity?: string; cvss_score?: number | null; package_id?: string; package_name?: string; installed_version?: string; package_path?: string; lockfile?: string; fixed_versions?: string[]; published?: string; modified?: string; links?: { detail?: string } }
export type Recommendation = { package_name?: string; installed_version?: string; fixed_versions?: string[]; recommendation?: string; vulnerability_ids?: string[]; package_id?: string; [key: string]: unknown }
export type Graph = { root_package_id: string; nodes: Array<Record<string, unknown> & { id: string; name?: string; version?: string }>; edges: Array<{ source: string; target: string; dependency_type?: string }>; truncated?: boolean }

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')
export function apiUrl(path: string) { return `${API_BASE}${path.startsWith('/') ? path : `/${path}`}` }

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), { ...init, headers: { ...(init?.body ? { 'Content-Type': 'application/json' } : {}), ...init?.headers } })
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`
    try { const body = await response.json(); message = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? body) } catch { /* non-JSON error */ }
    throw new Error(message)
  }
  return response.json() as Promise<T>
}
export function qs(values: Record<string, string | number | boolean | undefined | null>) {
  const params = new URLSearchParams()
  Object.entries(values).forEach(([key, value]) => { if (value !== undefined && value !== null && value !== '') params.set(key, String(value)) })
  return params.toString()
}
