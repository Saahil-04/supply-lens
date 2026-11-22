import type { FormEvent } from 'react'
import { ArrowRight } from 'lucide-react'
import { Github } from '../icons/Github'
import { Spinner } from '../ui/Spinner'

type Props = {
  url: string
  onUrlChange: (url: string) => void
  includeReachability: boolean
  onIncludeReachabilityChange: (value: boolean) => void
  onSubmit: (event: FormEvent) => void
  running: boolean
  /** The service is known to be down, so submitting would fail. */
  disabled: boolean
  hasAnalysis: boolean
  variant?: 'hero' | 'compact'
}

export function AnalyzeForm({
  url,
  onUrlChange,
  includeReachability,
  onIncludeReachabilityChange,
  onSubmit,
  running,
  disabled,
  hasAnalysis,
  variant = 'compact',
}: Props) {
  return (
    <form className={`analyze-form analyze-${variant}`} onSubmit={onSubmit} noValidate>
      <label htmlFor="repository-url" className={variant === 'hero' ? 'sr-only' : 'field-label'}>
        {hasAnalysis ? 'Analyze another repository' : 'GitHub repository URL'}
      </label>
      <div className="analyze-row">
        <div className="input-group">
          <Github size={17} />
          <input
            id="repository-url"
            type="url"
            inputMode="url"
            autoComplete="off"
            spellCheck={false}
            placeholder="https://github.com/owner/repository"
            value={url}
            onChange={(event) => onUrlChange(event.target.value)}
            disabled={running}
          />
        </div>
        <button type="submit" className="btn btn-primary btn-lg" disabled={running || disabled}>
          {running ? (
            <>
              <Spinner /> Analyzing…
            </>
          ) : (
            <>
              {hasAnalysis ? 'Run new analysis' : 'Analyze repository'} <ArrowRight size={16} />
            </>
          )}
        </button>
      </div>

      <label className="check-row">
        <input
          type="checkbox"
          checked={includeReachability}
          onChange={(event) => onIncludeReachabilityChange(event.target.checked)}
          disabled={running}
        />
        <span>
          Check whether vulnerable packages are actually imported
          <small>Slower, because source files are downloaded.</small>
        </span>
      </label>

      {(running || variant === 'hero') && (
        <p className="form-hint" aria-live="polite">
          {running
            ? 'Large repositories can take a minute or more. Keep this tab open.'
            : 'Public GitHub repositories with npm or pnpm lockfiles are supported.'}
        </p>
      )}
    </form>
  )
}
