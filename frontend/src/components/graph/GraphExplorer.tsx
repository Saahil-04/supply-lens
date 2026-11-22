import { useCallback, useEffect, useMemo, useState } from 'react'
import { Network } from 'lucide-react'
import type { Graph } from '../../api'
import { useViewport } from '../../hooks/useViewport'
import { buildGraphModel, type GraphModel } from '../../lib/graph'
import { pluralize } from '../../lib/format'
import { Alert } from '../ui/Alert'
import { EmptyState } from '../ui/EmptyState'
import { Spinner } from '../ui/Spinner'
import { GraphCanvas } from './GraphCanvas'
import { GraphInspector } from './GraphInspector'
import { GraphNodeList } from './GraphNodeList'

function Legend() {
  return (
    <ul className="graph-legend" aria-label="Legend">
      <li><i className="node-dot is-root" /> Selected package</li>
      <li><i className="node-dot is-near" /> 1 hop away</li>
      <li><i className="node-dot is-far" /> Further away</li>
    </ul>
  )
}

type WorkspaceProps = {
  model: GraphModel
  loading: boolean
  /** Re-run the graph with another package at the centre. */
  onRecenter: (id: string) => void
}

function GraphWorkspace({ model, loading, onRecenter }: WorkspaceProps) {
  const [activeId, setActiveId] = useState<string | null>(null)
  const [expanded, setExpanded] = useState(false)
  const viewport = useViewport({ bounds: model.bounds, sceneKey: model })
  const { centerOn } = viewport

  const active = activeId ? (model.byId.get(activeId) ?? null) : null

  /** Selecting from a list also brings the package into view. */
  const focusNode = useCallback(
    (id: string) => {
      const node = model.byId.get(id)
      setActiveId(id)
      if (node) centerOn(node.x, node.y)
    },
    [model, centerOn],
  )

  useEffect(() => {
    if (!expanded) return
    const onKeyDown = (event: KeyboardEvent) => event.key === 'Escape' && setExpanded(false)
    const { overflow } = document.body.style
    document.body.style.overflow = 'hidden'
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.body.style.overflow = overflow
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [expanded])

  return (
    <section className={`panel graph-panel ${expanded ? 'is-expanded' : ''}`.trim()}>
      <header className="panel-header">
        <div>
          <h2 className="panel-title">Package neighborhood</h2>
          <p className="panel-description">
            {pluralize(model.nodes.length, 'package')} · {pluralize(model.edges.length, 'relationship')}
          </p>
        </div>
        <Legend />
      </header>

      {model.truncated && (
        <div className="graph-notice">
          <Alert tone="warning" title="Partial neighborhood">
            The service truncated this view, so some packages and relationships are missing. Lower the depth or show
            one direction to see the full picture.
          </Alert>
        </div>
      )}

      <div className="graph-layout">
        <GraphCanvas
          model={model}
          viewport={viewport}
          activeId={activeId}
          onSelect={setActiveId}
          loading={loading}
          expanded={expanded}
          onToggleExpanded={() => setExpanded((value) => !value)}
        />
        <aside className="graph-side">
          <GraphInspector model={model} node={active} onSelect={focusNode} onRecenter={onRecenter} />
          <GraphNodeList model={model} activeId={activeId} onSelect={focusNode} />
        </aside>
      </div>
    </section>
  )
}

type Props = {
  graph: Graph | undefined
  loading: boolean
  error?: string
  onRecenter: (id: string) => void
}

export function GraphExplorer({ graph, loading, error, onRecenter }: Props) {
  const model = useMemo(() => (graph ? buildGraphModel(graph) : null), [graph])

  if (error) {
    return <Alert tone="error" title="Could not load the dependency graph">{error}</Alert>
  }

  if (!model || model.nodes.length === 0) {
    return (
      <section className="panel graph-panel">
        {loading ? (
          <div className="graph-placeholder" role="status">
            <Spinner size={20} /> Building neighborhood…
          </div>
        ) : (
          <EmptyState icon={Network} title="No graph to show">
            {graph
              ? 'This package has no relationships within the chosen depth.'
              : 'Choose a package to explore its dependency neighborhood.'}
          </EmptyState>
        )}
      </section>
    )
  }

  return <GraphWorkspace model={model} loading={loading} onRecenter={onRecenter} />
}
