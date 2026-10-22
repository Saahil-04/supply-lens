import { useEffect, useState } from 'react'
import { qs, request, type Page } from '../api'
import { errorText } from '../lib/format'

/** Paginated, searchable, filterable fetch of `/analyses/:id/:path`. */
export function useResource<T>(id: string, path: string, query: string, extra = '') {
  const [page, setPage] = useState<Page<T> | null>(null)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    setOffset(0)
  }, [query, extra, id])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    request<Page<T>>(
      `/analyses/${encodeURIComponent(id)}/${path}?${qs({
        offset,
        limit: 25,
        q: query || undefined,
        ...Object.fromEntries(new URLSearchParams(extra)),
      })}`,
    )
      .then((data) => {
        if (!cancelled) setPage(data)
      })
      .catch((e) => {
        if (!cancelled) setError(errorText(e))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [id, path, offset, query, extra])

  return { page, offset, setOffset, loading, error }
}
