import { Boxes, GitBranch, LayoutDashboard, Package, ShieldAlert, Sparkles } from 'lucide-react'

export type Tab = 'Overview' | 'Projects' | 'Packages' | 'Vulnerabilities' | 'Recommendations' | 'Dependency graph'

export const tabs: { name: Tab; icon: typeof LayoutDashboard }[] = [
  { name: 'Overview', icon: LayoutDashboard },
  { name: 'Projects', icon: Boxes },
  { name: 'Packages', icon: Package },
  { name: 'Vulnerabilities', icon: ShieldAlert },
  { name: 'Recommendations', icon: Sparkles },
  { name: 'Dependency graph', icon: GitBranch },
]
