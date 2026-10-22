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

export function VulnerabilitiesView({ id, onError }: { id: string; onError: (e: string) => void }) {
  const [query, setQuery] = useState('')
  const [severity, setSeverity] = useState('')
  const [hasFix, setHasFix] = useState('')
  const [selected, setSelected] = useState<Vulnerability | null>(null)
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const extra = useMemo(
    () =>
      qs({
        severity: severity || undefined,
        has_fix: hasFix === '' ? undefined : hasFix === 'true',
      }),
    [severity, hasFix],
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
        body="OSV advisory findings mapped to installed package instances. A finding does not by itself prove runtime exploitability."
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
