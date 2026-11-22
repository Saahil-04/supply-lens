import { useState } from 'react'
import type { Project } from '../api'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import { useResource } from '../hooks/useResource'
import { ProjectsTable } from '../components/projects/ProjectsTable'
import { DataPanel } from '../components/ui/DataPanel'
import { PageHeader } from '../components/ui/PageHeader'
import { SearchBox } from '../components/ui/SearchBox'

export function ProjectsView({ id }: { id: string }) {
  const [search, setSearch] = useState('')
  const resource = useResource<Project>(id, 'projects', { query: useDebouncedValue(search) })

  return (
    <>
      <PageHeader
        title="Projects"
        description="Discovered manifests and the lockfiles used to resolve each project."
        total={resource.total}
      />
      <div className="filter-bar">
        <SearchBox value={search} onChange={setSearch} placeholder="Search project name or path…" />
      </div>
      <DataPanel resource={resource}>{(items) => <ProjectsTable items={items} />}</DataPanel>
    </>
  )
}
