import { useEffect, useMemo, useState } from 'react'
import { AlertCircle } from 'lucide-react'
import { qs, request, type Graph, type PackageItem, type Page } from '../api'
import { errorText } from '../lib/format'
import { GraphControls } from '../components/graph/GraphControls'
import { GraphPanel } from '../components/graph/GraphPanel'
import { ResourceHeader } from '../components/ui/ResourceHeader'

const PACKAGE_PAGE_SIZE = 200

export function GraphView({ id }: { id: string }) {
  const [query, setQuery] = useState('')
  const [selectedId, setSelectedId] = useState('')
  const [depth, setDepth] = useState('1')
  const [direction, setDirection] = useState('both')
  const [graph, setGraph] = useState<Graph | null>(null)
  const [loadingGraph, setLoadingGraph] = useState(false)
  const [graphError, setGraphError] = useState('')
  const [packages, setPackages] = useState<PackageItem[]>([])
  const [loadingPackages, setLoadingPackages] = useState(false)
  const [packagesError, setPackagesError] = useState('')

  // The regular inventory view is paginated for performance. The graph selector
  // needs the complete inventory, so load every package page for this analysis.
  useEffect(() => {
    let cancelled = false

    async function loadAllPackages() {
      setLoadingPackages(true)
      setPackagesError('')
      setPackages([])
      setSelectedId('')
      setGraph(null)
      try {
        const all: PackageItem[] = []
        let offset = 0
        let total: number | undefined

        do {
          const page = await request<Page<PackageItem>>(
            `/analyses/${encodeURIComponent(id)}/packages?${qs({ offset, limit: PACKAGE_PAGE_SIZE })}`,
          )
          all.push(...page.items)
          total = page.pagination.total
          // Use the server's returned page size; this also works if the API
          // caps the requested limit below PACKAGE_PAGE_SIZE.
          offset += page.items.length
          if (!page.pagination.has_more || page.items.length === 0) break
        } while (total === undefined || offset < total)

        if (!cancelled) {
          // Defensively deduplicate by the stable package-instance ID.
          const unique = new Map(all.map((pkg) => [pkg.id, pkg]))
          const complete = [...unique.values()]
          setPackages(complete)
          if (complete.length) setSelectedId(complete[0].id)
        }
      } catch (e) {
        if (!cancelled) setPackagesError(errorText(e))
      } finally {
        if (!cancelled) setLoadingPackages(false)
      }
    }

    void loadAllPackages()
    return () => {
      cancelled = true
    }
  }, [id])

  const filteredPackages = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return packages
    return packages.filter((pkg) =>
      [pkg.name, pkg.version, pkg.path, pkg.lockfile, pkg.id]
        .some((value) => String(value ?? '').toLowerCase().includes(needle)),
    )
  }, [packages, query])

  const fetchGraph = async () => {
    if (!selectedId) return
    setLoadingGraph(true)
    setGraphError('')
    try {
      setGraph(
        await request<Graph>(
          `/analyses/${encodeURIComponent(id)}/graph?${qs({
            package_id: selectedId,
            depth: Number(depth),
            direction,
          })}`,
        ),
      )
    } catch (e) {
      setGraph(null)
      setGraphError(errorText(e))
    } finally {
      setLoadingGraph(false)
    }
  }

  useEffect(() => {
    // Depth/direction changes intentionally wait for the "Load graph" button.
    if (selectedId) void fetchGraph()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId])

  return (
    <>
      <ResourceHeader
        eyebrow="DEPENDENCY EXPLORER"
        title="Dependency graph"
        body="Inspect a bounded neighborhood around one resolved package instance. Edges show lockfile relationships, not proof of runtime exploitability."
      />
      {packagesError && (
        <div className="alert alert-error">
          <AlertCircle size={17} />
          Could not load package choices: {packagesError}
        </div>
      )}
      <GraphControls
        query={query}
        onQueryChange={setQuery}
        packages={filteredPackages}
        totalPackages={packages.length}
        loadingPackages={loadingPackages}
        selectedId={selectedId}
        onSelectedIdChange={setSelectedId}
        depth={depth}
        onDepthChange={setDepth}
        direction={direction}
        onDirectionChange={setDirection}
        loading={loadingGraph}
        onLoad={() => void fetchGraph()}
      />

      {graphError && (
        <div className="alert alert-error">
          <AlertCircle size={17} />
          {graphError}
        </div>
      )}

      <GraphPanel graph={graph} loading={loadingGraph} />
    </>
  )
}
