import type { Graph } from '../api'

/**
 * Turns the API's flat `{ nodes, edges }` payload into a drawable model:
 * a radial layout where each ring is one hop away from the selected package.
 *
 * Coordinates are in abstract layout units centred on the root at (0, 0).
 */

export type GraphNodeModel = {
  id: string
  name: string
  version?: string
  /** Hops from the selected package. Nodes unreachable from it get `maxHop + 1`. */
  hop: number
  x: number
  y: number
  /** Polar angle in radians; used to orient labels away from the centre. */
  angle: number
  isRoot: boolean
  /** Number of nodes on this node's ring, used to pick the label style. */
  ringSize: number
}

export type GraphEdgeModel = {
  key: string
  source: string
  target: string
  type?: string
  /** Same-ring edges are bent toward the centre so they do not cut through other nodes. */
  curved: boolean
}

export type GraphModel = {
  nodes: GraphNodeModel[]
  byId: Map<string, GraphNodeModel>
  edges: GraphEdgeModel[]
  neighbors: Map<string, Set<string>>
  /** Packages the key package depends on (edges where it is the source). */
  dependsOn: Map<string, string[]>
  /** Packages that depend on the key package (edges where it is the target). */
  requiredBy: Map<string, string[]>
  rootId: string | null
  maxHop: number
  bounds: { minX: number; minY: number; maxX: number; maxY: number }
  truncated: boolean
}

const RING_GAP = 150
/** Minimum arc length between neighbouring nodes on a ring. */
const ARC_SPACING = 72
/** Room for labels that extend outside the outermost ring. */
const BOUNDS_PADDING = 130

const push = <K, V>(map: Map<K, V[]>, key: K, value: V) => {
  const list = map.get(key)
  if (list) list.push(value)
  else map.set(key, [value])
}

/** Mean of angles (radians), or `undefined` when there are none. */
function meanAngle(angles: number[]) {
  if (!angles.length) return undefined
  const sin = angles.reduce((sum, a) => sum + Math.sin(a), 0)
  const cos = angles.reduce((sum, a) => sum + Math.cos(a), 0)
  return Math.atan2(sin, cos)
}

export function buildGraphModel(graph: Graph): GraphModel {
  const rawNodes = [...new Map((graph.nodes ?? []).map((node) => [node.id, node])).values()]
  const ids = new Set(rawNodes.map((node) => node.id))
  const rootId = ids.has(graph.root_package_id) ? graph.root_package_id : (rawNodes[0]?.id ?? null)

  // Edges, restricted to nodes we can actually draw.
  const neighbors = new Map<string, Set<string>>(rawNodes.map((node) => [node.id, new Set()]))
  const dependsOn = new Map<string, string[]>()
  const requiredBy = new Map<string, string[]>()
  const edgeSeen = new Set<string>()
  const rawEdges = (graph.edges ?? []).filter((edge) => {
    if (!ids.has(edge.source) || !ids.has(edge.target)) return false
    const key = `${edge.source}\u0000${edge.target}\u0000${edge.dependency_type ?? ''}`
    if (edgeSeen.has(key)) return false
    edgeSeen.add(key)
    return true
  })
  for (const edge of rawEdges) {
    neighbors.get(edge.source)?.add(edge.target)
    neighbors.get(edge.target)?.add(edge.source)
    push(dependsOn, edge.source, edge.target)
    push(requiredBy, edge.target, edge.source)
  }

  // Hop distance from the root (breadth-first, ignoring edge direction).
  const hops = new Map<string, number>()
  if (rootId) {
    hops.set(rootId, 0)
    const queue = [rootId]
    for (let head = 0; head < queue.length; head++) {
      const current = queue[head]
      for (const next of neighbors.get(current) ?? []) {
        if (hops.has(next)) continue
        hops.set(next, hops.get(current)! + 1)
        queue.push(next)
      }
    }
  }
  const reachableMax = Math.max(0, ...hops.values())
  const hasUnlinked = rawNodes.some((node) => !hops.has(node.id))
  const maxHop = reachableMax + (hasUnlinked ? 1 : 0)

  const rings = new Map<number, typeof rawNodes>()
  for (const node of rawNodes) push(rings, hops.get(node.id) ?? reachableMax + 1, node)

  // Place rings from the inside out. Within a ring, order nodes by where their
  // already-placed neighbours sit so related nodes end up near each other.
  const byId = new Map<string, GraphNodeModel>()
  let radius = 0
  for (let hop = 0; hop <= maxHop; hop++) {
    const ring = rings.get(hop) ?? []
    if (!ring.length) continue

    if (hop === 0) {
      for (const node of ring) {
        byId.set(node.id, {
          id: node.id,
          name: String(node.name ?? node.id),
          version: node.version,
          hop,
          x: 0,
          y: 0,
          angle: 0,
          isRoot: node.id === rootId,
          ringSize: ring.length,
        })
      }
      continue
    }

    radius = Math.max(radius + RING_GAP, (ring.length * ARC_SPACING) / (2 * Math.PI))
    const ordered = ring
      .map((node) => {
        const placed = [...(neighbors.get(node.id) ?? [])]
          .map((id) => byId.get(id))
          .filter((n): n is GraphNodeModel => !!n && n.hop > 0)
          .map((n) => n.angle)
        return { node, target: meanAngle(placed) }
      })
      .sort((a, b) => {
        if (a.target === undefined || b.target === undefined) {
          if (a.target === b.target) return String(a.node.name ?? a.node.id).localeCompare(String(b.node.name ?? b.node.id))
          return a.target === undefined ? 1 : -1
        }
        return a.target - b.target
      })

    const start = ordered[0].target ?? -Math.PI / 2
    // Stagger alternate rings by half a step so spokes do not line up.
    const stagger = hop % 2 === 0 ? Math.PI / ordered.length : 0
    ordered.forEach(({ node }, index) => {
      const angle = start + stagger + (2 * Math.PI * index) / ordered.length
      byId.set(node.id, {
        id: node.id,
        name: String(node.name ?? node.id),
        version: node.version,
        hop,
        x: Math.cos(angle) * radius,
        y: Math.sin(angle) * radius,
        angle: Math.atan2(Math.sin(angle), Math.cos(angle)),
        isRoot: false,
        ringSize: ordered.length,
      })
    })
  }

  const nodes = rawNodes.map((node) => byId.get(node.id)!).filter(Boolean)
  const edges: GraphEdgeModel[] = rawEdges.map((edge, index) => {
    const a = byId.get(edge.source)!
    const b = byId.get(edge.target)!
    return {
      key: `${edge.source}->${edge.target}#${index}`,
      source: edge.source,
      target: edge.target,
      type: edge.dependency_type,
      curved: a.hop === b.hop && a.hop > 0,
    }
  })

  const xs = nodes.map((n) => n.x)
  const ys = nodes.map((n) => n.y)
  const bounds = {
    minX: Math.min(0, ...xs) - BOUNDS_PADDING,
    maxX: Math.max(0, ...xs) + BOUNDS_PADDING,
    minY: Math.min(0, ...ys) - BOUNDS_PADDING / 2,
    maxY: Math.max(0, ...ys) + BOUNDS_PADDING / 2,
  }

  return {
    nodes,
    byId,
    edges,
    neighbors,
    dependsOn,
    requiredBy,
    rootId,
    maxHop,
    bounds,
    truncated: !!graph.truncated,
  }
}
