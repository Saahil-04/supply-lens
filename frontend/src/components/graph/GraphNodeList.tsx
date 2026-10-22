import type { Graph } from '../../api'

export function GraphNodeList({ graph }: { graph: Graph }) {
  return (
    <div className="graph-node-list">
      {(graph.nodes || []).map((node) => (
        <div
          key={node.id}
          className={`graph-node-row ${node.id === graph.root_package_id ? 'root-row' : ''}`}
        >
          <span className="node-dot" />
          <div>
            <b>{String(node.name || node.id)}</b>
            <small>{String(node.id)}</small>
          </div>
          <code>{String(node.version || '')}</code>
        </div>
      ))}
    </div>
  )
}
