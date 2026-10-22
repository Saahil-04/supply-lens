import { ArrowLeft, ArrowRight } from 'lucide-react'
import type { Page } from '../../api'
import { n } from '../../lib/format'

export function Pagination({
  page,
  offset,
  setOffset,
}: {
  page: Page<unknown> | null
  offset: number
  setOffset: (n: number) => void
}) {
  if (!page) return null
  const p = page.pagination
  return (
    <div className="pagination">
      <span>
        Showing {p.total === 0 ? 0 : offset + 1}–{Math.min(offset + p.limit, p.total)} of {n(p.total)}
      </span>
      <div>
        <button
          className="button button-secondary button-small"
          disabled={offset === 0}
          onClick={() => setOffset(Math.max(0, offset - p.limit))}
        >
          <ArrowLeft size={14} /> Previous
        </button>
        <button
          className="button button-secondary button-small"
          disabled={!p.has_more}
          onClick={() => setOffset(offset + p.limit)}
        >
          Next <ArrowRight size={14} />
        </button>
      </div>
    </div>
  )
}
