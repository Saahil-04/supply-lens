import { AlertCircle, X } from 'lucide-react'

export function ErrorAlert({
  message,
  canRestart,
  onRestart,
  onDismiss,
}: {
  message: string
  /** Show the "Start a new analysis" action (only useful when a stored analysis id exists). */
  canRestart: boolean
  onRestart: () => void
  onDismiss: () => void
}) {
  return (
    <div className="alert alert-error">
      <AlertCircle size={17} />
      <div>
        <b>We couldn't complete that request</b>
        <p>{message}</p>
        {/not found|expired/i.test(message) && canRestart && (
          <button className="text-button" onClick={onRestart}>
            Start a new analysis
          </button>
        )}
      </div>
      <button className="alert-close" onClick={onDismiss} aria-label="Dismiss">
        <X size={16} />
      </button>
    </div>
  )
}
