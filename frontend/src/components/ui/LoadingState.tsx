import { Spinner } from './Spinner'

export function LoadingState({ children }: { children: string }) {
  return (
    <div className="restoring" role="status">
      <Spinner size={18} /> {children}
    </div>
  )
}
