import type { Project } from '../../api'
import { formatNumber } from '../../lib/format'
import { Badge } from '../ui/Badge'

export function ProjectsTable({ items }: { items: Project[] }) {
  return (
    <div className="table-scroll">
      <table className="table">
        <thead>
          <tr>
            <th>Project</th>
            <th>Manifest</th>
            <th>Lockfile</th>
            <th>Resolved graph</th>
            <th className="num">Direct dependencies</th>
          </tr>
        </thead>
        <tbody>
          {items.map((project, index) => (
            <tr key={`${project.path}-${index}`}>
              <td>
                <div className="cell-title">{project.name || project.path || 'Unnamed project'}</div>
                <div className="cell-sub mono">{project.path || '—'}</div>
              </td>
              <td className="mono path">{project.manifest_path || '—'}</td>
              <td className="mono path">{project.lockfile_path || <span className="muted">Not found</span>}</td>
              <td>
                <Badge tone={project.has_resolved_graph ? 'success' : 'warning'}>
                  {project.has_resolved_graph ? 'Resolved' : 'Unavailable'}
                </Badge>
              </td>
              <td className="num">{formatNumber(project.direct_dependencies?.length ?? 0)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
