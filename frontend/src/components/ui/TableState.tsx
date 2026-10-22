import { AlertCircle, LoaderCircle } from 'lucide-react'

export function TableState({ loading, error, empty }: { loading: boolean; error: string; empty: boolean }) {
  if (loading)
    return (
      <div className="table-state">
        <LoaderCircle size={20} className="spin" /> Loading results…
      </div>
    )
  if (error)
    return (
      <div className="table-state table-error">
        <AlertCircle size={18} />
        {error}
      </div>
    )
  if (empty) return <div className="table-state">No matching results. Try changing your search or filters.</div>
  return null
}
