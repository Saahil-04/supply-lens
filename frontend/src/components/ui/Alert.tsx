import type { ReactNode } from 'react'
import { AlertCircle, AlertTriangle, CircleCheck, Info, X, type LucideIcon } from 'lucide-react'

export type AlertTone = 'error' | 'warning' | 'info' | 'success'

const ICONS: Record<AlertTone, LucideIcon> = {
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
  success: CircleCheck,
}

export function Alert({
  tone = 'info',
  title,
  children,
  action,
  onDismiss,
}: {
  tone?: AlertTone
  title?: string
  children?: ReactNode
  action?: ReactNode
  onDismiss?: () => void
}) {
  const Icon = ICONS[tone]
  return (
    <div className={`alert alert-${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
      <Icon size={18} className="alert-icon" aria-hidden="true" />
      <div className="alert-body">
        {title && <strong>{title}</strong>}
        {children && <p>{children}</p>}
        {action}
      </div>
      {onDismiss && (
        <button type="button" className="icon-button alert-dismiss" onClick={onDismiss} aria-label="Dismiss">
          <X size={16} />
        </button>
      )}
    </div>
  )
}
