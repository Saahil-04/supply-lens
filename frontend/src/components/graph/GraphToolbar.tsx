import type { PackageItem } from '../../api'
import { Segmented, type SegmentedOption } from '../ui/Segmented'
import { PackagePicker } from './PackagePicker'

export type Direction = 'both' | 'in' | 'out'

const DEPTH_OPTIONS: SegmentedOption<number>[] = [0, 1, 2, 3].map((hops) => ({
  value: hops,
  label: String(hops),
  title: `${hops} ${hops === 1 ? 'hop' : 'hops'} from the selected package`,
}))

const DIRECTION_OPTIONS: SegmentedOption<Direction>[] = [
  { value: 'both', label: 'Both', title: 'Both directions' },
  { value: 'in', label: 'Dependencies', title: 'Dependencies of the selected package' },
  { value: 'out', label: 'Dependents', title: 'Dependents of the selected package' },
]

type Props = {
  packages: PackageItem[]
  loadingPackages: boolean
  selectedId: string
  onSelectedIdChange: (id: string) => void
  depth: number
  onDepthChange: (depth: number) => void
  direction: Direction
  onDirectionChange: (direction: Direction) => void
}

export function GraphToolbar({
  packages,
  loadingPackages,
  selectedId,
  onSelectedIdChange,
  depth,
  onDepthChange,
  direction,
  onDirectionChange,
}: Props) {
  return (
    <div className="panel graph-toolbar">
      <PackagePicker packages={packages} selectedId={selectedId} onSelect={onSelectedIdChange} loading={loadingPackages} />
      <div className="field">
        <span className="field-label">Depth (hops)</span>
        <Segmented label="Depth" value={depth} onChange={onDepthChange} options={DEPTH_OPTIONS} />
      </div>
      <div className="field">
        <span className="field-label">Show</span>
        <Segmented label="Direction" value={direction} onChange={onDirectionChange} options={DIRECTION_OPTIONS} />
      </div>
    </div>
  )
}
