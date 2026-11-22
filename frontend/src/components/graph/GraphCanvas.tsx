import { useId, useMemo, useState, type ReactNode } from 'react'
import { Loader2, Maximize, Minimize, Minus, Plus, ScanSearch } from 'lucide-react'
import type { Viewport } from '../../hooks/useViewport'
import type { GraphEdgeModel, GraphModel, GraphNodeModel } from '../../lib/graph'
import { packageLabel, truncate } from '../../lib/format'

/* Layout-unit sizes. They are scaled against the zoom so nodes stay legible. */
const NODE_RADIUS = { root: 14, near: 9, far: 7 }
const LABEL_SIZE = 12
const MAX_LABEL = 26
const ARROW_LIMIT = 40
const DENSE_LIMIT = 60
const ALL_LABELS_ZOOM = 1.2
const SMALL_GRAPH = 40

const nodeRadius = (node: GraphNodeModel) => (node.isRoot ? NODE_RADIUS.root : node.hop === 1 ? NODE_RADIUS.near : NODE_RADIUS.far)

/** Snaps the zoom to ~12% steps so the scene only re-renders when sizes visibly change. */
const quantize = (k: number) => 1.12 ** Math.round(Math.log(k) / Math.log(1.12))

type Point = { x: number; y: number }

function edgePath(a: GraphNodeModel, b: GraphNodeModel, curved: boolean, sizeScale: number, arrow: boolean) {
  // Bend same-ring edges toward the centre; straight otherwise.
  const control: Point | null = curved ? { x: ((a.x + b.x) / 2) * 0.5, y: ((a.y + b.y) / 2) * 0.5 } : null
  const toward = (from: Point, to: Point, distance: number): Point => {
    const dx = to.x - from.x
    const dy = to.y - from.y
    const length = Math.hypot(dx, dy) || 1
    return { x: from.x + (dx / length) * distance, y: from.y + (dy / length) * distance }
  }
  const gap = 2 * sizeScale
  const start = toward(a, control ?? b, nodeRadius(a) * sizeScale + gap)
  const end = toward(b, control ?? a, nodeRadius(b) * sizeScale + gap + (arrow ? 3 * sizeScale : 0))
  return control
    ? `M${start.x} ${start.y}Q${control.x} ${control.y} ${end.x} ${end.y}`
    : `M${start.x} ${start.y}L${end.x} ${end.y}`
}

type SceneOptions = {
  model: GraphModel
  focusId: string | null
  activeId: string | null
  showAllLabels: boolean
  sizeScale: number
  textScale: number
  markerId: string
  onHover: (id: string | null) => void
  onSelect: (id: string | null) => void
}

function renderScene({ model, focusId, activeId, showAllLabels, sizeScale, textScale, markerId, onHover, onSelect }: SceneOptions) {
  const related = focusId ? model.neighbors.get(focusId) : undefined
  const showArrows = model.edges.length <= ARROW_LIMIT
  const dense = model.edges.length > DENSE_LIMIT

  const edgeElement = (edge: GraphEdgeModel) => {
    const a = model.byId.get(edge.source)
    const b = model.byId.get(edge.target)
    if (!a || !b || a === b) return null
    const isActive = !!focusId && (edge.source === focusId || edge.target === focusId)
    const state = isActive ? 'is-active' : focusId ? 'is-dim' : dense ? 'is-faint' : ''
    const arrow = showArrows || isActive
    return (
      <path
        key={edge.key}
        className={`graph-edge ${state}`.trim()}
        d={edgePath(a, b, edge.curved, sizeScale, arrow)}
        markerEnd={arrow ? `url(#${markerId}-${isActive ? 'active' : 'base'})` : undefined}
      >
        <title>{`${a.name} → ${b.name} (${edge.type || 'dependency'})`}</title>
      </path>
    )
  }

  // Highlighted edges are drawn last so they sit on top.
  const edges = [
    ...model.edges.filter((e) => !(focusId && (e.source === focusId || e.target === focusId))).map(edgeElement),
    ...model.edges.filter((e) => focusId && (e.source === focusId || e.target === focusId)).map(edgeElement),
  ]

  const nodes: ReactNode[] = model.nodes.map((node) => {
    const isFocus = node.id === focusId
    const isRelated = !!related?.has(node.id)
    const isDim = !!focusId && !isFocus && !isRelated
    const labelled = node.isRoot || node.hop === 1 || isFocus || isRelated || showAllLabels
    const radius = nodeRadius(node) * sizeScale
    const label = truncate(node.name, MAX_LABEL)
    const fontSize = LABEL_SIZE * textScale
    const offset = radius + 6 * textScale

    // Few nodes on a ring: horizontal labels outside the node. Many: labels run along the spoke.
    let labelProps: { x: number; y: number; textAnchor: 'start' | 'middle' | 'end'; transform?: string }
    if (node.isRoot) {
      labelProps = { x: 0, y: radius + fontSize + 4 * textScale, textAnchor: 'middle' }
    } else if (node.ringSize <= 14) {
      const right = Math.cos(node.angle) >= 0
      labelProps = { x: right ? offset : -offset, y: fontSize * 0.35, textAnchor: right ? 'start' : 'end' }
    } else {
      const degrees = (node.angle * 180) / Math.PI
      const right = Math.cos(node.angle) >= 0
      labelProps = {
        x: right ? offset : -offset,
        y: fontSize * 0.35,
        textAnchor: right ? 'start' : 'end',
        transform: `rotate(${right ? degrees : degrees + 180})`,
      }
    }

    const classes = [
      'graph-node',
      node.isRoot ? 'is-root' : node.hop === 1 ? 'is-near' : 'is-far',
      node.id === activeId && 'is-active',
      isFocus && 'is-focus',
      isDim && 'is-dim',
    ]
      .filter(Boolean)
      .join(' ')

    return (
      <g
        key={node.id}
        className={classes}
        transform={`translate(${node.x} ${node.y})`}
        onPointerEnter={() => onHover(node.id)}
        onPointerLeave={() => onHover(null)}
        onClick={(event) => {
          event.stopPropagation()
          onSelect(node.id)
        }}
      >
        <title>{`${packageLabel(node.name, node.version)}${node.isRoot ? ' · selected package' : ''}`}</title>
        {node.id === activeId && <circle className="graph-node-halo" r={radius + 5 * sizeScale} strokeWidth={2 * sizeScale} />}
        <circle className="graph-node-dot" r={radius} strokeWidth={1.5 * sizeScale} />
        {labelled && (
          <text className="graph-label" fontSize={fontSize} strokeWidth={3.5 * textScale} {...labelProps}>
            {label}
          </text>
        )}
      </g>
    )
  })

  return { edges, nodes }
}

