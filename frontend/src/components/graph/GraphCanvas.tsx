import { useMemo, useState } from 'react'
import type { PointerEvent as ReactPointerEvent, WheelEvent as ReactWheelEvent } from 'react'
import { Minus, Plus, RotateCcw } from 'lucide-react'
import type { Graph } from '../../api'

type Point = { x: number; y: number }

/** Interactive neighbourhood graph with zoom, pan and relationship highlighting. */
export function GraphCanvas({ graph }: { graph: Graph }) {
  const nodes = graph.nodes || []
  const edges = graph.edges || []
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState<Point>({ x: 0, y: 0 })
  const [hoveredId, setHoveredId] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)
  const [dragOrigin, setDragOrigin] = useState<Point | null>(null)
  const [dragStartPan, setDragStartPan] = useState<Point>({ x: 0, y: 0 })

  const positions = useMemo(() => {
    const root = nodes.find((node) => node.id === graph.root_package_id)
    const others = nodes.filter((node) => node.id !== graph.root_package_id)
    return [
      ...(root ? [{ node: root, x: 50, y: 50 }] : []),
      ...others.map((node, i) => {
        // Two rings reduce the single-ring "scrambled egg" effect for larger neighbourhoods.
        const ring = i < 18 ? 1 : 2
        const ringNodes = ring === 1 ? Math.min(others.length, 18) : Math.max(others.length - 18, 1)
        const index = ring === 1 ? i : i - 18
        const radius = ring === 1 ? 23 : 42
        const angle = (2 * Math.PI * index) / ringNodes - Math.PI / 2 + (ring === 2 ? Math.PI / Math.max(ringNodes, 1) : 0)
        return { node, x: 50 + Math.cos(angle) * radius, y: 50 + Math.sin(angle) * radius }
      }),
    ]
  }, [nodes, graph.root_package_id])

  const posMap = useMemo(() => new Map(positions.map((pos) => [pos.node.id, pos])), [positions])
  const connectedIds = useMemo(() => {
    const connected = new Set<string>()
    if (hoveredId) {
      connected.add(hoveredId)
      edges.forEach((edge) => {
        if (edge.source === hoveredId) connected.add(edge.target)
        if (edge.target === hoveredId) connected.add(edge.source)
      })
    }
    return connected
  }, [hoveredId, edges])

  const resetView = () => { setZoom(1); setPan({ x: 0, y: 0 }) }
  const onWheel = (event: ReactWheelEvent<SVGSVGElement>) => {
    // Let ordinary wheel gestures scroll the page. Zoom the graph only when
    // the user explicitly holds Ctrl/Cmd, so one gesture never does both.
    if (!event.ctrlKey && !event.metaKey) return
    event.preventDefault()
    setZoom((current) => Math.max(0.65, Math.min(5, current * (event.deltaY < 0 ? 1.15 : 1 / 1.15))))
  }
  const onPointerDown = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (event.button !== 0) return
    setDragging(true)
    setDragOrigin({ x: event.clientX, y: event.clientY })
    setDragStartPan(pan)
    event.currentTarget.setPointerCapture(event.pointerId)
  }
  const onPointerMove = (event: ReactPointerEvent<SVGSVGElement>) => {
    if (!dragging || !dragOrigin) return
    const rect = event.currentTarget.getBoundingClientRect()
    const scale = 100 / Math.max(rect.width, rect.height)
    setPan({ x: dragStartPan.x + (event.clientX - dragOrigin.x) * scale, y: dragStartPan.y + (event.clientY - dragOrigin.y) * scale })
  }

  return (
    <div className="graph-canvas-wrap">
      <div className="graph-zoom-controls" aria-label="Graph navigation controls">
        <button onClick={() => setZoom((v) => Math.min(5, v * 1.25))} title="Zoom in" aria-label="Zoom in"><Plus size={16} /></button>
        <span>{Math.round(zoom * 100)}%</span>
        <button onClick={() => setZoom((v) => Math.max(0.65, v / 1.25))} title="Zoom out" aria-label="Zoom out"><Minus size={16} /></button>
        <button onClick={resetView} title="Fit graph to view / reset zoom" aria-label="Fit graph to view"><RotateCcw size={15} /></button>
      </div>
      <div className="graph-canvas">
        <svg
          viewBox="0 0 100 100"
          role="img"
          aria-label="Interactive dependency neighborhood graph. Scroll to move the page; hold Ctrl or Cmd while scrolling to zoom the graph, and drag to pan."
          onWheel={onWheel}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={() => { setDragging(false); setDragOrigin(null) }}
          onPointerCancel={() => { setDragging(false); setDragOrigin(null) }}
          onPointerLeave={() => { if (!dragging) setHoveredId(null) }}
          style={{ cursor: dragging ? 'grabbing' : 'grab', touchAction: 'none' }}
        >
          <g transform={`translate(${pan.x} ${pan.y}) translate(50 50) scale(${zoom}) translate(-50 -50)`}>
            {edges.map((edge, i) => {
              const a = posMap.get(edge.source)
              const b = posMap.get(edge.target)
              if (!a || !b) return null
              const active = !!hoveredId && (edge.source === hoveredId || edge.target === hoveredId)
              const dim = !!hoveredId && !active
              return (
                <g key={`${edge.source}-${edge.target}-${i}`} className={active ? 'graph-edge-group edge-active' : dim ? 'graph-edge-group edge-dim' : 'graph-edge-group'}>
                  <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} className="graph-edge" />
                  <title>{`${a.node.name || a.node.id} → ${b.node.name || b.node.id} (${edge.dependency_type || 'dependency'})`}</title>
                </g>
              )
            })}
            {positions.map(({ node, x, y }) => {
              const root = node.id === graph.root_package_id
              const hovered = node.id === hoveredId
              const related = connectedIds.has(node.id)
              const dim = !!hoveredId && !related
              const showLabel = root || hovered || (related && nodes.length <= 60)
              return (
                <g
                  key={node.id}
                  className={`graph-node ${root ? 'is-root' : ''} ${hovered ? 'is-hovered' : ''} ${dim ? 'is-dimmed' : ''} ${related ? 'is-related' : ''}`}
                  onPointerEnter={() => setHoveredId(node.id)}
                  onPointerLeave={() => setHoveredId((current) => current === node.id ? null : current)}
                  onPointerDown={(event) => event.stopPropagation()}
                  tabIndex={0}
                  role="button"
                  aria-label={`${node.name || node.id}${node.version ? ` version ${node.version}` : ''}`}
                  onFocus={() => setHoveredId(node.id)}
                  onBlur={() => setHoveredId(null)}
                >
                  <circle cx={x} cy={y} r={root ? 3.8 : hovered ? 3.6 : 2.5} className={root ? 'graph-node-root' : 'graph-node-circle'} />
                  {showLabel && (
                    <text x={x} y={y + (root || hovered ? 6 : 4.8)} textAnchor="middle" className="graph-node-label">
                      {String(node.name || node.id).slice(0, 22)}
                    </text>
                  )}
                  <title>{`${node.name || node.id}${node.version ? `@${node.version}` : ''}${root ? ' · selected package' : ''}`}</title>
                </g>
              )
            })}
          </g>
        </svg>
      </div>
      {hoveredId && posMap.get(hoveredId) && (
        <div className="graph-hover-card">
          <b>{posMap.get(hoveredId)?.node.name || hoveredId}</b>
          <span>{posMap.get(hoveredId)?.node.version ? `Version ${posMap.get(hoveredId)?.node.version}` : 'Version not provided'}</span>
          <span>{edges.filter((edge) => edge.source === hoveredId || edge.target === hoveredId).length} connected relationship(s)</span>
          {hoveredId === graph.root_package_id && <em>Selected root package</em>}
        </div>
      )}
    </div>
  )
}
