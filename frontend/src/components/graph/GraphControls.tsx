import { GitBranch, LoaderCircle } from 'lucide-react'
import type { PackageItem } from '../../api'
import { SearchBox } from '../ui/SearchBox'

export function GraphControls({
  query,
  onQueryChange,
  packages,
  selectedId,
  onSelectedIdChange,
  depth,
  onDepthChange,
  direction,
  onDirectionChange,
  loading,
  onLoad,
}: {
  query: string
  onQueryChange: (q: string) => void
  packages: PackageItem[]
  selectedId: string
  onSelectedIdChange: (id: string) => void
  depth: string
  onDepthChange: (d: string) => void
  direction: string
  onDirectionChange: (d: string) => void
  loading: boolean
  onLoad: () => void
}) {
  return (
    <div className="graph-controls panel">
      <div className="graph-package-field">
        <label>Root package</label>
        <SearchBox value={query} onChange={onQueryChange} placeholder="Filter package choices…" />
        <select className="wide-select" value={selectedId} onChange={(e) => onSelectedIdChange(e.target.value)}>
          <option value="">Select a package</option>
          {packages.map((pkg) => (
            <option key={pkg.id} value={pkg.id}>
              {pkg.name}@{pkg.version} · {pkg.lockfile || pkg.path || ''}
            </option>
          ))}
        </select>
        <span className="field-hint">
          Choose from the current page of package search results; type above to narrow the choices.
        </span>
      </div>
      <div className="graph-option">
        <label>Depth</label>
        <select className="filter-select" value={depth} onChange={(e) => onDepthChange(e.target.value)}>
          {[0, 1, 2, 3].map((d) => (
            <option key={d} value={d}>
              {d} hop{d === 1 ? '' : 's'}
            </option>
          ))}
        </select>
      </div>
      <div className="graph-option">
        <label>Direction</label>
        <select className="filter-select" value={direction} onChange={(e) => onDirectionChange(e.target.value)}>
          <option value="both">Both</option>
          <option value="in">Dependencies of</option>
          <option value="out">Dependents of</option>
        </select>
      </div>
      <button className="button button-primary graph-submit" onClick={onLoad} disabled={!selectedId || loading}>
        {loading ? <LoaderCircle size={15} className="spin" /> : <GitBranch size={15} />} Load graph
      </button>
    </div>
  )
}
