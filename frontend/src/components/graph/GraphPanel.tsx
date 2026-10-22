import { LoaderCircle } from 'lucide-react'
import type { Graph } from '../../api'
import { GraphCanvas } from './GraphCanvas'
import { GraphNodeList } from './GraphNodeList'

export function GraphPanel({ graph, loading }: { graph: Graph | null; loading: boolean }) {
  const nodeCount = graph?.nodes?.length ?? 0
  const edgeCount = graph?.edges?.length ?? 0

  return (
    <section className="panel graph-panel">
      <div className="panel-heading">
        <div>
          <h3>Package neighborhood</h3>
          <p>
            {nodeCount} nodes · {edgeCount} edges
          </p>
        </div>
        <div className="graph-legend">
          <span>
            <i className="legend-root" /> Selected package
          </span>
          <span>
            <i /> Related package
          </span>
        </div>
      </div>

      {loading ? (
        <div className="table-state">
          <LoaderCircle size={20} className="spin" /> Building neighborhood…
        </div>
      ) : graph && nodeCount ? (
        <>
          <GraphCanvas graph={graph} />
          <GraphNodeList graph={graph} />
        </>
      ) : (
        <div className="table-state">Choose a package and load its dependency neighborhood.</div>
      )}
    </section>
  )
}
