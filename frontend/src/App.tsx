import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  ArrowDownToLine,
  ArrowLeft,
  ArrowRight,
  Boxes,
  Check,
  ChevronDown,
  CircleHelp,
  ExternalLink,
  FileCheck2,
  GitBranch,
  LayoutDashboard,
  LoaderCircle,
  Package,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  X,
} from 'lucide-react'
import {
  apiUrl,
  qs,
  request,
  type Analysis,
  type Graph,
  type PackageItem,
  type Page,
  type Project,
  type Recommendation,
  type Vulnerability,
} from './api'

// lucide-react v1+ removed brand icons (including Github), so we ship a local one.
function Github({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12 .5C5.73.5.5 5.73.5 12c0 5.08 3.29 9.39 7.86 10.91.58.1.79-.25.79-.56v-2c-3.2.7-3.88-1.54-3.88-1.54-.52-1.33-1.28-1.69-1.28-1.69-1.04-.71.08-.7.08-.7 1.15.08 1.76 1.19 1.76 1.19 1.03 1.76 2.69 1.25 3.35.96.1-.74.4-1.25.73-1.54-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.28 1.19-3.09-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.17 1.18a11 11 0 0 1 5.77 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.11 3.05.74.81 1.19 1.83 1.19 3.09 0 4.42-2.69 5.39-5.25 5.68.41.36.78 1.06.78 2.14v3.17c0 .31.21.67.8.56A11.51 11.51 0 0 0 23.5 12C23.5 5.73 18.27.5 12 .5Z" />
    </svg>
  )
}

type Tab = 'Overview' | 'Projects' | 'Packages' | 'Vulnerabilities' | 'Recommendations' | 'Dependency graph'

const tabs: { name: Tab; icon: typeof LayoutDashboard }[] = [
  { name: 'Overview', icon: LayoutDashboard },
  { name: 'Projects', icon: Boxes },
  { name: 'Packages', icon: Package },
  { name: 'Vulnerabilities', icon: ShieldAlert },
  { name: 'Recommendations', icon: Sparkles },
  { name: 'Dependency graph', icon: GitBranch },
]

const storedAnalysisKey = 'supplylens:last-analysis-id'
const storedUrlKey = 'supplylens:last-repository-url'

const n = (value: unknown) =>
  typeof value === 'number' ? value.toLocaleString() : value == null ? '—' : String(value)
const severityClass = (s?: string) => `severity severity-${(s || 'unknown').toLowerCase()}`
const errorText = (error: unknown) =>
  error instanceof Error ? error.message : 'Something went wrong. Please try again.'

