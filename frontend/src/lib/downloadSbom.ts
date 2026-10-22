    import { apiUrl } from '../api'
import { errorText } from './format'

export async function downloadSbom(id: string, setError: (e: string) => void) {
  try {
    const response = await fetch(apiUrl(`/analyses/${encodeURIComponent(id)}/sbom`))
    if (!response.ok) {
      let message = `${response.status} ${response.statusText}`
      try {
        const body = await response.json()
        message = body.detail || message
      } catch {
        /* response body was not JSON; keep the status text */
      }
      throw new Error(message)
    }
    const blob = await response.blob()
    const disposition = response.headers.get('content-disposition') || ''
    const filename = disposition.match(/filename="?([^";]+)"?/i)?.[1] || `supplylens-${id}.cdx.json`
    const href = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = href
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(href)
  } catch (e) {
    setError(errorText(e))
  }
}
