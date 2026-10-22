import type { PackageItem } from '../../api'

export function PackagesTable({ items }: { items: PackageItem[] }) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Package</th>
            <th>Version</th>
            <th>Type</th>
            <th>Scope</th>
            <th>Project lockfile</th>
          </tr>
        </thead>
        <tbody>
          {items.map((p, i) => (
            <tr key={`${p.id}-${i}`}>
              <td>
                <div className="cell-main">{p.name}</div>
                <div className="cell-sub mono">{p.id}</div>
              </td>
              <td>
                <code className="version-code">{p.version || '—'}</code>
              </td>
              <td>
                <span className={`pill ${p.is_direct ? 'pill-blue' : 'pill-neutral'}`}>
                  {p.is_direct ? 'Direct' : 'Transitive'}
                </span>
              </td>
              <td>
                {p.is_dev ? (
                  <span className="pill pill-violet">Development</span>
                ) : (
                  <span className="muted">Production / other</span>
                )}
              </td>
              <td className="path-cell">{p.lockfile || p.path || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