export default function App() {
  const [tab, setTab] = useState<Tab>('Overview')
  const [repositoryUrl, setRepositoryUrl] = useState(() => localStorage.getItem(storedUrlKey) || '')
  const [analysisId, setAnalysisId] = useState(() => localStorage.getItem(storedAnalysisKey) || '')
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [loading, setLoading] = useState(false)
  const [checking, setChecking] = useState(false)
  const [error, setError] = useState('')
  const [apiOnline, setApiOnline] = useState<boolean | null>(null)

  const loadAnalysis = useCallback(async (id: string) => {
    if (!id) return
    setChecking(true)
    try {
      const result = await request<Analysis>(`/analyses/${encodeURIComponent(id)}`)
      setAnalysis(result)
      setError('')
    } catch (e) {
      setAnalysis(null)
      setError(errorText(e))
    } finally {
      setChecking(false)
    }
  }, [])

  const checkApi = () =>
    request<{ status: string }>('/health')
      .then(() => setApiOnline(true))
      .catch(() => setApiOnline(false))

  useEffect(() => {
    void checkApi()
  }, [])

  useEffect(() => {
    if (analysisId) void loadAnalysis(analysisId)
  }, [analysisId, loadAnalysis])

  const runAnalysis = async (event: React.FormEvent) => {
    event.preventDefault()
    const url = repositoryUrl.trim()
    if (!/^https?:\/\/(www\.)?github\.com\/[\w.-]+\/[\w.-]+\/?$/.test(url)) {
      setError('Enter a GitHub repository URL, for example https://github.com/owner/repo')
      return
    }
    setLoading(true)
    setError('')
    setAnalysis(null)
    try {
      localStorage.setItem(storedUrlKey, url)
      const result = await request<Analysis>('/analyze', {
        method: 'POST',
        body: JSON.stringify({ repository_url: url }),
      })
      setAnalysisId(result.analysis_id)
      localStorage.setItem(storedAnalysisKey, result.analysis_id)
      setAnalysis(result)
      setTab('Overview')
    } catch (e) {
      setError(errorText(e))
    } finally {
      setLoading(false)
    }
  }

  const forgetAnalysis = () => {
    setAnalysisId('')
    setAnalysis(null)
    setError('')
    localStorage.removeItem(storedAnalysisKey)
    setTab('Overview')
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <ShieldCheck size={21} />
          </div>
          <div>
            <div className="brand-name">SupplyLens</div>
            <div className="brand-subtitle">SOFTWARE SUPPLY CHAIN</div>
          </div>
        </div>

        <div className="workspace-label">WORKSPACE</div>
        <div className="repo-switcher">
          <div className="repo-avatar">
            <Github size={16} />
          </div>
          <div className="repo-switcher-text">
            <b>{analysis?.repository?.name || 'Repository analysis'}</b>
            <span>{analysis?.repository?.owner || 'GitHub repository'}</span>
          </div>
          <ChevronDown size={15} />
        </div>

        <div className="nav-label">ANALYZE</div>
        <nav className="nav-list">
          {tabs.map((item) => {
            const Icon = item.icon
            return (
              <button
                key={item.name}
                className={`nav-item ${tab === item.name ? 'active' : ''}`}
                onClick={() => setTab(item.name)}
                disabled={!analysis && item.name !== 'Overview'}
              >
                <Icon size={17} />
                <span>{item.name}</span>
                {item.name === 'Vulnerabilities' &&
                  analysis &&
                  Number(analysis.summary.vulnerabilities_found) > 0 && (
                    <span className="nav-count">{n(analysis.summary.vulnerabilities_found)}</span>
                  )}
              </button>
            )
          })}
        </nav>

        <div className="sidebar-bottom">
          <div className="api-status">
            <span
              className={`status-dot ${apiOnline === true ? 'online' : apiOnline === false ? 'offline' : ''}`}
            />
            <span>
              API {apiOnline === true ? 'connected' : apiOnline === false ? 'unreachable' : 'checking'}
            </span>
            <button title="Check API again" onClick={() => void checkApi()}>
              <RefreshCw size={13} />
            </button>
          </div>
          <div className="version">SUPPLYLENS MVP · LOCAL</div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <span>/</span> <b>{tab}</b>
          </div>
          <div className="topbar-right">
            <span className="live-label">
              <span className="status-dot online" /> Repository snapshot analysis
            </span>
            {analysis && (
              <button className="button button-quiet button-small" onClick={forgetAnalysis}>
                <X size={14} /> Close scan
              </button>
            )}
          </div>
        </header>

        <div className="page-content">
          {!analysis && tab !== 'Overview' ? (
            <EmptyState
              title="No active analysis"
              body="Analyze a GitHub repository first. Your results will appear here."
              action={() => setTab('Overview')}
            />
          ) : null}

          {tab === 'Overview' && (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">SECURITY POSTURE</div>
                  <h1>Repository overview</h1>
                  <p>Understand dependency inventory, known vulnerabilities, and remediation priorities.</p>
                </div>
                {analysis && (
                  <button
                    className="button button-secondary"
                    onClick={() => loadAnalysis(analysis.analysis_id)}
                    disabled={checking}
                  >
                    {checking ? <LoaderCircle className="spin" size={16} /> : <RefreshCw size={16} />} Refresh
                    summary
                  </button>
                )}
              </div>

              <form className="scan-card" onSubmit={runAnalysis}>
                <div className="scan-icon">
                  <Github size={22} />
                </div>
                <div className="scan-fields">
                  <label htmlFor="repo-url">Analyze a GitHub repository</label>
                  <div className="scan-input-row">
                    <input
                      id="repo-url"
                      type="url"
                      placeholder="https://github.com/owner/repository"
                      value={repositoryUrl}
                      onChange={(e) => setRepositoryUrl(e.target.value)}
                      disabled={loading}
                    />
                    <button
                      className="button button-primary"
                      type="submit"
                      disabled={loading || apiOnline === false}
                    >
                      {loading ? (
                        <>
                          <LoaderCircle size={16} className="spin" /> Scanning repository…
                        </>
                      ) : (
                        <>
                          <Activity size={16} /> {analysis ? 'Run new scan' : 'Analyze repository'}{' '}
                          <ArrowRight size={16} />
                        </>
                      )}
                    </button>
                  </div>
                  <div className="field-hint">
                    <CircleHelp size={13} /> Public GitHub repositories · npm lockfiles supported for resolved
                    dependency graphs
                  </div>
                </div>
              </form>

              {error && (
                <div className="alert alert-error">
                  <AlertCircle size={17} />
                  <div>
                    <b>We couldn't complete that request</b>
                    <p>{error}</p>
                    {/not found|expired/i.test(error) && analysisId && (
                      <button className="text-button" onClick={forgetAnalysis}>
                        Start a new analysis
                      </button>
                    )}
                  </div>
                  <button className="alert-close" onClick={() => setError('')} aria-label="Dismiss">
                    <X size={16} />
                  </button>
                </div>
              )}

              {!analysis && (
                <div className="welcome-panel">
                  <div className="welcome-art">
                    <div className="art-orbit orbit-one" />
                    <div className="art-orbit orbit-two" />
                    <div className="art-core">
                      <ShieldCheck size={39} />
                    </div>
                    <div className="art-chip chip-a">
                      <Package size={15} />
                    </div>
                    <div className="art-chip chip-b">
                      <GitBranch size={15} />
                    </div>
                    <div className="art-chip chip-c">
                      <ShieldAlert size={15} />
                    </div>
                  </div>
                  <div className="welcome-copy">
                    <div className="eyebrow">YOUR SECURITY WORKSPACE</div>
                    <h2>See the risk hiding in your dependencies.</h2>
                    <p>
                      Paste a repository URL above to map npm dependencies, inspect known OSV advisories,
                      explore dependency relationships, and export a CycloneDX SBOM.
                    </p>
                    <div className="welcome-points">
                      <span>
                        <Check size={14} /> Dependency inventory
                      </span>
                      <span>
                        <Check size={14} /> Vulnerability findings
                      </span>
                      <span>
                        <Check size={14} /> SBOM export
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {analysis && (
                <Overview
                  analysis={analysis}
                  onNavigate={setTab}
                  onDownload={() => downloadSbom(analysis.analysis_id, setError)}
                />
              )}
            </>
          )}

          {analysis && tab === 'Projects' && <ProjectsView id={analysis.analysis_id} />}
          {analysis && tab === 'Packages' && <PackagesView id={analysis.analysis_id} />}
          {analysis && tab === 'Vulnerabilities' && (
            <VulnerabilitiesView id={analysis.analysis_id} onError={setError} />
          )}
          {analysis && tab === 'Recommendations' && <RecommendationsView id={analysis.analysis_id} />}
          {analysis && tab === 'Dependency graph' && <GraphView id={analysis.analysis_id} />}

          {analysis && (
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
          )}
        </div>
      </main>
    </div>
  )
}

function Overview({
  analysis,
  onNavigate,
  onDownload,
}: {
  analysis: Analysis
  onNavigate: (tab: Tab) => void
  onDownload: () => void
}) {
  const summary = analysis.summary || {}
  const warningList = Array.isArray(analysis.analysis_metadata?.warnings)
    ? (analysis.analysis_metadata.warnings as Array<string | { message?: string }>)
    : []
  const isComplete = analysis.status === 'complete'
  const statusText = isComplete ? 'Analysis complete' : 'Partial analysis'
  const repoUrl = analysis.repository?.url || ''

  return (
    <>
      <div className={`scan-status-banner ${isComplete ? 'status-complete' : 'status-partial'}`}>
        <div className="status-banner-icon">
          {isComplete ? <ShieldCheck size={19} /> : <AlertTriangle size={19} />}
        </div>
        <div className="status-banner-copy">
          <b>{statusText}</b>
          <span>
            {isComplete
              ? 'Inventory and vulnerability analysis stages reported complete.'
              : 'Some coverage is incomplete. Review warnings before treating this as a full assessment.'}
          </span>
        </div>
        <span className={`pill ${isComplete ? 'pill-green' : 'pill-amber'}`}>
          {analysis.status || 'unknown'}
        </span>
      </div>

      <div className="repo-title-row">
        <div className="repo-large-icon">
          <Github size={22} />
        </div>
        <div className="repo-title">
          <h2>
            {analysis.repository?.owner && analysis.repository?.name
              ? `${analysis.repository.owner}/${analysis.repository.name}`
              : repoUrl || 'Analyzed repository'}
          </h2>
          <div className="repo-meta">
            <span>
              <GitBranch size={13} /> {analysis.repository?.default_branch || 'default branch'}
            </span>
            {analysis.repository?.commit_sha && (
              <span className="commit-chip">{analysis.repository.commit_sha.slice(0, 7)}</span>
            )}
            <span>
              Scanned {analysis.created_at ? new Date(analysis.created_at).toLocaleString() : 'recently'}
            </span>
            {repoUrl && (
              <a href={repoUrl} target="_blank" rel="noreferrer">
                View repository <ExternalLink size={12} />
              </a>
            )}
          </div>
        </div>
        <button className="button button-secondary" onClick={onDownload}>
          <ArrowDownToLine size={16} /> Export SBOM
        </button>
      </div>

      <div className="section-title-row">
        <div>
          <h3>Inventory at a glance</h3>
          <p>Counts reflect this repository snapshot.</p>
        </div>
        <span className="muted-caption">SCAN SUMMARY</span>
      </div>

      <div className="metric-grid">
        <Metric
          icon={<Boxes size={18} />}
          label="Projects discovered"
          value={summary.projects_discovered}
          sub="Manifest-based projects"
          tone="blue"
        />
        <Metric
          icon={<Package size={18} />}
          label="Packages inventoried"
          value={summary.total_packages}
          sub={`${n(summary.direct_packages)} direct · ${n(summary.transitive_packages)} transitive`}
          tone="violet"
        />
        <Metric
          icon={<ShieldAlert size={18} />}
          label="Vulnerability findings"
          value={summary.vulnerabilities_found}
          sub={`${n(summary.unique_advisories_found)} unique advisories`}
          tone="red"
        />
        <Metric
          icon={<GitBranch size={18} />}
          label="Dependency edges"
          value={summary.dependency_edges}
          sub="Resolved relationships"
          tone="teal"
        />
      </div>

      <div className="overview-grid">
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h3>Vulnerability posture</h3>
              <p>Known advisory findings from OSV</p>
            </div>
            <span className={`risk-chip risk-${String(summary.risk_level || 'unknown').toLowerCase()}`}>
              {String(summary.risk_level || 'Unknown risk')}
            </span>
          </div>
          <div className="vuln-total">
            <strong>{n(summary.vulnerabilities_found)}</strong>
            <span>finding instances</span>
          </div>
          <div className="advisory-note">
            <ShieldAlert size={16} />
            <span>
              A single advisory can affect multiple installed package instances. Finding count and unique
              advisory count are intentionally different.
            </span>
          </div>
          <button className="button button-secondary full-width" onClick={() => onNavigate('Vulnerabilities')}>
            Review vulnerability findings <ArrowRight size={15} />
          </button>
        </section>

        <section className="panel">
          <div className="panel-heading">
            <div>
              <h3>Analysis coverage</h3>
              <p>What this scan could resolve</p>
            </div>
            <FileCheck2 size={18} className="panel-heading-icon" />
          </div>
          <CoverageRow
            label="Projects with resolved graph"
            value={summary.projects_with_resolved_graph}
            total={summary.projects_discovered}
          />
          <CoverageRow
            label="Manifests found"
            value={summary.manifests_found}
            total={summary.projects_discovered}
          />
          <CoverageRow label="Lockfiles found" value={summary.lockfiles_found} />
          <div className="coverage-note">
            <CircleHelp size={15} />
            <span>Lockfiles without a matching manifest are not silently assigned to a project.</span>
          </div>
          <button className="button button-quiet full-width" onClick={() => onNavigate('Projects')}>
            Inspect projects <ArrowRight size={15} />
          </button>
        </section>
      </div>

      {warningList.length > 0 && (
        <section className="panel warning-panel">
          <div className="panel-heading">
            <div className="warning-heading">
              <AlertTriangle size={18} />
              <div>
                <h3>Coverage warnings</h3>
                <p>Resolve these to improve confidence in the results.</p>
              </div>
            </div>
            <span className="warning-count">
              {warningList.length} {warningList.length === 1 ? 'warning' : 'warnings'}
            </span>
          </div>
          <ul className="warning-list">
            {warningList.map((w, i) => (
              <li key={i}>{typeof w === 'string' ? w : w.message || JSON.stringify(w)}</li>
            ))}
          </ul>
        </section>
      )}

      <div className="quick-actions">
        <button onClick={() => onNavigate('Packages')}>
          <span className="quick-icon quick-violet">
            <Package size={18} />
          </span>
          <span>
            <b>Explore packages</b>
            <small>Search the resolved inventory</small>
          </span>
          <ArrowRight size={16} />
        </button>
        <button onClick={() => onNavigate('Recommendations')}>
          <span className="quick-icon quick-green">
            <Sparkles size={18} />
          </span>
          <span>
            <b>Review remediation</b>
            <small>Find suggested package updates</small>
          </span>
          <ArrowRight size={16} />
        </button>
        <button onClick={() => onNavigate('Dependency graph')}>
          <span className="quick-icon quick-blue">
            <GitBranch size={18} />
          </span>
          <span>
            <b>Trace dependencies</b>
            <small>Inspect a package neighborhood</small>
          </span>
          <ArrowRight size={16} />
        </button>
      </div>
    </>
  )
}

function Metric({
  icon,
  label,
  value,
  sub,
  tone,
}: {
  icon: React.ReactNode
  label: string
  value: unknown
  sub: string
  tone: string
}) {
  return (
    <div className="metric-card">
      <div className={`metric-icon tone-${tone}`}>{icon}</div>
      <div className="metric-label">{label}</div>
      <div className="metric-value">{n(value)}</div>
      <div className="metric-sub">{sub}</div>
    </div>
  )
}

function CoverageRow({ label, value, total }: { label: string; value: unknown; total?: unknown }) {
  const number = typeof value === 'number' ? value : 0
  const denom = typeof total === 'number' && total > 0 ? total : number
  const pct = denom > 0 ? Math.min(100, (number / denom) * 100) : 0
  return (
    <div className="coverage-row">
      <div className="coverage-label">
        <span>{label}</span>
        <b>
          {n(value)}
          {typeof total === 'number' ? ` / ${n(total)}` : ''}
        </b>
      </div>
      <div className="progress-track">
        <div className="progress-value" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function EmptyState({ title, body, action }: { title: string; body: string; action: () => void }) {
  return (
    <div className="empty-state">
      <div className="empty-icon">
        <Package size={23} />
      </div>
      <h2>{title}</h2>
      <p>{body}</p>
      <button className="button button-primary" onClick={action}>
        Go to overview <ArrowRight size={15} />
      </button>
    </div>
  )
}

function ResourceHeader({
  eyebrow,
  title,
  body,
  total,
  action,
}: {
  eyebrow: string
  title: string
  body: string
  total?: number
  action?: React.ReactNode
}) {
  return (
    <div className="page-heading resource-heading">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{body}</p>
      </div>
      <div className="resource-heading-right">
        {total !== undefined && <span className="total-badge">{n(total)} total</span>}
        {action}
      </div>
    </div>
  )
}

function SearchBox({
  value,
  onChange,
  placeholder = 'Search…',
}: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
}) {
  return (
    <label className="search-box">
      <Search size={16} />
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} />
      {value && (
        <button type="button" onClick={() => onChange('')} aria-label="Clear search">
          <X size={14} />
        </button>
      )}
    </label>
  )
}

function useResource<T>(id: string, path: string, query: string, extra = '') {
  const [page, setPage] = useState<Page<T> | null>(null)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    setOffset(0)
  }, [query, extra, id])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    request<Page<T>>(
      `/analyses/${encodeURIComponent(id)}/${path}?${qs({
        offset,
        limit: 25,
        q: query || undefined,
        ...Object.fromEntries(new URLSearchParams(extra)),
      })}`,
    )
      .then((data) => {
        if (!cancelled) setPage(data)
      })
      .catch((e) => {
        if (!cancelled) setError(errorText(e))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [id, path, offset, query, extra])

  return { page, offset, setOffset, loading, error }
}

function Pagination({
  page,
  offset,
  setOffset,
}: {
  page: Page<unknown> | null
  offset: number
  setOffset: (n: number) => void
}) {
  if (!page) return null
  const p = page.pagination
  return (
    <div className="pagination">
      <span>
        Showing {p.total === 0 ? 0 : offset + 1}–{Math.min(offset + p.limit, p.total)} of {n(p.total)}
      </span>
      <div>
        <button
          className="button button-secondary button-small"
          disabled={offset === 0}
          onClick={() => setOffset(Math.max(0, offset - p.limit))}
        >
          <ArrowLeft size={14} /> Previous
        </button>
        <button
          className="button button-secondary button-small"
          disabled={!p.has_more}
          onClick={() => setOffset(offset + p.limit)}
        >
          Next <ArrowRight size={14} />
        </button>
      </div>
    </div>
  )
}

function TableState({ loading, error, empty }: { loading: boolean; error: string; empty: boolean }) {
  if (loading)
    return (
      <div className="table-state">
        <LoaderCircle size={20} className="spin" /> Loading results…
      </div>
    )
  if (error)
    return (
      <div className="table-state table-error">
        <AlertCircle size={18} />
        {error}
      </div>
    )
  if (empty) return <div className="table-state">No matching results. Try changing your search or filters.</div>
  return null
}

function ProjectsView({ id }: { id: string }) {
  const [query, setQuery] = useState('')
  const q = useResource<Project>(id, 'projects', query)
  const items = q.page?.items || []

  return (
    <>
      <ResourceHeader
        eyebrow="INVENTORY"
        title="Projects"
        body="Discovered manifests and the lockfiles used to resolve each project."
        total={q.page?.pagination.total}
      />
      <div className="toolbar">
        <SearchBox value={query} onChange={setQuery} placeholder="Search project name or path…" />
      </div>
      <div className="table-card">
        <TableState
          loading={q.loading}
          error={q.error}
          empty={!q.loading && !q.error && items.length === 0}
        />
        {items.length > 0 && (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Project</th>
                  <th>Manifest</th>
                  <th>Lockfile</th>
                  <th>Resolved graph</th>
                  <th>Direct declarations</th>
                </tr>
              </thead>
              <tbody>
                {items.map((p, i) => (
                  <tr key={`${p.path}-${i}`}>
                    <td>
                      <div className="cell-main">{p.name || p.path || 'Unnamed project'}</div>
                      <div className="cell-sub">{p.path || '—'}</div>
                    </td>
                    <td className="path-cell">{p.manifest_path || '—'}</td>
                    <td className="path-cell">{p.lockfile_path || <span className="muted">Not found</span>}</td>
                    <td>
                      <span className={`pill ${p.has_resolved_graph ? 'pill-green' : 'pill-amber'}`}>
                        {p.has_resolved_graph ? 'Resolved' : 'Unavailable'}
                      </span>
                    </td>
                    <td>{n(p.direct_dependencies?.length ?? 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      <Pagination page={q.page as Page<unknown> | null} offset={q.offset} setOffset={q.setOffset} />
    </>
  )
}

function PackagesView({ id }: { id: string }) {
  const [query, setQuery] = useState('')
  const [direct, setDirect] = useState('')
  const [dev, setDev] = useState('')
  const extra = useMemo(
    () =>
      qs({
        direct: direct === '' ? undefined : direct === 'true',
        is_dev: dev === '' ? undefined : dev === 'true',
      }),
    [direct, dev],
  )
  const q = useResource<PackageItem>(id, 'packages', query, extra)
  const items = q.page?.items || []

  return (
    <>
      <ResourceHeader
        eyebrow="INVENTORY"
        title="Packages"
        body="Search resolved package instances across project lockfiles. Identical versions in different lockfiles remain separate instances."
        total={q.page?.pagination.total}
      />
      <div className="toolbar">
        <SearchBox value={query} onChange={setQuery} placeholder="Search package, version, or path…" />
        <select className="filter-select" value={direct} onChange={(e) => setDirect(e.target.value)}>
          <option value="">All dependency types</option>
          <option value="true">Direct only</option>
          <option value="false">Transitive only</option>
        </select>
        <select className="filter-select" value={dev} onChange={(e) => setDev(e.target.value)}>
          <option value="">All scopes</option>
          <option value="true">Development</option>
          <option value="false">Non-development</option>
        </select>
      </div>
      <div className="table-card">
        <TableState
          loading={q.loading}
          error={q.error}
          empty={!q.loading && !q.error && items.length === 0}
        />
        {items.length > 0 && (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Package</th>
                  <th>Version</th>
                  <th>Type</th>
                  <th>Scope</th>
                  <th>Project lockfile</th>
                </tr>
              </thead>
              <tbody>
                {items.map((p, i) => (
                  <tr key={`${p.id}-${i}`}>
                    <td>
                      <div className="cell-main">{p.name}</div>
                      <div className="cell-sub mono">{p.id}</div>
                    </td>
                    <td>
                      <code className="version-code">{p.version || '—'}</code>
                    </td>
                    <td>
                      <span className={`pill ${p.is_direct ? 'pill-blue' : 'pill-neutral'}`}>
                        {p.is_direct ? 'Direct' : 'Transitive'}
                      </span>
                    </td>
                    <td>
                      {p.is_dev ? (
                        <span className="pill pill-violet">Development</span>
                      ) : (
                        <span className="muted">Production / other</span>
                      )}
                    </td>
                    <td className="path-cell">{p.lockfile || p.path || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      <Pagination page={q.page as Page<unknown> | null} offset={q.offset} setOffset={q.setOffset} />
    </>
  )
}

function VulnerabilitiesView({ id, onError }: { id: string; onError: (e: string) => void }) {
  const [query, setQuery] = useState('')
  const [severity, setSeverity] = useState('')
  const [hasFix, setHasFix] = useState('')
  const [selected, setSelected] = useState<Vulnerability | null>(null)
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const extra = useMemo(
    () =>
      qs({
        severity: severity || undefined,
        has_fix: hasFix === '' ? undefined : hasFix === 'true',
      }),
    [severity, hasFix],
  )
  const q = useResource<Vulnerability>(id, 'vulnerabilities', query, extra)
  const items = q.page?.items || []

  const openDetail = async (v: Vulnerability) => {
    setSelected(v)
    setDetail(null)
    setDetailLoading(true)
    try {
      setDetail(
        await request<Record<string, unknown>>(
          v.links?.detail ||
            `/analyses/${encodeURIComponent(id)}/vulnerabilities/${encodeURIComponent(v.finding_id)}`,
        ),
      )
    } catch (e) {
      onError(errorText(e))
    } finally {
      setDetailLoading(false)
    }
  }

  return (
    <>
      <ResourceHeader
        eyebrow="SECURITY FINDINGS"
        title="Vulnerabilities"
        body="OSV advisory findings mapped to installed package instances. A finding does not by itself prove runtime exploitability."
        total={q.page?.pagination.total}
      />
      <div className="toolbar">
        <SearchBox value={query} onChange={setQuery} placeholder="Search advisory, package, or summary…" />
        <select className="filter-select" value={severity} onChange={(e) => setSeverity(e.target.value)}>
          <option value="">All severities</option>
          {['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'UNKNOWN'].map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select className="filter-select" value={hasFix} onChange={(e) => setHasFix(e.target.value)}>
          <option value="">Fix availability</option>
          <option value="true">Fix available</option>
          <option value="false">No known fix</option>
        </select>
      </div>

      <div className="table-card">
        <TableState
          loading={q.loading}
          error={q.error}
          empty={!q.loading && !q.error && items.length === 0}
        />
        {items.length > 0 && (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Advisory</th>
                  <th>Severity</th>
                  <th>Affected package</th>
                  <th>Installed</th>
                  <th>Known fix</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {items.map((v) => (
                  <tr key={v.finding_id} className="clickable-row" onClick={() => void openDetail(v)}>
                    <td>
                      <div className="cell-main">{v.id || 'Unknown advisory'}</div>
                      <div className="cell-sub">{(v.aliases || []).slice(0, 2).join(' · ')}</div>
                    </td>
                    <td>
                      <span className={severityClass(v.severity)}>{v.severity || 'UNKNOWN'}</span>
                      {v.cvss_score != null && <div className="cell-sub">CVSS {v.cvss_score}</div>}
                    </td>
                    <td>
                      <div className="cell-main">{v.package_name || '—'}</div>
                      <div className="cell-sub">{v.package_path || v.lockfile || '—'}</div>
                    </td>
                    <td>
                      <code className="version-code">{v.installed_version || '—'}</code>
                    </td>
                    <td>
                      {v.fixed_versions?.length ? (
                        <span className="pill pill-green">{v.fixed_versions.join(', ')}</span>
                      ) : (
                        <span className="muted">Not listed</span>
                      )}
                    </td>
                    <td>
                      <ArrowRight size={15} className="row-arrow" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      <Pagination page={q.page as Page<unknown> | null} offset={q.offset} setOffset={q.setOffset} />

      {selected && (
        <div
          className="modal-backdrop"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) setSelected(null)
          }}
        >
          <section className="detail-modal">
            <div className="modal-heading">
              <div>
                <div className="eyebrow">ADVISORY DETAIL</div>
                <h2>{selected.id || 'Vulnerability finding'}</h2>
              </div>
              <button className="icon-button" onClick={() => setSelected(null)}>
                <X size={18} />
              </button>
            </div>
            {detailLoading ? (
              <div className="table-state">
                <LoaderCircle size={18} className="spin" /> Loading advisory detail…
              </div>
            ) : (
              detail && (
                <>
                  <div className="detail-summary">
                    <span className={severityClass(String(detail.severity || selected.severity))}>
                      {String(detail.severity || selected.severity || 'UNKNOWN')}
                    </span>
                    <h3>{String(detail.summary || selected.summary || 'No summary supplied by OSV')}</h3>
                    <p>
                      {String(detail.package_name || selected.package_name)} @{' '}
                      {String(detail.installed_version || selected.installed_version)}
                    </p>
                  </div>
                  <DetailField label="Advisory ID" value={detail.id} />
                  <DetailField
                    label="Fixed versions"
                    value={
                      Array.isArray(detail.fixed_versions) && detail.fixed_versions.length
                        ? detail.fixed_versions.join(', ')
                        : 'No fixed version listed by source'
                    }
                  />
                  <DetailField label="Affected package path" value={detail.package_path || selected.package_path} />
                  <DetailField label="Details" value={detail.details} />
                  <DetailField
                    label="References"
                    value={
                      Array.isArray(detail.references)
                        ? (detail.references as Array<Record<string, unknown>>)
                            .map((r) => String(r.url || ''))
                            .filter(Boolean)
                            .join('\n')
                        : undefined
                    }
                  />
                  <p className="detail-disclaimer">
                    OSV data reflects published advisories. Assess whether the affected code path and package
                    usage make this relevant to your application.
                  </p>
                </>
              )
            )}
          </section>
        </div>
      )}
    </>
  )
}

function DetailField({ label, value }: { label: string; value: unknown }) {
  if (value == null || value === '') return null
  return (
    <div className="detail-field">
      <span>{label}</span>
      <div>{String(value)}</div>
    </div>
  )
}

function RecommendationsView({ id }: { id: string }) {
  const [query, setQuery] = useState('')
  const [hasFix, setHasFix] = useState('')
  const extra = useMemo(() => qs({ has_fix: hasFix === '' ? undefined : hasFix === 'true' }), [hasFix])
  const q = useResource<Recommendation>(id, 'recommendations', query, extra)
  const items = q.page?.items || []

  return (
    <>
      <ResourceHeader
        eyebrow="REMEDIATION"
        title="Recommendations"
        body="Prioritize updates suggested by the analysis. Verify compatibility and regression-test changes before merging."
        total={q.page?.pagination.total}
      />
      <div className="toolbar">
        <SearchBox value={query} onChange={setQuery} placeholder="Search package or recommendation…" />
        <select className="filter-select" value={hasFix} onChange={(e) => setHasFix(e.target.value)}>
          <option value="">All recommendations</option>
          <option value="true">Fix available</option>
          <option value="false">No fix listed</option>
        </select>
      </div>
      <div className="recommendation-list">
        <TableState
          loading={q.loading}
          error={q.error}
          empty={!q.loading && !q.error && items.length === 0}
        />
        {items.map((r, i) => (
          <article className="recommendation-card" key={`${r.package_name}-${r.installed_version}-${i}`}>
            <div className="recommendation-icon">
              <Sparkles size={18} />
            </div>
            <div className="recommendation-content">
              <div className="recommendation-title">
                <h3>{r.package_name || 'Package update'}</h3>
                <span className="version-code">{String(r.installed_version || 'current version')}</span>
                <ArrowRight size={14} />
                <span className="fix-version">
                  {r.fixed_versions?.length ? r.fixed_versions.join(', ') : 'No fixed version listed'}
                </span>
              </div>
              <p>
                {String(
                  r.recommendation ||
                    'Review the advisory and update to a patched version if a compatible release is available.',
                )}
              </p>
              <div className="recommendation-meta">
                <span>
                  <ShieldAlert size={13} />
                  {n(r.vulnerability_ids?.length || 0)} linked advisories
                </span>
                {r.package_id && <span className="mono">{r.package_id}</span>}
              </div>
            </div>
          </article>
        ))}
      </div>
      <Pagination page={q.page as Page<unknown> | null} offset={q.offset} setOffset={q.setOffset} />
    </>
  )
}

function GraphView({ id }: { id: string }) {
  const [query, setQuery] = useState('')
  const [selectedId, setSelectedId] = useState('')
  const [depth, setDepth] = useState('1')
  const [direction, setDirection] = useState('both')
  const [graph, setGraph] = useState<Graph | null>(null)
  const [loadingGraph, setLoadingGraph] = useState(false)
  const [graphError, setGraphError] = useState('')

  const p = useResource<PackageItem>(id, 'packages', query)
  const packages = p.page?.items || []

  useEffect(() => {
    if (!selectedId && packages.length) setSelectedId(packages[0].id)
  }, [packages, selectedId])

  const fetchGraph = async () => {
    if (!selectedId) return
    setLoadingGraph(true)
    setGraphError('')
    try {
      setGraph(
        await request<Graph>(
          `/analyses/${encodeURIComponent(id)}/graph?${qs({
            package_id: selectedId,
            depth: Number(depth),
            direction,
          })}`,
        ),
      )
    } catch (e) {
      setGraph(null)
      setGraphError(errorText(e))
    } finally {
      setLoadingGraph(false)
    }
  }

  useEffect(() => {
    // Depth/direction changes intentionally wait for the "Load graph" button.
    if (selectedId) void fetchGraph()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId])

  const nodes = graph?.nodes || []
  const edges = graph?.edges || []

  const positions = useMemo(() => {
    const centerX = 50
    const centerY = 50
    const radius = nodes.length <= 1 ? 0 : 35
    return nodes.map((node, i) => {
      const angle = (2 * Math.PI * i) / Math.max(nodes.length, 1) - Math.PI / 2
      return { node, x: centerX + Math.cos(angle) * radius, y: centerY + Math.sin(angle) * radius }
    })
  }, [nodes])

  const posMap = useMemo(() => new Map(positions.map((pos) => [pos.node.id, pos])), [positions])

  return (
    <>
      <ResourceHeader
        eyebrow="DEPENDENCY EXPLORER"
        title="Dependency graph"
        body="Inspect a bounded neighborhood around one resolved package instance. Edges show lockfile relationships, not proof of runtime exploitability."
      />
      <div className="graph-controls panel">
        <div className="graph-package-field">
          <label>Root package</label>
          <SearchBox value={query} onChange={setQuery} placeholder="Filter package choices…" />
          <select className="wide-select" value={selectedId} onChange={(e) => setSelectedId(e.target.value)}>
            <option value="">Select a package</option>
            {packages.map((pkg) => (
              <option key={pkg.id} value={pkg.id}>
                {pkg.name}@{pkg.version} · {pkg.lockfile || pkg.path || ''}
              </option>
            ))}
          </select>
          <span className="field-hint">
            Choose from the current page of package search results; type above to narrow the choices.
          </span>
        </div>
        <div className="graph-option">
          <label>Depth</label>
          <select className="filter-select" value={depth} onChange={(e) => setDepth(e.target.value)}>
            {[0, 1, 2, 3].map((d) => (
              <option key={d} value={d}>
                {d} hop{d === 1 ? '' : 's'}
              </option>
            ))}
          </select>
        </div>
        <div className="graph-option">
          <label>Direction</label>
          <select className="filter-select" value={direction} onChange={(e) => setDirection(e.target.value)}>
            <option value="both">Both</option>
            <option value="in">Dependencies of</option>
            <option value="out">Dependents of</option>
          </select>
        </div>
        <button
          className="button button-primary graph-submit"
          onClick={() => void fetchGraph()}
          disabled={!selectedId || loadingGraph}
        >
          {loadingGraph ? <LoaderCircle size={15} className="spin" /> : <GitBranch size={15} />} Load graph
        </button>
      </div>

      {graphError && (
        <div className="alert alert-error">
          <AlertCircle size={17} />
          {graphError}
        </div>
      )}

      <section className="panel graph-panel">
        <div className="panel-heading">
          <div>
            <h3>Package neighborhood</h3>
            <p>
              {nodes.length} nodes · {edges.length} edges
            </p>
          </div>
          <div className="graph-legend">
            <span>
              <i className="legend-root" /> Selected package
            </span>
            <span>
              <i /> Related package
            </span>
          </div>
        </div>

        {loadingGraph ? (
          <div className="table-state">
            <LoaderCircle size={20} className="spin" /> Building neighborhood…
          </div>
        ) : graph && nodes.length ? (
          <>
            <div className="graph-canvas">
              <svg viewBox="0 0 100 100" role="img" aria-label="Dependency neighborhood graph">
                {edges.map((edge, i) => {
                  const a = posMap.get(edge.source)
                  const b = posMap.get(edge.target)
                  if (!a || !b) return null
                  return (
                    <g key={`${edge.source}-${edge.target}-${i}`}>
                      <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} className="graph-edge" />
                      <title>{`${a.node.name || a.node.id} → ${b.node.name || b.node.id} (${edge.dependency_type || 'dependency'})`}</title>
                    </g>
                  )
                })}
                {positions.map(({ node, x, y }) => {
                  const root = node.id === graph.root_package_id
                  return (
                    <g key={node.id} className="graph-node">
                      <circle
                        cx={x}
                        cy={y}
                        r={root ? 3.7 : 2.8}
                        className={root ? 'graph-node-root' : 'graph-node-circle'}
                      />
                      <text x={x} y={y + (root ? 7 : 6)} textAnchor="middle">
                        {String(node.name || node.id).slice(0, 20)}
                      </text>
                      <title>{`${node.name || node.id}${node.version ? `@${node.version}` : ''}`}</title>
                    </g>
                  )
                })}
              </svg>
            </div>
            <div className="graph-node-list">
              {nodes.map((node) => (
                <div
                  key={node.id}
                  className={`graph-node-row ${node.id === graph.root_package_id ? 'root-row' : ''}`}
                >
                  <span className="node-dot" />
                  <div>
                    <b>{String(node.name || node.id)}</b>
                    <small>{String(node.id)}</small>
                  </div>
                  <code>{String(node.version || '')}</code>
                </div>
              ))}
            </div>
          </>
        ) : (
          <div className="table-state">Choose a package and load its dependency neighborhood.</div>
        )}
      </section>
    </>
  )
}

async function downloadSbom(id: string, setError: (e: string) => void) {
  try {
    const response = await fetch(apiUrl(`/analyses/${encodeURIComponent(id)}/sbom`))
    if (!response.ok) {
      let message = `${response.status} ${response.statusText}`
      try {
        const body = await response.json()
        message = body.detail || message
      } catch {
        /* response body was not JSON; keep the status text */
      }
      throw new Error(message)
    }
    const blob = await response.blob()
    const disposition = response.headers.get('content-disposition') || ''
    const filename = disposition.match(/filename="?([^";]+)"?/i)?.[1] || `supplylens-${id}.cdx.json`
    const href = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = href
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(href)
  } catch (e) {
    setError(errorText(e))
  }
}