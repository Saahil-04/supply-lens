import { useMemo, useState } from 'react'
import { qs, type Page, type Recommendation } from '../api'
import { useResource } from '../hooks/useResource'
import { RecommendationCard } from '../components/recommendations/RecommendationCard'
import { Pagination } from '../components/ui/Pagination'
import { ResourceHeader } from '../components/ui/ResourceHeader'
import { SearchBox } from '../components/ui/SearchBox'
import { TableState } from '../components/ui/TableState'

export function RecommendationsView({ id }: { id: string }) {
  const [query, setQuery] = useState('')
  const [hasFix, setHasFix] = useState('')
  const extra = useMemo(() => qs({ has_fix: hasFix === '' ? undefined : hasFix === 'true' }), [hasFix])
  const q = useResource<Recommendation>(id, 'recommendations', query, extra)
  const items = q.page?.items || []

  return (
    <>
      <ResourceHeader
        eyebrow="REMEDIATION"
        title="Recommendations"
        body="Prioritize updates suggested by the analysis. Verify compatibility and regression-test changes before merging."
        total={q.page?.pagination.total}
      />
      <div className="toolbar">
        <SearchBox value={query} onChange={setQuery} placeholder="Search package or recommendation…" />
        <select className="filter-select" value={hasFix} onChange={(e) => setHasFix(e.target.value)}>
          <option value="">All recommendations</option>
          <option value="true">Fix available</option>
          <option value="false">No fix listed</option>
        </select>
      </div>
      <div className="recommendation-list">
        <TableState loading={q.loading} error={q.error} empty={!q.loading && !q.error && items.length === 0} />
        {items.map((r, i) => (
          <RecommendationCard key={`${r.package_name}-${r.installed_version}-${i}`} r={r} />
        ))}
      </div>
      <Pagination page={q.page as Page<unknown> | null} offset={q.offset} setOffset={q.setOffset} />
    </>
  )
}
