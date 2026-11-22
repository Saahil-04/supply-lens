import { Boxes, GitBranch, LayoutDashboard, Package, ShieldAlert, Sparkles, type LucideIcon } from 'lucide-react'

export type TabId = 'overview' | 'projects' | 'packages' | 'vulnerabilities' | 'recommendations' | 'graph'

export type TabDefinition = { id: TabId; label: string; icon: LucideIcon }

export const TABS: TabDefinition[] = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'projects', label: 'Projects', icon: Boxes },
  { id: 'packages', label: 'Packages', icon: Package },
  { id: 'vulnerabilities', label: 'Vulnerabilities', icon: ShieldAlert },
  { id: 'recommendations', label: 'Recommendations', icon: Sparkles },
  { id: 'graph', label: 'Dependency graph', icon: GitBranch },
]

export const DEFAULT_TAB: TabId = 'overview'

export const tabLabel = (id: TabId) => TABS.find((tab) => tab.id === id)?.label ?? ''

export const isTabId = (value: string): value is TabId => TABS.some((tab) => tab.id === value)
