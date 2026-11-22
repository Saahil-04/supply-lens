import { LoaderCircle } from 'lucide-react'

export function Spinner({ size = 16 }: { size?: number }) {
  return <LoaderCircle className="spin" size={size} aria-hidden="true" />
}
