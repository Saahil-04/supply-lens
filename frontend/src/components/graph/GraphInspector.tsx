import { memo } from 'react'
import { Crosshair, MousePointerClick } from 'lucide-react'
import type { GraphModel, GraphNodeModel } from '../../lib/graph'
import { packageLabel } from '../../lib/format'
import { Badge } from '../ui/Badge'

function Relations({
  title,
  ids,
  model,
  onSelect,
}: {
  title: string
  ids: string[]
  model: GraphModel
  onSelect: (id: string) => void
}) {
  if (!ids.length) return null
  return (
    <section className="relations">
      <h4>
        {title} <span>{ids.length}</span>
      </h4>
      <ul>
        {[...new Set(ids)].map((id) => {
          const node = model.byId.get(id)
          return (
            <li key={id}>
              <button type="button" onClick={() => onSelect(id)}>
                <span className="truncate">{node?.name ?? id}</span>
                {node?.version && <code>{node.version}</code>}
              </button>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

type Props = {
  model: GraphModel
  node: GraphNodeModel | null
  onSelect: (id: string) => void
  onRecenter: (id: string) => void
}

/** Details of the clicked package, with links to the packages it connects to. */
export const GraphInspector = memo(function GraphInspector({ model, node, onSelect, onRecenter }: Props) {
  if (!node) {
    return (
      <div className="inspector inspector-empty">
        <MousePointerClick size={20} aria-hidden="true" />
        <p>Select a package in the graph or list to see how it connects.</p>
      </div>
    )
  }

  const dependsOn = model.dependsOn.get(node.id) ?? []
  const requiredBy = model.requiredBy.get(node.id) ?? []

  return (
    <div className="inspector">
      <div className="inspector-head">
        <h3 className="truncate" title={node.name}>
          {node.name}
        </h3>
        {node.version && <code className="version">{node.version}</code>}
      </div>
      <div className="chip-row">
        {node.isRoot ? <Badge tone="info">Selected package</Badge> : <Badge>{node.hop} {node.hop === 1 ? 'hop' : 'hops'} away</Badge>}
      </div>
      <p className="mono inspector-id" title={packageLabel(node.name, node.version)}>
        {node.id}
      </p>

      <Relations title="Depends on" ids={dependsOn} model={model} onSelect={onSelect} />
      <Relations title="Required by" ids={requiredBy} model={model} onSelect={onSelect} />
      {!dependsOn.length && !requiredBy.length && <p className="muted">No relationships in this view.</p>}

      {!node.isRoot && (
        <button type="button" className="btn btn-secondary btn-sm btn-block" onClick={() => onRecenter(node.id)}>
          <Crosshair size={14} /> Explore from this package
        </button>
      )}
    </div>
  )
})
