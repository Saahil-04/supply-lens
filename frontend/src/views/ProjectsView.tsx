import { useState } from 'react'
import type { Page, Project } from '../api'
import { useResource } from '../hooks/useResource'
import { ProjectsTable } from '../components/projects/ProjectsTable'
import { Pagination } from '../components/ui/Pagination'
import { ResourceHeader } from '../components/ui/ResourceHeader'
import { SearchBox } from '../components/ui/SearchBox'
import { TableState } from '../components/ui/TableState'

export function ProjectsView({ id }: { id: string }) {
  const [query, setQuery] = useState('')
  const q = useResource<Project>(id, 'projects', query)
  const items = q.page?.items || []

  return (
    <>
      <ResourceHeader
        eyebrow="INVENTORY"
        title="Projects"
        body="Discovered manifests and the lockfiles used to resolve each project."
        total={q.page?.pagination.total}
      />
      <div className="toolbar">
        <SearchBox value={query} onChange={setQuery} placeholder="Search project name or path…" />
      </div>
      <div className="table-card">
        <TableState loading={q.loading} error={q.error} empty={!q.loading && !q.error && items.length === 0} />
        {items.length > 0 && <ProjectsTable items={items} />}
      </div>
      <Pagination page={q.page as Page<unknown> | null} offset={q.offset} setOffset={q.setOffset} />
    </>
  )
}
