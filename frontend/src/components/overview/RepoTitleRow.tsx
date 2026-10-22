import { ArrowDownToLine, ExternalLink, GitBranch } from 'lucide-react'
import type { Analysis } from '../../api'
import { Github } from '../icons/Github'

export function RepoTitleRow({ analysis, onDownload }: { analysis: Analysis; onDownload: () => void }) {
  const repoUrl = analysis.repository?.url || ''
  return (
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
  )
}
