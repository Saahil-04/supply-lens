import { useCallback, useSyncExternalStore } from 'react'
import { DEFAULT_TAB, isTabId, type TabId } from '../lib/tabs'

const subscribe = (onChange: () => void) => {
  window.addEventListener('hashchange', onChange)
  return () => window.removeEventListener('hashchange', onChange)
}
const getHash = () => window.location.hash

function parseTab(hash: string): TabId {
  const slug = hash.replace(/^#\/?/, '')
  return isTabId(slug) ? slug : DEFAULT_TAB
}

/** The active tab, stored in the URL hash (`#/packages`) so refresh and back/forward work. */
export function useTabRoute() {
  const hash = useSyncExternalStore(subscribe, getHash, () => '')
  const navigate = useCallback((tab: TabId) => {
    window.location.hash = `/${tab}`
  }, [])
  return [parseTab(hash), navigate] as const
}
