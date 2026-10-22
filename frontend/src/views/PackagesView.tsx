import { useMemo, useState } from 'react'
import { qs, type PackageItem, type Page } from '../api'
import { useResource } from '../hooks/useResource'
import { PackagesTable } from '../components/packages/PackagesTable'
import { Pagination } from '../components/ui/Pagination'
import { ResourceHeader } from '../components/ui/ResourceHeader'
import { SearchBox } from '../components/ui/SearchBox'
import { TableState } from '../components/ui/TableState'

export function PackagesView({ id }: { id: string }) {
  const [query, setQuery] = useState('')
  const [direct, setDirect] = useState('')
  const [dev, setDev] = useState('')
  const extra = useMemo(
    () =>
      qs({
        direct: direct === '' ? undefined : direct === 'true',
        is_dev: dev === '' ? undefined : dev === 'true',
      }),
    [direct, dev],
  )
  const q = useResource<PackageItem>(id, 'packages', query, extra)
  const items = q.page?.items || []

  return (
    <>
      <ResourceHeader
        eyebrow="INVENTORY"
        title="Packages"
        body="Search resolved package instances across project lockfiles. Identical versions in different lockfiles remain separate instances."
        total={q.page?.pagination.total}
      />
      <div className="toolbar">
        <SearchBox value={query} onChange={setQuery} placeholder="Search package, version, or path…" />
        <select className="filter-select" value={direct} onChange={(e) => setDirect(e.target.value)}>
          <option value="">All dependency types</option>
          <option value="true">Direct only</option>
          <option value="false">Transitive only</option>
        </select>
        <select className="filter-select" value={dev} onChange={(e) => setDev(e.target.value)}>
          <option value="">All scopes</option>
          <option value="true">Development</option>
          <option value="false">Non-development</option>
        </select>
      </div>
      <div className="table-card">
        <TableState loading={q.loading} error={q.error} empty={!q.loading && !q.error && items.length === 0} />
        {items.length > 0 && <PackagesTable items={items} />}
      </div>
      <Pagination page={q.page as Page<unknown> | null} offset={q.offset} setOffset={q.setOffset} />
    </>
  )
}
