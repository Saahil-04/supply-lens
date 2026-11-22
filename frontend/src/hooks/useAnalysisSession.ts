import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { request, type Analysis } from '../api'
import { errorText } from '../lib/format'
import { STORAGE_KEYS, storage } from '../lib/storage'

const GITHUB_REPO_URL = /^https?:\/\/(www\.)?github\.com\/[\w.-]+\/[\w.-]+\/?$/
const STALE_ANALYSIS = /not found|expired/i

/**
 * Owns everything about the current analysis: service health, the repository
 * URL input, the loaded analysis, and the actions that change them.
 * `onShowOverview` lets the host return to the Overview tab after a run or reset.
 */
export function useAnalysisSession({ onShowOverview }: { onShowOverview: () => void }) {
  const [initialId] = useState(() => storage.get(STORAGE_KEYS.analysisId) ?? '')
  const [analysisId, setAnalysisId] = useState(initialId)
  const [repositoryUrl, setRepositoryUrl] = useState(() => storage.get(STORAGE_KEYS.repositoryUrl) ?? '')
  const [includeReachability, setIncludeReachability] = useState(true)
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [running, setRunning] = useState(false)
  const [refreshing, setRefreshing] = useState(!!initialId)
  const [error, setError] = useState('')
  const [apiOnline, setApiOnline] = useState<boolean | null>(null)

  const fetchAnalysis = useCallback(
    (id: string) =>
      request<Analysis>(`/analyses/${encodeURIComponent(id)}`)
        .then((result) => {
          setAnalysis(result)
          setError('')
        })
        .catch((e) => {
          setAnalysis(null)
          setError(errorText(e))
        })
        .finally(() => setRefreshing(false)),
    [],
  )

  const loadAnalysis = useCallback(
    (id: string) => {
      setRefreshing(true)
      return fetchAnalysis(id)
    },
    [fetchAnalysis],
  )

  const checkApi = useCallback(
    () =>
      request('/health').then(
        () => setApiOnline(true),
        () => setApiOnline(false),
      ),
    [],
  )

  useEffect(() => {
    void checkApi()
  }, [checkApi])

  // Restore the last analysis once on load.
  useEffect(() => {
    if (initialId) void fetchAnalysis(initialId)
  }, [initialId, fetchAnalysis])

  const runAnalysis = async (event: FormEvent) => {
    event.preventDefault()
    const url = repositoryUrl.trim()
    if (!GITHUB_REPO_URL.test(url)) {
      setError('Enter a GitHub repository URL, for example https://github.com/owner/repo')
      return
    }

    setRunning(true)
    setError('')
    setAnalysis(null)
    try {
      storage.set(STORAGE_KEYS.repositoryUrl, url)
      const result = await request<Analysis>('/analyze', {
        method: 'POST',
        body: JSON.stringify({ repository_url: url, include_reachability: includeReachability }),
      })
      storage.set(STORAGE_KEYS.analysisId, result.analysis_id)
      setAnalysisId(result.analysis_id)
      setAnalysis(result)
      onShowOverview()
    } catch (e) {
      setError(errorText(e))
    } finally {
      setRunning(false)
    }
  }

  const closeAnalysis = () => {
    storage.remove(STORAGE_KEYS.analysisId)
    setAnalysisId('')
    setAnalysis(null)
    setError('')
    onShowOverview()
  }

  return {
    analysis,
    repositoryUrl,
    setRepositoryUrl,
    includeReachability,
    setIncludeReachability,
    running,
    refreshing,
    error,
    dismissError: () => setError(''),
    setError,
    /** The stored analysis is gone (expired or unknown to the service), so offer a fresh start. */
    canStartOver: !!analysisId && STALE_ANALYSIS.test(error),
    apiOnline,
    checkApi,
    refresh: () => analysis && loadAnalysis(analysis.analysis_id),
    runAnalysis,
    closeAnalysis,
  }
}

export type AnalysisSession = ReturnType<typeof useAnalysisSession>
