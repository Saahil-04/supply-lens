import { useState } from 'react'
import type { PackageItem } from '../api'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import { useResource } from '../hooks/useResource'
import { triState, withDefault } from '../lib/filters'
import { PackagesTable } from '../components/packages/PackagesTable'
import { DataPanel } from '../components/ui/DataPanel'
import { FilterBar } from '../components/ui/FilterBar'
import { PageHeader } from '../components/ui/PageHeader'
import { Select } from '../components/ui/Select'

const TYPE_OPTIONS = withDefault('All dependency types', [
  { value: 'true', label: 'Direct only' },
  { value: 'false', label: 'Transitive only' },
])
const SCOPE_OPTIONS = withDefault('All scopes', [
  { value: 'true', label: 'Development' },
  { value: 'false', label: 'Non-development' },
])

export function PackagesView({ id }: { id: string }) {
  const [search, setSearch] = useState('')
  const [direct, setDirect] = useState('')
  const [dev, setDev] = useState('')

  const resource = useResource<PackageItem>(id, 'packages', {
    query: useDebouncedValue(search),
    filters: { direct: triState(direct), is_dev: triState(dev) },
  })

  return (
    <>
      <PageHeader
        title="Packages"
        description="Resolved package instances across project lockfiles. The same version in different lockfiles is listed separately."
        total={resource.total}
      />
      <FilterBar
        search={search}
        onSearchChange={setSearch}
        searchPlaceholder="Search package, version or path…"
        isFiltered={!!(search || direct || dev)}
        onReset={() => {
          setSearch('')
          setDirect('')
          setDev('')
        }}
      >
        <Select label="Dependency type" value={direct} onChange={setDirect} options={TYPE_OPTIONS} />
        <Select label="Scope" value={dev} onChange={setDev} options={SCOPE_OPTIONS} />
      </FilterBar>
      <DataPanel resource={resource}>{(items) => <PackagesTable items={items} />}</DataPanel>
    </>
  )
}
