import type { Project } from '../../api'
import { n } from '../../lib/format'

export function ProjectsTable({ items }: { items: Project[] }) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Project</th>
            <th>Manifest</th>
            <th>Lockfile</th>
            <th>Resolved graph</th>
            <th>Direct declarations</th>
          </tr>
        </thead>
        <tbody>
          {items.map((p, i) => (
            <tr key={`${p.path}-${i}`}>
              <td>
                <div className="cell-main">{p.name || p.path || 'Unnamed project'}</div>
                <div className="cell-sub">{p.path || '—'}</div>
              </td>
              <td className="path-cell">{p.manifest_path || '—'}</td>
              <td className="path-cell">{p.lockfile_path || <span className="muted">Not found</span>}</td>
              <td>
                <span className={`pill ${p.has_resolved_graph ? 'pill-green' : 'pill-amber'}`}>
                  {p.has_resolved_graph ? 'Resolved' : 'Unavailable'}
                </span>
              </td>
              <td>{n(p.direct_dependencies?.length ?? 0)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
