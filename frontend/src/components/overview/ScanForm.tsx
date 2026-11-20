import type { FormEvent } from 'react'
import { Activity, ArrowRight, CircleHelp, LoaderCircle } from 'lucide-react'
import { Github } from '../icons/Github'

export function ScanForm({
  repositoryUrl,
  onUrlChange,
  includeReachability,
  onIncludeReachabilityChange,
  onSubmit,
  loading,
  apiOnline,
  hasAnalysis,
}: {
  repositoryUrl: string
  onUrlChange: (url: string) => void
  includeReachability: boolean
  onIncludeReachabilityChange: (value: boolean) => void
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
        <label className="check-row">
          <input
            type="checkbox"
            checked={includeReachability}
            onChange={(e) => onIncludeReachabilityChange(e.target.checked)}
            disabled={loading}
          />
          Check whether vulnerable packages are actually imported (slower: downloads source files)
        </label>
        <div className="field-hint">
          <CircleHelp size={13} /> Public GitHub repositories · npm and pnpm lockfiles supported
          {loading && ' · Large repositories can take a minute or more. Keep this tab open.'}
        </div>
      </div>
    </form>
  )
}
