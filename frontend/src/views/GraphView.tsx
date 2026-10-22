import { useEffect, useState } from 'react'
import { AlertCircle } from 'lucide-react'
import { qs, request, type Graph, type PackageItem } from '../api'
import { useResource } from '../hooks/useResource'
import { errorText } from '../lib/format'
import { GraphControls } from '../components/graph/GraphControls'
import { GraphPanel } from '../components/graph/GraphPanel'
import { ResourceHeader } from '../components/ui/ResourceHeader'

export function GraphView({ id }: { id: string }) {
  const [query, setQuery] = useState('')
  const [selectedId, setSelectedId] = useState('')
  const [depth, setDepth] = useState('1')
  const [direction, setDirection] = useState('both')
  const [graph, setGraph] = useState<Graph | null>(null)
  const [loadingGraph, setLoadingGraph] = useState(false)
  const [graphError, setGraphError] = useState('')

  const p = useResource<PackageItem>(id, 'packages', query)
  const packages = p.page?.items || []

  useEffect(() => {
    if (!selectedId && packages.length) setSelectedId(packages[0].id)
  }, [packages, selectedId])

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
      <GraphControls
        query={query}
        onQueryChange={setQuery}
        packages={packages}
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
