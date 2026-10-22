import { ArrowRight, Package } from 'lucide-react'

export function EmptyState({ title, body, action }: { title: string; body: string; action: () => void }) {
  return (
    <div className="empty-state">
      <div className="empty-icon">
        <Package size={23} />
      </div>
      <h2>{title}</h2>
      <p>{body}</p>
      <button className="button button-primary" onClick={action}>
        Go to overview <ArrowRight size={15} />
      </button>
    </div>
  )
}
