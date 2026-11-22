import { useEffect, useState } from 'react'
import { request } from '../api'
import { errorText } from '../lib/format'

type Settled<T> = { url: string; data?: T; error?: string }

/**
 * GETs `url` (or does nothing while it is `null`) and aborts the request when
 * the url changes or the component unmounts.
 *
 * With `keepPrevious`, the last successful payload stays available while the
 * next one loads, which avoids layout jumps in paginated tables and the graph.
 */
export function useApi<T>(url: string | null, { keepPrevious = false } = {}) {
  const [settled, setSettled] = useState<Settled<T> | null>(null)

  useEffect(() => {
    if (!url) return
    const controller = new AbortController()
    request<T>(url, { signal: controller.signal })
      .then((data) => setSettled({ url, data }))
      .catch((error) => {
        if (!controller.signal.aborted) setSettled({ url, error: errorText(error) })
      })
    return () => controller.abort()
  }, [url])

  const isCurrent = !!url && settled?.url === url
  return {
    data: isCurrent || keepPrevious ? settled?.data : undefined,
    error: isCurrent ? settled?.error : undefined,
    loading: !!url && !isCurrent,
  }
}
