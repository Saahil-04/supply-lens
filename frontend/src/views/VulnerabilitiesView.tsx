import { useMemo, useState } from 'react'
import { qs, request, type Page, type Vulnerability } from '../api'
import { useResource } from '../hooks/useResource'
import { errorText } from '../lib/format'
import { Pagination } from '../components/ui/Pagination'
import { ResourceHeader } from '../components/ui/ResourceHeader'
import { SearchBox } from '../components/ui/SearchBox'
import { TableState } from '../components/ui/TableState'
import { VulnerabilityModal } from '../components/vulnerabilities/VulnerabilityModal'
import { VulnerabilityTable } from '../components/vulnerabilities/VulnerabilityTable'

const SEVERITIES = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'UNKNOWN']
const REACHABILITY_OPTIONS = [
  ['imported', 'Imported by your code'],
  ['transitive_of_imported', 'Used via a dependency'],
  ['tests_or_tooling_only', 'Tests / tooling only'],
  ['dev_only', 'Dev dependency'],
  ['not_imported', 'Not imported'],
  ['unknown', 'Unknown'],
]

export function VulnerabilitiesView({ id, onError }: { id: string; onError: (e: string) => void }) {
  const [query, setQuery] = useState('')
  const [severity, setSeverity] = useState('')
  const [hasFix, setHasFix] = useState('')
  const [reachability, setReachability] = useState('')
  const [sort, setSort] = useState('priority')
  const [selected, setSelected] = useState<Vulnerability | null>(null)
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const extra = useMemo(
    () =>
      qs({
        severity: severity || undefined,
        has_fix: hasFix === '' ? undefined : hasFix === 'true',
        reachability: reachability || undefined,
        sort,
      }),
    [severity, hasFix, reachability, sort],
  )
  const q = useResource<Vulnerability>(id, 'vulnerabilities', query, extra)
  const items = q.page?.items || []

  const openDetail = async (v: Vulnerability) => {
    setSelected(v)
    setDetail(null)
    setDetailLoading(true)
    try {
      setDetail(
        await request<Record<string, unknown>>(
          v.links?.detail ||
            `/analyses/${encodeURIComponent(id)}/vulnerabilities/${encodeURIComponent(v.finding_id)}`,
        ),
      )
    } catch (e) {
      onError(errorText(e))
    } finally {
      setDetailLoading(false)
    }
  }

  return (
    <>
      <ResourceHeader
        eyebrow="SECURITY FINDINGS"
        title="Vulnerabilities"
        body="OSV advisory findings mapped to installed package instances, ranked by priority (severity adjusted for whether the package is actually used). A finding does not by itself prove runtime exploitability."
        total={q.page?.pagination.total}
      />
      <div className="toolbar">
        <SearchBox value={query} onChange={setQuery} placeholder="Search advisory, package, or summary…" />
        <select className="filter-select" value={severity} onChange={(e) => setSeverity(e.target.value)}>
          <option value="">All severities</option>
          {SEVERITIES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select className="filter-select" value={hasFix} onChange={(e) => setHasFix(e.target.value)}>
          <option value="">Fix availability</option>
          <option value="true">Fix available</option>
          <option value="false">No known fix</option>
        </select>
        <select className="filter-select" value={reachability} onChange={(e) => setReachability(e.target.value)}>
          <option value="">All usage states</option>
          {REACHABILITY_OPTIONS.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <select className="filter-select" value={sort} onChange={(e) => setSort(e.target.value)}>
          <option value="priority">Sort: priority</option>
          <option value="severity">Sort: severity</option>
        </select>
      </div>

      <div className="table-card">
        <TableState loading={q.loading} error={q.error} empty={!q.loading && !q.error && items.length === 0} />
        {items.length > 0 && <VulnerabilityTable items={items} onSelect={(v) => void openDetail(v)} />}
      </div>
      <Pagination page={q.page as Page<unknown> | null} offset={q.offset} setOffset={q.setOffset} />

      {selected && (
        <VulnerabilityModal
          selected={selected}
          detail={detail}
          loading={detailLoading}
          onClose={() => setSelected(null)}
        />
      )}
    </>
  )
}
