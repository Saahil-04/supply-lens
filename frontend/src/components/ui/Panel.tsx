import type { ReactNode } from 'react'

/** A titled surface. Use `flush` when the children draw their own padding (tables, canvases). */
export function Panel({
  title,
  description,
  action,
  flush = false,
  className = '',
  children,
}: {
  title?: string
  description?: ReactNode
  action?: ReactNode
  flush?: boolean
  className?: string
  children: ReactNode
}) {
  return (
    <section className={`panel ${className}`.trim()}>
      {(title || action) && (
        <header className="panel-header">
          <div>
            {title && <h2 className="panel-title">{title}</h2>}
            {description && <p className="panel-description">{description}</p>}
          </div>
          {action}
        </header>
      )}
      <div className={flush ? undefined : 'panel-body'}>{children}</div>
    </section>
  )
}
