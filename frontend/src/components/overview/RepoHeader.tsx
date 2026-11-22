import { Download, ExternalLink, GitBranch, RefreshCw } from 'lucide-react'
import type { Analysis } from '../../api'
import { formatDateTime } from '../../lib/format'
import { Github } from '../icons/Github'
import { Badge } from '../ui/Badge'
import { Spinner } from '../ui/Spinner'

type Props = {
  analysis: Analysis
  refreshing: boolean
  onRefresh: () => void
  onDownload: () => void
}

export function RepoHeader({ analysis, refreshing, onRefresh, onDownload }: Props) {
  const { repository } = analysis
  const complete = analysis.status === 'complete'
  const name =
    repository?.owner && repository.name ? `${repository.owner}/${repository.name}` : (repository?.url ?? 'Repository')

  return (
    <header className="repo-header">
      <span className="repo-header-icon">
        <Github size={22} />
      </span>
      <div className="repo-header-main">
        <div className="repo-header-title">
          <h1>{name}</h1>
          <Badge tone={complete ? 'success' : 'warning'}>{complete ? 'Analysis complete' : 'Partial analysis'}</Badge>
        </div>
        <div className="repo-meta">
          {repository?.default_branch && (
            <span>
              <GitBranch size={13} /> {repository.default_branch}
            </span>
          )}
          {repository?.commit_sha && <code>{repository.commit_sha.slice(0, 7)}</code>}
          {analysis.created_at && <span>Analyzed {formatDateTime(analysis.created_at)}</span>}
          {repository?.url && (
            <a href={repository.url} target="_blank" rel="noreferrer" className="link">
              View on GitHub <ExternalLink size={12} />
            </a>
          )}
        </div>
      </div>
      <div className="repo-header-actions">
        <button type="button" className="btn btn-secondary" onClick={onRefresh} disabled={refreshing}>
          {refreshing ? <Spinner /> : <RefreshCw size={15} />} Refresh
        </button>
        <button type="button" className="btn btn-primary" onClick={onDownload}>
          <Download size={15} /> Export SBOM
        </button>
      </div>
    </header>
  )
}
