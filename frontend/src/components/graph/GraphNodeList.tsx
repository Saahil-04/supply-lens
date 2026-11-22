import { memo, useMemo, useState } from 'react'
import { Search } from 'lucide-react'
import type { GraphModel } from '../../lib/graph'

type Props = {
  model: GraphModel
  activeId: string | null
  onSelect: (id: string) => void
}

/** Filterable list of every package in the current view, grouped by distance from the selected package. */
export const GraphNodeList = memo(function GraphNodeList({ model, activeId, onSelect }: Props) {
  const [filter, setFilter] = useState('')

  const groups = useMemo(() => {
    const needle = filter.trim().toLowerCase()
    const matching = model.nodes.filter((node) => !needle || node.name.toLowerCase().includes(needle))
    const byHop = new Map<number, typeof matching>()
    for (const node of matching.sort((a, b) => a.name.localeCompare(b.name))) {
      byHop.set(node.hop, [...(byHop.get(node.hop) ?? []), node])
    }
    return [...byHop.entries()].sort(([a], [b]) => a - b)
  }, [model, filter])

  return (
    <div className="node-list">
      <label className="node-list-filter">
        <Search size={14} aria-hidden="true" />
        <input
          type="search"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          placeholder="Filter packages in view…"
          aria-label="Filter packages in view"
        />
      </label>

      <div className="node-list-scroll">
        {groups.length === 0 && <p className="muted node-list-empty">No packages match.</p>}
        {groups.map(([hop, nodes]) => (
          <section key={hop}>
            <h4>{hop === 0 ? 'Selected package' : `${hop} ${hop === 1 ? 'hop' : 'hops'} away`}</h4>
            <ul>
              {nodes.map((node) => (
                <li key={node.id}>
                  <button
                    type="button"
                    className={node.id === activeId ? 'is-active' : undefined}
                    aria-pressed={node.id === activeId}
                    onClick={() => onSelect(node.id)}
                  >
                    <span className={`node-dot ${node.isRoot ? 'is-root' : node.hop === 1 ? 'is-near' : 'is-far'}`} />
                    <span className="truncate">{node.name}</span>
                    {node.version && <code>{node.version}</code>}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  )
})
