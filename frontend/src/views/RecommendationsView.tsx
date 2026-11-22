import { useState } from 'react'
import type { Recommendation } from '../api'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import { useResource } from '../hooks/useResource'
import { triState, withDefault } from '../lib/filters'
import { RecommendationCard } from '../components/recommendations/RecommendationCard'
import { DataPanel } from '../components/ui/DataPanel'
import { FilterBar } from '../components/ui/FilterBar'
import { PageHeader } from '../components/ui/PageHeader'
import { Select } from '../components/ui/Select'

const FIX_OPTIONS = withDefault('All recommendations', [
  { value: 'true', label: 'Fix available' },
  { value: 'false', label: 'No fix listed' },
])

export function RecommendationsView({ id }: { id: string }) {
  const [search, setSearch] = useState('')
  const [hasFix, setHasFix] = useState('')

  const resource = useResource<Recommendation>(id, 'recommendations', {
    query: useDebouncedValue(search),
    filters: { has_fix: triState(hasFix) },
  })

  return (
    <>
      <PageHeader
        title="Recommendations"
        description="Suggested updates, most urgent first. Verify compatibility and regression-test each change before merging."
        total={resource.total}
      />
      <FilterBar
        search={search}
        onSearchChange={setSearch}
        searchPlaceholder="Search package or recommendation…"
        isFiltered={!!(search || hasFix)}
        onReset={() => {
          setSearch('')
          setHasFix('')
        }}
      >
        <Select label="Fix availability" value={hasFix} onChange={setHasFix} options={FIX_OPTIONS} />
      </FilterBar>
      <DataPanel resource={resource} surface="plain">
        {(items) => (
          <div className="recommendation-list">
            {items.map((item, index) => (
              <RecommendationCard
                key={`${item.package_id ?? item.package_name}-${item.installed_version}-${index}`}
                recommendation={item}
              />
            ))}
          </div>
        )}
      </DataPanel>
    </>
  )
}
