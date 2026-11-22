import { useCallback, useEffect, useState } from 'react'
import { STORAGE_KEYS, storage } from '../lib/storage'

export type Theme = 'light' | 'dark'

function initialTheme(): Theme {
  const saved = storage.get(STORAGE_KEYS.theme)
  if (saved === 'light' || saved === 'dark') return saved
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

/** Light/dark theme, persisted and applied to `<html data-theme>`. */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(initialTheme)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    storage.set(STORAGE_KEYS.theme, theme)
  }, [theme])

  const toggleTheme = useCallback(() => setTheme((current) => (current === 'light' ? 'dark' : 'light')), [])
  return { theme, toggleTheme }
}
