import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { Check, ChevronDown, Search, X } from 'lucide-react'
import type { PackageItem } from '../../api'
import { formatNumber, packageLabel } from '../../lib/format'
import { Spinner } from '../ui/Spinner'

const MAX_OPTIONS = 250

const matches = (pkg: PackageItem, needle: string) =>
  [pkg.name, pkg.version, pkg.path, pkg.lockfile, pkg.id].some((value) => String(value ?? '').toLowerCase().includes(needle))

type Props = {
  packages: PackageItem[]
  selectedId: string
  onSelect: (id: string) => void
  loading: boolean
}

/** Searchable combobox over every package instance in the analysis. */
export function PackagePicker({ packages, selectedId, onSelect, loading }: Props) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [highlighted, setHighlighted] = useState(0)
  const rootRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const listId = useId()

  const selected = useMemo(() => packages.find((pkg) => pkg.id === selectedId), [packages, selectedId])
  const results = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return needle ? packages.filter((pkg) => matches(pkg, needle)) : packages
  }, [packages, query])
  const visible = results.slice(0, MAX_OPTIONS)
  const active = Math.min(highlighted, Math.max(visible.length - 1, 0))

  useEffect(() => {
    if (!open) return
    const onPointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false)
    }
    const onKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  // Keep the highlighted option visible while navigating with the keyboard.
  useEffect(() => {
    if (open) listRef.current?.children[active]?.scrollIntoView({ block: 'nearest' })
  }, [open, active])

  const choose = (pkg: PackageItem) => {
    onSelect(pkg.id)
    setQuery('')
    setOpen(false)
  }

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault()
        setOpen(true)
        setHighlighted(Math.min(active + 1, visible.length - 1))
        break
      case 'ArrowUp':
        event.preventDefault()
        setHighlighted(Math.max(active - 1, 0))
        break
      case 'Enter':
        if (open && visible[active]) {
          event.preventDefault()
          choose(visible[active])
        }
        break
    }
  }

  const selectedLabel = selected ? packageLabel(selected.name, selected.version) : ''

  return (
    <div className="field" ref={rootRef}>
      <label className="field-label" htmlFor={`${listId}-input`}>
        Package
        <span className="field-label-hint">
          {loading ? 'Loading inventory…' : `${formatNumber(packages.length)} in this analysis`}
        </span>
      </label>
      <div className={`combobox ${open ? 'is-open' : ''}`.trim()}>
        <Search size={16} aria-hidden="true" />
        <input
          id={`${listId}-input`}
          ref={inputRef}
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={open && visible[active] ? `${listId}-${active}` : undefined}
          autoComplete="off"
          spellCheck={false}
          disabled={loading}
          value={open ? query : selectedLabel}
          placeholder={loading ? 'Loading packages…' : open && selectedLabel ? selectedLabel : 'Search by name, version or path…'}
          onFocus={() => setOpen(true)}
          onClick={() => setOpen(true)}
          onChange={(event) => {
            setQuery(event.target.value)
            setHighlighted(0)
            setOpen(true)
          }}
          onKeyDown={onKeyDown}
        />
        {open && query ? (
          <button type="button" className="icon-button" aria-label="Clear search" onClick={() => { setQuery(''); inputRef.current?.focus() }}>
            <X size={15} />
          </button>
        ) : (
          <button
            type="button"
            className="icon-button"
            tabIndex={-1}
            aria-label={open ? 'Hide package list' : 'Show package list'}
            onClick={() => { setOpen((value) => !value); inputRef.current?.focus() }}
          >
            <ChevronDown size={16} />
          </button>
        )}

        {open && (
          <div className="combobox-menu">
            {loading ? (
              <div className="combobox-empty">
                <Spinner size={15} /> Loading package inventory…
              </div>
            ) : visible.length ? (
              <div id={listId} ref={listRef} role="listbox" aria-label="Packages" className="combobox-list">
                {visible.map((pkg, index) => (
                  <button
                    key={pkg.id}
                    id={`${listId}-${index}`}
                    type="button"
                    role="option"
                    aria-selected={pkg.id === selectedId}
                    className={`combobox-option ${index === active ? 'is-highlighted' : ''}`.trim()}
                    onMouseEnter={() => setHighlighted(index)}
                    onClick={() => choose(pkg)}
                  >
                    <span className="combobox-option-text">
                      <strong>
                        {pkg.name}
                        {pkg.version && <span>@{pkg.version}</span>}
                      </strong>
                      <small title={`${pkg.lockfile ?? ''} ${pkg.path ?? ''}`.trim()}>
                        {pkg.lockfile || 'Lockfile unknown'} · {pkg.path || pkg.id}
                      </small>
                    </span>
                    {pkg.id === selectedId && <Check size={15} aria-hidden="true" />}
                  </button>
                ))}
              </div>
            ) : (
              <div className="combobox-empty">No packages match “{query}”.</div>
            )}
            {results.length > MAX_OPTIONS && (
              <div className="combobox-footer">
                Showing the first {MAX_OPTIONS} of {formatNumber(results.length)} matches. Refine your search to narrow the list.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
