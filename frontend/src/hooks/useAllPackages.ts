import { useEffect, useState } from 'react'
import { qs, request, type PackageItem, type Page } from '../api'
import { errorText } from '../lib/format'

const PAGE_SIZE = 200
const NONE: PackageItem[] = []

type Loaded = { analysisId: string; packages: PackageItem[]; error?: string }

async function fetchEveryPackage(analysisId: string, signal: AbortSignal) {
  const all: PackageItem[] = []
  let offset = 0
  for (;;) {
    const page = await request<Page<PackageItem>>(
      `/analyses/${encodeURIComponent(analysisId)}/packages?${qs({ offset, limit: PAGE_SIZE })}`,
      { signal },
    )
    all.push(...page.items)
    // Advance by what the server returned, so a server-side page cap still works.
    offset += page.items.length
    if (!page.pagination.has_more || page.items.length === 0 || offset >= page.pagination.total) break
  }
  // Package-instance ids are stable and unique; deduplicate defensively.
  return [...new Map(all.map((pkg) => [pkg.id, pkg])).values()]
}

/**
 * Loads the complete package inventory of an analysis. The Packages tab is
 * paginated, but the graph's package picker needs every instance.
 */
export function useAllPackages(analysisId: string) {
  const [loaded, setLoaded] = useState<Loaded | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    fetchEveryPackage(analysisId, controller.signal)
      .then((packages) => setLoaded({ analysisId, packages }))
      .catch((error) => {
        if (!controller.signal.aborted) setLoaded({ analysisId, packages: NONE, error: errorText(error) })
      })
    return () => controller.abort()
  }, [analysisId])

  const isCurrent = loaded?.analysisId === analysisId
  return {
    packages: isCurrent ? loaded.packages : NONE,
    loading: !isCurrent,
    error: isCurrent ? loaded.error : undefined,
  }
}
