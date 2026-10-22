import { useMemo } from 'react'
import type { Graph } from '../../api'

/** Radial layout: every node on one circle, the neighbourhood drawn as straight edges. */
export function GraphCanvas({ graph }: { graph: Graph }) {
  const nodes = graph.nodes || []
  const edges = graph.edges || []

  const positions = useMemo(() => {
    const centerX = 50
    const centerY = 50
    const radius = nodes.length <= 1 ? 0 : 35
    return nodes.map((node, i) => {
      const angle = (2 * Math.PI * i) / Math.max(nodes.length, 1) - Math.PI / 2
      return { node, x: centerX + Math.cos(angle) * radius, y: centerY + Math.sin(angle) * radius }
    })
  }, [nodes])

  const posMap = useMemo(() => new Map(positions.map((pos) => [pos.node.id, pos])), [positions])

  return (
    <div className="graph-canvas">
      <svg viewBox="0 0 100 100" role="img" aria-label="Dependency neighborhood graph">
        {edges.map((edge, i) => {
          const a = posMap.get(edge.source)
          const b = posMap.get(edge.target)
          if (!a || !b) return null
          return (
            <g key={`${edge.source}-${edge.target}-${i}`}>
              <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} className="graph-edge" />
              <title>{`${a.node.name || a.node.id} → ${b.node.name || b.node.id} (${edge.dependency_type || 'dependency'})`}</title>
            </g>
          )
        })}
        {positions.map(({ node, x, y }) => {
          const root = node.id === graph.root_package_id
          return (
            <g key={node.id} className="graph-node">
              <circle
                cx={x}
                cy={y}
                r={root ? 3.7 : 2.8}
                className={root ? 'graph-node-root' : 'graph-node-circle'}
              />
              <text x={x} y={y + (root ? 7 : 6)} textAnchor="middle">
                {String(node.name || node.id).slice(0, 20)}
              </text>
              <title>{`${node.name || node.id}${node.version ? `@${node.version}` : ''}`}</title>
            </g>
          )
        })}
      </svg>
    </div>
  )
}