type Props = {
  model: GraphModel
  viewport: Viewport
  activeId: string | null
  onSelect: (id: string | null) => void
  loading: boolean
  expanded: boolean
  onToggleExpanded: () => void
}

/** SVG rendering of a graph model with pan, zoom, hover highlighting and selection. */
export function GraphCanvas({ model, viewport, activeId, onSelect, loading, expanded, onToggleExpanded }: Props) {
  const markerId = useId().replace(/:/g, '')
  const [hoverId, setHoverId] = useState<string | null>(null)
  const { view, dragging, wasDragged, bindContainer, containerProps, zoomIn, zoomOut, fit } = viewport

  const zoom = quantize(view.k)
  const sizeScale = zoom ** -0.5
  const textScale = 1 / zoom
  const showAllLabels = view.k >= ALL_LABELS_ZOOM || model.nodes.length <= SMALL_GRAPH
  const focusId = hoverId ?? activeId

  // Rebuilt only when something visible changes, not on every pan frame.
  const scene = useMemo(
    () =>
      renderScene({ model, focusId, activeId, showAllLabels, sizeScale, textScale, markerId, onHover: setHoverId, onSelect }),
    [model, focusId, activeId, showAllLabels, sizeScale, textScale, markerId, onSelect],
  )

  const arrowSize = 9 * textScale

  return (
    <div
      ref={bindContainer}
      className={`graph-canvas ${dragging ? 'is-dragging' : ''}`.trim()}
      tabIndex={0}
      aria-label="Dependency graph. Drag to pan, hold Ctrl or Cmd and scroll to zoom. Use the package list to move through packages with the keyboard."
      onClick={() => !wasDragged() && onSelect(null)}
      {...containerProps}
    >
      <svg className="graph-svg" role="img" aria-label={`Graph with ${model.nodes.length} packages`}>
        <defs>
          {(['base', 'active'] as const).map((kind) => (
            <marker
              key={kind}
              id={`${markerId}-${kind}`}
              className={`graph-arrow graph-arrow-${kind}`}
              viewBox="0 0 10 10"
              refX="10"
              refY="5"
              markerUnits="userSpaceOnUse"
              markerWidth={arrowSize}
              markerHeight={arrowSize}
              orient="auto"
            >
              <path d="M0 0L10 5L0 10z" />
            </marker>
          ))}
        </defs>
        <g transform={`translate(${view.x} ${view.y}) scale(${view.k})`}>
          <g>{scene.edges}</g>
          <g>{scene.nodes}</g>
        </g>
      </svg>

      <div className="graph-controls" onPointerDown={(event) => event.stopPropagation()} onClick={(event) => event.stopPropagation()}>
        <button type="button" className="icon-button" onClick={zoomIn} aria-label="Zoom in" title="Zoom in">
          <Plus size={16} />
        </button>
        <button type="button" className="icon-button" onClick={zoomOut} aria-label="Zoom out" title="Zoom out">
          <Minus size={16} />
        </button>
        <button type="button" className="icon-button" onClick={fit} aria-label="Fit graph to view" title="Fit to view">
          <ScanSearch size={16} />
        </button>
        <button
          type="button"
          className="icon-button"
          onClick={onToggleExpanded}
          aria-label={expanded ? 'Exit full screen' : 'Full screen'}
          title={expanded ? 'Exit full screen' : 'Full screen'}
        >
          {expanded ? <Minimize size={16} /> : <Maximize size={16} />}
        </button>
      </div>

      <div className="graph-hint">Drag to pan · Ctrl/⌘ + scroll to zoom · Click a package to inspect it</div>

      {loading && (
        <div className="graph-loading" role="status">
          <Loader2 size={16} className="spin" /> Updating graph…
        </div>
      )}
    </div>
  )
}
