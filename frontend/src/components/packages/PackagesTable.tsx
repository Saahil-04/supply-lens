import type { PackageItem } from '../../api'
import { Badge } from '../ui/Badge'

export function PackagesTable({ items }: { items: PackageItem[] }) {
  return (
    <div className="table-scroll">
      <table className="table">
        <thead>
          <tr>
            <th>Package</th>
            <th>Version</th>
            <th>Type</th>
            <th>Scope</th>
            <th>Lockfile</th>
          </tr>
        </thead>
        <tbody>
          {items.map((pkg, index) => (
            <tr key={`${pkg.id}-${index}`}>
              <td>
                <div className="cell-title">{pkg.name}</div>
                <div className="cell-sub mono truncate" title={pkg.id}>
                  {pkg.id}
                </div>
              </td>
              <td>
                <code className="version">{pkg.version ?? '—'}</code>
              </td>
              <td>
                <Badge tone={pkg.is_direct ? 'info' : 'neutral'}>{pkg.is_direct ? 'Direct' : 'Transitive'}</Badge>
              </td>
              <td>{pkg.is_dev ? <Badge tone="violet">Development</Badge> : <span className="muted">Production</span>}</td>
              <td className="mono path">{pkg.lockfile || pkg.path || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
