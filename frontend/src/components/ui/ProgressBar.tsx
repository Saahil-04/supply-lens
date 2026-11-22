import type { Tone } from '../../lib/format'

export function ProgressBar({ value, max, tone = 'info' }: { value: number; max: number; tone?: Tone }) {
  const percent = max > 0 ? Math.min(100, (value / max) * 100) : 0
  return (
    <div className="progress" role="presentation">
      <div className={`progress-fill progress-${tone}`} style={{ width: `${percent}%` }} />
    </div>
  )
}
