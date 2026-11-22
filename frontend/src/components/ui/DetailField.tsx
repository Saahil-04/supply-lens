import type { ReactNode } from 'react'

/** Label/value row for detail views. Renders nothing for empty values. */
export function DetailField({
  label,
  children,
  mono = false,
}: {
  label: string
  children?: ReactNode
  mono?: boolean
}) {
  if (children == null || children === '' || children === false) return null
  return (
    <div className="detail-field">
      <dt>{label}</dt>
      <dd className={mono ? 'mono pre' : undefined}>{children}</dd>
    </div>
  )
}
