import type { ReactNode } from 'react'
import { SearchX } from 'lucide-react'
import type { Page } from '../../api'
import type { Resource } from '../../hooks/useResource'
import { Alert } from './Alert'
import { EmptyState } from './EmptyState'
import { Pagination } from './Pagination'

function Skeleton() {
  return (
    <div className="skeleton-list" aria-busy="true" aria-label="Loading results">
      {Array.from({ length: 6 }, (_, i) => (
        <div key={i} className="skeleton-row">
          <span className="skeleton" style={{ width: `${28 + ((i * 17) % 30)}%` }} />
          <span className="skeleton" style={{ width: '12%' }} />
          <span className="skeleton" style={{ width: '18%' }} />
        </div>
      ))}
    </div>
  )
}

/**
 * Renders the loading, error, empty and loaded states of a paginated resource,
 * plus its pagination controls. `surface="card"` wraps the content in a card
 * (tables); `surface="plain"` leaves it bare (lists of cards).
 */
export function DataPanel<T>({
  resource,
  surface = 'card',
  children,
}: {
  resource: Resource<T>
  surface?: 'card' | 'plain'
  children: (items: T[]) => ReactNode
}) {
  const { items, page, loading, error, offset, setOffset } = resource
  const firstLoad = loading && !page

  let content: ReactNode
  if (error) {
    content = (
      <div className="data-state">
        <Alert tone="error" title="Could not load results">{error}</Alert>
      </div>
    )
  } else if (firstLoad) {
    content = <Skeleton />
  } else if (items.length === 0) {
    content = (
      <EmptyState icon={SearchX} title="No matching results" compact>
        Try a different search or adjust your filters.
      </EmptyState>
    )
  } else {
    content = children(items)
  }

  return (
    <>
      <div className={`data-panel data-${surface} ${loading && !firstLoad ? 'is-refreshing' : ''}`.trim()}>
        {content}
      </div>
      {!error && <Pagination page={page as Page<unknown> | undefined} offset={offset} onOffsetChange={setOffset} />}
    </>
  )
}
