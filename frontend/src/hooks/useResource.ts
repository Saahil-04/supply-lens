import { useCallback, useState } from 'react'
import { qs, type Page } from '../api'
import { useApi } from './useApi'

export const PAGE_SIZE = 25

type FilterValues = Record<string, string | number | boolean | undefined | null>

/** Paginated, searchable and filterable fetch of `/analyses/:id/:resource`. */
export function useResource<T>(
  analysisId: string,
  resource: string,
  { query = '', filters = {} }: { query?: string; filters?: FilterValues } = {},
) {
  const criteria = qs({ q: query, ...filters })

  // The offset belongs to one set of criteria; changing the search or a filter
  // starts from the first page again without a second request.
  const [paging, setPaging] = useState({ criteria, offset: 0 })
  const offset = paging.criteria === criteria ? paging.offset : 0
  const setOffset = useCallback((next: number) => setPaging({ criteria, offset: next }), [criteria])

  const { data: page, loading, error } = useApi<Page<T>>(
    `/analyses/${encodeURIComponent(analysisId)}/${resource}?${qs({ offset, limit: PAGE_SIZE })}&${criteria}`,
    { keepPrevious: true },
  )

  return {
    page,
    items: page?.items ?? [],
    total: page?.pagination.total,
    offset,
    setOffset,
    loading,
    error,
  }
}

export type Resource<T> = ReturnType<typeof useResource<T>>
