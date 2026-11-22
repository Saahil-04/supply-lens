import { ChevronLeft, ChevronRight } from 'lucide-react'
import type { Page } from '../../api'
import { formatNumber } from '../../lib/format'

export function Pagination({
  page,
  offset,
  onOffsetChange,
}: {
  page?: Page<unknown>
  offset: number
  onOffsetChange: (offset: number) => void
}) {
  if (!page || page.pagination.total === 0) return null
  const { limit, total, has_more: hasMore } = page.pagination

  return (
    <nav className="pagination" aria-label="Pagination">
      <span>
        Showing {formatNumber(offset + 1)}–{formatNumber(Math.min(offset + limit, total))} of {formatNumber(total)}
      </span>
      <div className="pagination-buttons">
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          disabled={offset === 0}
          onClick={() => onOffsetChange(Math.max(0, offset - limit))}
        >
          <ChevronLeft size={14} /> Previous
        </button>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          disabled={!hasMore}
          onClick={() => onOffsetChange(offset + limit)}
        >
          Next <ChevronRight size={14} />
        </button>
      </div>
    </nav>
  )
}
