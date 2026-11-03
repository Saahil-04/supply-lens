import { useEffect, useMemo, useRef, useState } from 'react'
import type { KeyboardEvent as ReactKeyboardEvent } from 'react'
import { Check, ChevronDown, GitBranch, LoaderCircle, Search, X } from 'lucide-react'
import type { PackageItem } from '../../api'

export function GraphControls({
  query,
  onQueryChange,
  packages,
  totalPackages,
  loadingPackages,
  selectedId,
  onSelectedIdChange,
  depth,
  onDepthChange,
  direction,
  onDirectionChange,
  loading,
  onLoad,
}: {
  query: string
  onQueryChange: (q: string) => void
  packages: PackageItem[]
  totalPackages: number
  loadingPackages: boolean
  selectedId: string
  onSelectedIdChange: (id: string) => void
  depth: string
  onDepthChange: (d: string) => void
  direction: string
  onDirectionChange: (d: string) => void
  loading: boolean
  onLoad: () => void
}) {
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const rootRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const selectedPackage = useMemo(
    () => packages.find((pkg) => pkg.id === selectedId),
    [packages, selectedId],
  )

  useEffect(() => {
    if (!open) return
    const handlePointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false)
    }
    const handleKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('pointerdown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open])

  const choose = (pkg: PackageItem) => {
    onSelectedIdChange(pkg.id)
    onQueryChange('')
    setOpen(false)
  }

  const handleInputKeyDown = (event: ReactKeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setOpen(true)
      setActiveIndex((index) => Math.min(index + 1, Math.max(packages.length - 1, 0)))
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActiveIndex((index) => Math.max(index - 1, 0))
    } else if (event.key === 'Enter' && packages[activeIndex]) {
      event.preventDefault()
      choose(packages[activeIndex])
    }
  }

  return (
    <div className="graph-controls panel">
      <div className="graph-package-field" ref={rootRef}>
        <label htmlFor="graph-package-search">Root package</label>
        <div className={`graph-package-picker ${open ? 'is-open' : ''}`}>
          <Search size={16} aria-hidden="true" />
          <input
            id="graph-package-search"
            ref={inputRef}
            role="combobox"
            aria-expanded={open}
            aria-controls="graph-package-options"
            aria-autocomplete="list"
            value={open ? query : selectedPackage ? `${selectedPackage.name}@${selectedPackage.version}` : (selectedId ? selectedId : query)}
            onFocus={() => setOpen(true)}
            onClick={() => setOpen(true)}
            onChange={(event) => {
              onQueryChange(event.target.value)
              setActiveIndex(0)
              setOpen(true)
            }}
            onKeyDown={handleInputKeyDown}
            placeholder={loadingPackages ? 'Loading packages…' : 'Search packages by name, version or path…'}
            disabled={loadingPackages}
          />
          {query ? (
            <button type="button" aria-label="Clear package search" onClick={() => { onQueryChange(''); inputRef.current?.focus() }}>
              <X size={15} />
            </button>
          ) : (
            <button type="button" aria-label="Show package choices" onClick={() => { setOpen((value) => !value); inputRef.current?.focus() }}>
              <ChevronDown size={16} />
            </button>
          )}
          {open && (
            <div className="graph-package-menu" id="graph-package-options" role="listbox" aria-label="Package choices">
              {loadingPackages ? (
                <div className="graph-package-empty"><LoaderCircle size={15} className="spin" /> Loading package inventory…</div>
              ) : packages.length ? (
                packages.slice(0, 250).map((pkg, index) => (
                  <button
                    type="button"
                    role="option"
                    aria-selected={pkg.id === selectedId}
                    className={`graph-package-option ${pkg.id === selectedId ? 'is-selected' : ''} ${index === activeIndex ? 'is-active' : ''}`}
                    key={pkg.id}
                    onMouseEnter={() => setActiveIndex(index)}
                    onClick={() => choose(pkg)}
                  >
                    <span className="graph-package-option-copy">
                      <strong>{pkg.name}<span>@{pkg.version}</span></strong>
                      <small title={`${pkg.lockfile || ''} · ${pkg.path || ''}`}>{pkg.lockfile || 'Lockfile unknown'} · {pkg.path || pkg.id}</small>
                    </span>
                    {pkg.id === selectedId && <Check size={16} />}
                  </button>
                ))
              ) : (
                <div className="graph-package-empty">No packages match this search.</div>
              )}
              {packages.length > 250 && <div className="graph-package-footer">Showing first 250 matches. Refine your search to narrow the list.</div>}
            </div>
          )}
        </div>
        <span className="field-hint">
          {loadingPackages
            ? 'Loading the complete package inventory…'
            : `Showing ${packages.length.toLocaleString()} matching packages of ${totalPackages.toLocaleString()} total package instances.`}
        </span>
      </div>
      <div className="graph-option">
        <label>Depth</label>
        <select className="filter-select" value={depth} onChange={(e) => onDepthChange(e.target.value)}>
          {[0, 1, 2, 3].map((d) => <option key={d} value={d}>{d} hop{d === 1 ? '' : 's'}</option>)}
        </select>
      </div>
      <div className="graph-option">
        <label>Direction</label>
        <select className="filter-select" value={direction} onChange={(e) => onDirectionChange(e.target.value)}>
          <option value="both">Both</option>
          <option value="in">Dependencies of</option>
          <option value="out">Dependents of</option>
        </select>
      </div>
      <button className="button button-primary graph-submit" onClick={onLoad} disabled={!selectedId || loading}>
        {loading ? <LoaderCircle size={15} className="spin" /> : <GitBranch size={15} />} Load graph
      </button>
    </div>
  )
}
