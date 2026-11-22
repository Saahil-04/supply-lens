import { fetchOk } from '../api'

/** Downloads the CycloneDX SBOM for an analysis. Throws an `ApiError` if the request fails. */
export async function downloadSbom(analysisId: string) {
  const response = await fetchOk(`/analyses/${encodeURIComponent(analysisId)}/sbom`)
  const blob = await response.blob()
  const disposition = response.headers.get('content-disposition') ?? ''
  const filename = disposition.match(/filename="?([^";]+)"?/i)?.[1] ?? `supplylens-${analysisId}.cdx.json`

  const href = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = href
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(href)
}
