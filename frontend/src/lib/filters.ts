import type { SelectOption } from '../components/ui/Select'

/** Maps a yes/no/any `<select>` value ('' | 'true' | 'false') to a query value. */
export const triState = (value: string) => (value === '' ? undefined : value === 'true')

export const withDefault = (label: string, options: SelectOption[]): SelectOption[] => [
  { value: '', label },
  ...options,
]
