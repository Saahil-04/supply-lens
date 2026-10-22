import { Check, GitBranch, Package, ShieldAlert, ShieldCheck } from 'lucide-react'

export function WelcomePanel() {
  return (
    <div className="welcome-panel">
      <div className="welcome-art">
        <div className="art-orbit orbit-one" />
        <div className="art-orbit orbit-two" />
        <div className="art-core">
          <ShieldCheck size={39} />
        </div>
        <div className="art-chip chip-a">
          <Package size={15} />
        </div>
        <div className="art-chip chip-b">
          <GitBranch size={15} />
        </div>
        <div className="art-chip chip-c">
          <ShieldAlert size={15} />
        </div>
      </div>
      <div className="welcome-copy">
        <div className="eyebrow">YOUR SECURITY WORKSPACE</div>
        <h2>See the risk hiding in your dependencies.</h2>
        <p>
          Paste a repository URL above to map npm dependencies, inspect known OSV advisories, explore
          dependency relationships, and export a CycloneDX SBOM.
        </p>
        <div className="welcome-points">
          <span>
            <Check size={14} /> Dependency inventory
          </span>
          <span>
            <Check size={14} /> Vulnerability findings
          </span>
          <span>
            <Check size={14} /> SBOM export
          </span>
        </div>
      </div>
    </div>
  )
}
