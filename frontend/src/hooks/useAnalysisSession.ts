import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { request, type Analysis } from '../api'
import { errorText } from '../lib/format'
import { storedAnalysisKey, storedUrlKey } from '../lib/storage'

const GITHUB_REPO_URL = /^https?:\/\/(www\.)?github\.com\/[\w.-]+\/[\w.-]+\/?$/

/**
 * Owns everything about the current scan: API health, the repository URL input,
 * the loaded analysis, and the actions that change them.
 * `onShowOverview` lets the host switch back to the Overview tab after a scan or reset.
 */
export function useAnalysisSession({ onShowOverview }: { onShowOverview: () => void }) {
  const [repositoryUrl, setRepositoryUrl] = useState(() => localStorage.getItem(storedUrlKey) || '')
  const [analysisId, setAnalysisId] = useState(() => localStorage.getItem(storedAnalysisKey) || '')
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [loading, setLoading] = useState(false)
  const [checking, setChecking] = useState(false)
  const [error, setError] = useState('')
  const [apiOnline, setApiOnline] = useState<boolean | null>(null)

  const loadAnalysis = useCallback(async (id: string) => {
    if (!id) return
    setChecking(true)
    try {
      const result = await request<Analysis>(`/analyses/${encodeURIComponent(id)}`)
      setAnalysis(result)
      setError('')
    } catch (e) {
      setAnalysis(null)
      setError(errorText(e))
    } finally {
      setChecking(false)
    }
  }, [])

  const checkApi = useCallback(
    () =>
      request<{ status: string }>('/health')
        .then(() => setApiOnline(true))
        .catch(() => setApiOnline(false)),
    [],
  )

  useEffect(() => {
    void checkApi()
  }, [checkApi])

  useEffect(() => {
    if (analysisId) void loadAnalysis(analysisId)
  }, [analysisId, loadAnalysis])

  const runAnalysis = async (event: FormEvent) => {
    event.preventDefault()
    const url = repositoryUrl.trim()
    if (!GITHUB_REPO_URL.test(url)) {
      setError('Enter a GitHub repository URL, for example https://github.com/owner/repo')
      return
    }
    setLoading(true)
    setError('')
    setAnalysis(null)
    try {
      localStorage.setItem(storedUrlKey, url)
      const result = await request<Analysis>('/analyze', {
        method: 'POST',
        body: JSON.stringify({ repository_url: url }),
      })
      setAnalysisId(result.analysis_id)
      localStorage.setItem(storedAnalysisKey, result.analysis_id)
      setAnalysis(result)
      onShowOverview()
    } catch (e) {
      setError(errorText(e))
    } finally {
      setLoading(false)
    }
  }

  const forgetAnalysis = () => {
    setAnalysisId('')
    setAnalysis(null)
    setError('')
    localStorage.removeItem(storedAnalysisKey)
    onShowOverview()
  }

  return {
    repositoryUrl,
    setRepositoryUrl,
    analysisId,
    analysis,
    loading,
    checking,
    error,
    setError,
    apiOnline,
    checkApi,
    loadAnalysis,
    runAnalysis,
    forgetAnalysis,
  }
}
