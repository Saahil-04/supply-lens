import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type PointerEvent as ReactPointerEvent,
} from 'react'

type Bounds = { minX: number; minY: number; maxX: number; maxY: number }
type Size = { width: number; height: number }
type View = {
  /** Screen-space translation and scale applied to the scene. */
  x: number
  y: number
  k: number
  /** True once the user has panned or zoomed; the view then stops auto-fitting on resize. */
  touched: boolean
}

const MIN_ZOOM = 0.08
const MAX_ZOOM = 6
const FIT_MAX_ZOOM = 1.4
const KEY_PAN_STEP = 60
const DRAG_THRESHOLD = 4

const clampZoom = (k: number) => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, k))

function fitView(bounds: Bounds, { width, height }: Size): View {
  const k = Math.min(FIT_MAX_ZOOM, width / (bounds.maxX - bounds.minX), height / (bounds.maxY - bounds.minY))
  const cx = (bounds.minX + bounds.maxX) / 2
  const cy = (bounds.minY + bounds.maxY) / 2
  return { x: width / 2 - cx * k, y: height / 2 - cy * k, k, touched: false }
}

/**
 * Pan/zoom state for an SVG scene rendered inside `containerRef`.
 *
 * - Drag to pan, Ctrl/Cmd + wheel (or trackpad pinch) to zoom toward the cursor.
 * - Keyboard: arrows pan, `+` / `-` zoom, `0` fits the scene.
 * - The scene refits whenever `sceneKey` changes, and on resize until the user interacts.
 */
export function useViewport({ bounds, sceneKey }: { bounds: Bounds; sceneKey: unknown }) {
  // A callback ref (kept in state) so effects re-run if the element is ever replaced.
  const [container, setContainer] = useState<HTMLDivElement | null>(null)
  const [size, setSize] = useState<Size>({ width: 0, height: 0 })
  const [view, setView] = useState<View>({ x: 0, y: 0, k: 1, touched: false })
  const [fitted, setFitted] = useState<{ sceneKey: unknown } & Size>({ sceneKey: null, width: 0, height: 0 })
  const [dragging, setDragging] = useState(false)
  const drag = useRef<{ x: number; y: number; view: View; moved: boolean } | null>(null)
  const justDragged = useRef(false)

  // Track the container size.
  useEffect(() => {
    if (!container) return
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect
      setSize((current) => (current.width === width && current.height === height ? current : { width, height }))
    })
    observer.observe(container)
    return () => observer.disconnect()
  }, [container])

  // Fit a new scene, and refit on resize while the user has not moved the view.
  const sizeChanged = fitted.width !== size.width || fitted.height !== size.height
  if (size.width > 0 && (fitted.sceneKey !== sceneKey || (sizeChanged && !view.touched))) {
    setFitted({ sceneKey, ...size })
    setView(fitView(bounds, size))
  }

  const zoomAt = useCallback((px: number, py: number, factor: number) => {
    setView((v) => {
      const k = clampZoom(v.k * factor)
      const ratio = k / v.k
      return { x: px - (px - v.x) * ratio, y: py - (py - v.y) * ratio, k, touched: true }
    })
  }, [])

  const zoomBy = useCallback(
    (factor: number) => zoomAt(size.width / 2, size.height / 2, factor),
    [zoomAt, size.width, size.height],
  )

  const fit = useCallback(() => setView(fitView(bounds, size)), [bounds, size])

  /** Pans so the layout point (x, y) sits in the middle of the container. */
  const centerOn = useCallback(
    (x: number, y: number) => {
      setView((v) => {
        const k = Math.max(v.k, 0.6)
        return { x: size.width / 2 - x * k, y: size.height / 2 - y * k, k, touched: true }
      })
    },
    [size.width, size.height],
  )

  // React attaches wheel listeners as passive, so zooming needs a native listener.
  useEffect(() => {
    const element = container
    if (!element) return
    const onWheel = (event: WheelEvent) => {
      // Plain scrolling keeps scrolling the page; zoom needs Ctrl/Cmd (or a pinch gesture).
      if (!event.ctrlKey && !event.metaKey) return
      event.preventDefault()
      const rect = element.getBoundingClientRect()
      const delta = Math.max(-100, Math.min(100, event.deltaY))
      zoomAt(event.clientX - rect.left, event.clientY - rect.top, Math.exp(-delta * 0.0022))
    }
    element.addEventListener('wheel', onWheel, { passive: false })
    return () => element.removeEventListener('wheel', onWheel)
  }, [container, zoomAt])

  const onPointerDown = (event: ReactPointerEvent<HTMLElement>) => {
    if (event.button !== 0) return
    drag.current = { x: event.clientX, y: event.clientY, view, moved: false }
  }

  const onPointerMove = (event: ReactPointerEvent<HTMLElement>) => {
    const origin = drag.current
    if (!origin) return
    const dx = event.clientX - origin.x
    const dy = event.clientY - origin.y
    if (!origin.moved && Math.hypot(dx, dy) < DRAG_THRESHOLD) return
    if (!origin.moved) {
      origin.moved = true
      setDragging(true)
      // Capture only once a real drag starts, so plain clicks still reach nodes.
      event.currentTarget.setPointerCapture(event.pointerId)
    }
    setView({ ...origin.view, x: origin.view.x + dx, y: origin.view.y + dy, touched: true })
  }

  const endDrag = () => {
    if (drag.current?.moved) {
      justDragged.current = true
      // Swallow the click that follows a drag, then re-arm.
      window.setTimeout(() => (justDragged.current = false), 0)
    }
    drag.current = null
    setDragging(false)
  }

  const onKeyDown = (event: ReactKeyboardEvent<HTMLElement>) => {
    const pan = (dx: number, dy: number) =>
      setView((v) => ({ ...v, x: v.x + dx, y: v.y + dy, touched: true }))
    switch (event.key) {
      case 'ArrowLeft': pan(KEY_PAN_STEP, 0); break
      case 'ArrowRight': pan(-KEY_PAN_STEP, 0); break
      case 'ArrowUp': pan(0, KEY_PAN_STEP); break
      case 'ArrowDown': pan(0, -KEY_PAN_STEP); break
      case '+':
      case '=': zoomBy(1.25); break
      case '-': zoomBy(1 / 1.25); break
      case '0': fit(); break
      default: return
    }
    event.preventDefault()
  }

  return {
    bindContainer: setContainer,
    view,
    dragging,
    /** True right after a drag ends, so a canvas click handler can ignore it. */
    wasDragged: () => justDragged.current,
    zoomIn: () => zoomBy(1.25),
    zoomOut: () => zoomBy(1 / 1.25),
    fit,
    centerOn,
    containerProps: { onPointerDown, onPointerMove, onPointerUp: endDrag, onPointerCancel: endDrag, onKeyDown },
  }
}

export type Viewport = ReturnType<typeof useViewport>
