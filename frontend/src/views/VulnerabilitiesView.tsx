import { useState } from 'react'
import type { Vulnerability } from '../api'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import { useResource } from '../hooks/useResource'
import { REACHABILITY, SEVERITIES } from '../lib/format'
import { triState, withDefault } from '../lib/filters'
import { VulnerabilityDrawer } from '../components/vulnerabilities/VulnerabilityDrawer'
import { VulnerabilityTable } from '../components/vulnerabilities/VulnerabilityTable'
import { DataPanel } from '../components/ui/DataPanel'
import { FilterBar } from '../components/ui/FilterBar'
import { PageHeader } from '../components/ui/PageHeader'
import { Select } from '../components/ui/Select'

const DEFAULT_SORT = 'priority'

const SEVERITY_OPTIONS = withDefault(
  'All severities',
  SEVERITIES.map((value) => ({ value, label: value.charAt(0) + value.slice(1).toLowerCase() })),
)
const FIX_OPTIONS = withDefault('Any fix status', [
  { value: 'true', label: 'Fix available' },
  { value: 'false', label: 'No known fix' },
])
const USAGE_OPTIONS = withDefault(
  'All usage states',
  Object.entries(REACHABILITY).map(([value, { label }]) => ({ value, label })),
)
const SORT_OPTIONS = [
  { value: 'priority', label: 'Sort by priority' },
  { value: 'severity', label: 'Sort by severity' },
]

export function VulnerabilitiesView({ id }: { id: string }) {
  const [search, setSearch] = useState('')
  const [severity, setSeverity] = useState('')
  const [hasFix, setHasFix] = useState('')
  const [usage, setUsage] = useState('')
  const [sort, setSort] = useState(DEFAULT_SORT)
  const [selected, setSelected] = useState<Vulnerability | null>(null)

  const resource = useResource<Vulnerability>(id, 'vulnerabilities', {
    query: useDebouncedValue(search),
    filters: { severity, has_fix: triState(hasFix), reachability: usage, sort },
  })

  const reset = () => {
    setSearch('')
    setSeverity('')
    setHasFix('')
    setUsage('')
    setSort(DEFAULT_SORT)
  }

  return (
    <>
      <PageHeader
        title="Vulnerabilities"
        description="OSV advisories mapped to installed packages and ranked by priority: severity, adjusted for whether the package is actually used. A finding alone does not prove it can be exploited."
        total={resource.total}
      />
      <FilterBar
        search={search}
        onSearchChange={setSearch}
        searchPlaceholder="Search advisory, package or summary…"
        isFiltered={!!(search || severity || hasFix || usage || sort !== DEFAULT_SORT)}
        onReset={reset}
      >
        <Select label="Severity" value={severity} onChange={setSeverity} options={SEVERITY_OPTIONS} />
        <Select label="Fix availability" value={hasFix} onChange={setHasFix} options={FIX_OPTIONS} />
        <Select label="Usage" value={usage} onChange={setUsage} options={USAGE_OPTIONS} />
        <Select label="Sort order" value={sort} onChange={setSort} options={SORT_OPTIONS} />
      </FilterBar>

      <DataPanel resource={resource}>
        {(items) => <VulnerabilityTable items={items} onSelect={setSelected} />}
      </DataPanel>

      {selected && (
        <VulnerabilityDrawer
          key={selected.finding_id}
          analysisId={id}
          selected={selected}
          onClose={() => setSelected(null)}
        />
      )}
    </>
  )
}
