import { useState } from 'react'
import { qs, type Graph } from '../api'
import { useAllPackages } from '../hooks/useAllPackages'
import { useApi } from '../hooks/useApi'
import { GraphExplorer } from '../components/graph/GraphExplorer'
import { GraphToolbar, type Direction } from '../components/graph/GraphToolbar'
import { Alert } from '../components/ui/Alert'
import { PageHeader } from '../components/ui/PageHeader'

export function GraphView({ id }: { id: string }) {
  const { packages, loading: loadingPackages, error: packagesError } = useAllPackages(id)
  const [chosenId, setChosenId] = useState('')
  const [depth, setDepth] = useState(1)
  const [direction, setDirection] = useState<Direction>('both')

  // Until the user picks a package, start from the first one in the inventory.
  const selectedId = chosenId || packages[0]?.id || ''

  const { data: graph, loading, error } = useApi<Graph>(
    selectedId
      ? `/analyses/${encodeURIComponent(id)}/graph?${qs({ package_id: selectedId, depth, direction })}`
      : null,
    { keepPrevious: true },
  )

  return (
    <>
      <PageHeader
        title="Dependency graph"
        description="Explore the packages around one resolved package instance. Edges come from lockfile relationships and do not prove a vulnerability is exploitable at runtime."
      />
      {packagesError && (
        <Alert tone="error" title="Could not load the package list">
          {packagesError}
        </Alert>
      )}
      <GraphToolbar
        packages={packages}
        loadingPackages={loadingPackages}
        selectedId={selectedId}
        onSelectedIdChange={setChosenId}
        depth={depth}
        onDepthChange={setDepth}
        direction={direction}
        onDirectionChange={setDirection}
      />
      <GraphExplorer graph={graph} loading={loading} error={error} onRecenter={setChosenId} />
    </>
  )
}
