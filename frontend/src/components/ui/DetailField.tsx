export function DetailField({ label, value }: { label: string; value: unknown }) {
  if (value == null || value === '') return null
  return (
    <div className="detail-field">
      <span>{label}</span>
      <div>{String(value)}</div>
    </div>
  )
}
