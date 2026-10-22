import type { FormEvent } from 'react'
import { Activity, ArrowRight, CircleHelp, LoaderCircle } from 'lucide-react'
import { Github } from '../icons/Github'

export function ScanForm({
  repositoryUrl,
  onUrlChange,
  onSubmit,
  loading,
  apiOnline,
  hasAnalysis,
}: {
  repositoryUrl: string
  onUrlChange: (url: string) => void
  onSubmit: (event: FormEvent) => void
  loading: boolean
  apiOnline: boolean | null
  hasAnalysis: boolean
}) {
  return (
    <form className="scan-card" onSubmit={onSubmit}>
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
            onChange={(e) => onUrlChange(e.target.value)}
            disabled={loading}
          />
          <button className="button button-primary" type="submit" disabled={loading || apiOnline === false}>
            {loading ? (
              <>
                <LoaderCircle size={16} className="spin" /> Scanning repository…
              </>
            ) : (
              <>
                <Activity size={16} /> {hasAnalysis ? 'Run new scan' : 'Analyze repository'}{' '}
                <ArrowRight size={16} />
              </>
            )}
          </button>
        </div>
        <div className="field-hint">
          <CircleHelp size={13} /> Public GitHub repositories · npm lockfiles supported for resolved dependency
          graphs
        </div>
      </div>
    </form>
  )
}
