import type { ReactNode } from 'react'
import { RotateCcw } from 'lucide-react'
import { SearchBox } from './SearchBox'

/** Search box plus filter controls, with a reset button once anything is applied. */
export function FilterBar({
  search,
  onSearchChange,
  searchPlaceholder,
  isFiltered,
  onReset,
  children,
}: {
  search: string
  onSearchChange: (value: string) => void
  searchPlaceholder: string
  isFiltered: boolean
  onReset: () => void
  children?: ReactNode
}) {
  return (
    <div className="filter-bar">
      <SearchBox value={search} onChange={onSearchChange} placeholder={searchPlaceholder} />
      {children}
      {isFiltered && (
        <button type="button" className="btn btn-ghost btn-sm" onClick={onReset}>
          <RotateCcw size={14} /> Reset
        </button>
      )}
    </div>
  )
}
