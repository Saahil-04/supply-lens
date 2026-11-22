/** Storage keys. The values are stable so existing users keep their last analysis and theme. */
export const STORAGE_KEYS = {
  analysisId: 'supplylens:last-analysis-id',
  repositoryUrl: 'supplylens:last-repository-url',
  theme: 'supplylens-theme',
} as const

/** `localStorage` wrapper that never throws (private mode, blocked storage, quota). */
export const storage = {
  get(key: string): string | null {
    try {
      return localStorage.getItem(key)
    } catch {
      return null
    }
  },
  set(key: string, value: string) {
    try {
      localStorage.setItem(key, value)
    } catch {
      /* Persistence is best-effort. */
    }
  },
  remove(key: string) {
    try {
      localStorage.removeItem(key)
    } catch {
      /* Persistence is best-effort. */
    }
  },
}
