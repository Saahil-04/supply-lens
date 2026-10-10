"""Repository-wide npm inventory and OSV enrichment service."""
from __future__ import annotations

import json
from typing import Any

import httpx

from app.analysis.dependencies import resolve_dependency_path
from app.analysis.discovery import discover_dependency_files
from app.analysis.direct import get_direct_dependencies
from app.analysis.graph import DependencyGraph, build_dependency_graph
from app.analysis.osv import scan_packages
from app.analysis.sbom import build_cyclonedx_sbom
from app.analysis.projects import NpmProject, build_npm_projects
from app.github.client import GitHubClient

SUPPORTED_NPM_LOCKFILES = {"package-lock.json", "npm-shrinkwrap.json"}


def map_projects_to_graphs(projects: list[NpmProject], graphs: dict[str, DependencyGraph]) -> dict[str, DependencyGraph]:
    """Map standalone projects and workspace members to their shared lockfile graph."""
    project_graphs: dict[str, DependencyGraph] = {}
    for project in projects:
        if project.lockfile is not None:
            graph = graphs.get(project.lockfile["path"])
            if graph is not None:
                project_graphs[project.root_path] = graph
    for root_project in projects:
        if not root_project.is_workspace_root or root_project.lockfile is None:
            continue
        graph = graphs.get(root_project.lockfile["path"])
        if graph is None:
            continue
        for member_manifest_path in root_project.workspace_members:
            member_root = member_manifest_path.rsplit("/", maxsplit=1)[0]
            project_graphs[member_root] = graph
    return project_graphs


def _project_direct_dependencies(project: NpmProject, graph: DependencyGraph | None) -> list[dict[str, Any]]:
    declarations = get_direct_dependencies(project.manifest_data)
    version_specs: dict[str, Any] = {}
    for field in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
        values = project.manifest_data.get(field, {})
        if isinstance(values, dict):
            for name, spec in values.items():
                version_specs.setdefault(name, spec)
    package_paths = set(graph.nodes) if graph else set()
    result: list[dict[str, Any]] = []
    for name, dependency_type in declarations.items():
        dependency_path = resolve_dependency_path(project.root_path, name, package_paths) if graph else None
        node = graph.nodes.get(dependency_path) if graph and dependency_path else None
        result.append({
            "name": name,
            "declared_version": version_specs.get(name),
            "dependency_type": dependency_type,
            "resolved_version": node.version if node else None,
            "package_path": dependency_path,
            "resolved": bool(node and node.version),
        })
    return result


def _risk_level(vulnerabilities: list[dict[str, Any]], scan_complete: bool) -> str:
    # Preserve known high-severity findings even if other parts of the scan were incomplete.
    if not vulnerabilities:
        return "none_detected" if scan_complete else "not_assessed"
    severities = {v.get("severity", "UNKNOWN") for v in vulnerabilities}
    for level in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        if level in severities:
            return level.lower()
    return "unknown"


def _recommendations(vulnerabilities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for vuln in vulnerabilities:
        key = (vuln["package_id"], vuln["package_name"], vuln["installed_version"])
        rec = grouped.setdefault(key, {
            "package_id": key[0], "package_name": key[1], "installed_version": key[2],
            "vulnerability_ids": [], "fixed_versions": [],
            "recommendation": "Review the advisory and upgrade to a fixed version when one is available.",
        })
        if vuln.get("id") and vuln["id"] not in rec["vulnerability_ids"]:
            rec["vulnerability_ids"].append(vuln["id"])
        for version in vuln.get("fixed_versions", []):
            if version not in rec["fixed_versions"]:
                rec["fixed_versions"].append(version)
    result = list(grouped.values())
    for rec in result:
        rec["fixed_versions"].sort()
        if rec["fixed_versions"]:
            rec["recommendation"] = "Review compatibility and upgrade to one of the OSV-listed fixed versions."
        else:
            rec["recommendation"] = "OSV did not provide a fixed version; review the advisory and mitigation guidance."
    return sorted(result, key=lambda r: (r["package_name"], r["installed_version"]))


async def analyze_repository(repository_url: str) -> dict[str, Any]:
    """Analyze one immutable GitHub commit; return partial data with explicit coverage warnings."""
    client = GitHubClient()
    try:
        repository = await client.get_repository(repository_url)
        owner = repository["owner"].get("login")
        repository_name = repository.get("name")
        branch = repository.get("default_branch")
        if not all(isinstance(x, str) and x for x in (owner, repository_name, branch)):
            raise ValueError("GitHub returned incomplete repository metadata")
        commit_sha = await client.get_latest_commit_sha(owner, repository_name, branch)
        tree = await client.get_repository_tree(owner, repository_name, commit_sha)
        discovered = discover_dependency_files(tree)
        if not discovered["manifests"]:
            raise ValueError("No package.json manifests were found in this repository")

        warnings: list[str] = []
        manifest_contents: dict[str, dict[str, Any]] = {}
        for manifest in discovered["manifests"]:
            try:
                raw = await client.get_file_content(owner, repository_name, manifest["sha"])
                parsed = json.loads(raw)
                if not isinstance(parsed, dict):
                    raise ValueError("package.json must contain a JSON object")
                manifest_contents[manifest["path"]] = parsed
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
                warnings.append(f"Could not parse {manifest['path']}: {exc}")

        usable_discovery = {
            "manifests": [m for m in discovered["manifests"] if m["path"] in manifest_contents],
            "lockfiles": discovered["lockfiles"],
        }
        projects, orphaned_lockfiles = build_npm_projects(usable_discovery, manifest_contents)
        graphs: dict[str, DependencyGraph] = {}
        for project in projects:
            lockfile = project.lockfile
            if lockfile is None:
                continue
            lockfile_name = lockfile["path"].rsplit("/", 1)[-1]
            if lockfile_name not in SUPPORTED_NPM_LOCKFILES:
                warnings.append(f"{lockfile['path']} was discovered but {lockfile_name} is not supported for resolved npm graph analysis yet.")
                continue
            if lockfile["path"] in graphs:
                continue
            try:
                raw = await client.get_file_content(owner, repository_name, lockfile["sha"])
                lockfile_data = json.loads(raw)
                packages = lockfile_data.get("packages") if isinstance(lockfile_data, dict) else None
                if not isinstance(packages, dict):
                    raise ValueError("lockfile has no valid 'packages' object (npm lockfile v2/v3 required)")
                if lockfile_data.get("lockfileVersion") not in (2, 3):
                    warnings.append(f"{lockfile['path']} has lockfileVersion {lockfile_data.get('lockfileVersion')!r}; graph support is validated for npm lockfile v2/v3.")
                graph = build_dependency_graph(packages)
                graphs[lockfile["path"]] = graph
                if graph.unresolved:
                    warnings.append(f"{lockfile['path']}: {len(graph.unresolved)} dependency or package entries could not be resolved in the lockfile graph.")
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
                warnings.append(f"Could not analyze lockfile {lockfile['path']}: {exc}")

        project_graphs = map_projects_to_graphs(projects, graphs)
        package_records: dict[tuple[str, str], dict[str, Any]] = {}
        edge_records: dict[tuple[str, str, str, str], dict[str, str]] = {}
        project_records: list[dict[str, Any]] = []
        direct_instance_keys: set[tuple[str, str]] = set()
        direct_projects_by_instance: dict[tuple[str, str], set[str]] = {}
        analyzed_projects = 0

        for project in projects:
            graph = project_graphs.get(project.root_path)
            direct_dependencies = _project_direct_dependencies(project, graph)
            if graph is not None:
                analyzed_projects += 1
                graph_key = next((path for path, candidate in graphs.items() if candidate is graph), project.root_path)
                for dep in direct_dependencies:
                    if dep["package_path"]:
                        instance_key = (graph_key, dep["package_path"])
                        direct_instance_keys.add(instance_key)
                        direct_projects_by_instance.setdefault(instance_key, set()).add(project.root_path or ".")
                for path, node in graph.nodes.items():
                    key = (graph_key, path)
                    package_records[key] = {
                        "id": f"{graph_key}::{path}", "name": node.name, "version": node.version,
                        "path": path, "lockfile": graph_key, "is_direct": False, "direct_projects": [],
                        # This reflects npm's lockfile flag; direct declaration scope is per-project below.
                        "is_dev": node.dev, "is_optional": node.optional, "is_dev_optional": node.dev_optional,
                        "is_link": node.is_link, "resolved": node.resolved, "integrity": node.integrity,
                    }
                for edge in graph.edges:
                    edge_records[(graph_key, edge.source, edge.target, edge.dependency_type.value)] = {
                        "source": f"{graph_key}::{edge.source}", "target": f"{graph_key}::{edge.target}",
                        "dependency_type": edge.dependency_type.value,
                    }
            project_records.append({
                "path": project.root_path, "name": project.package_name, "version": project.package_version,
                "manifest_path": project.manifest.get("path"),
                "lockfile_path": project.lockfile.get("path") if project.lockfile else None,
                "has_resolved_graph": graph is not None,
                "graph_lockfile_path": next((path for path, candidate in graphs.items() if candidate is graph), None) if graph is not None else None,
                "is_workspace_root": project.is_workspace_root,
                "workspace_members": project.workspace_members, "direct_dependencies": direct_dependencies,
            })

        for key in direct_instance_keys:
            if key in package_records:
                package_records[key]["is_direct"] = True
                package_records[key]["direct_projects"] = sorted(direct_projects_by_instance.get(key, set()))
        packages = sorted(package_records.values(), key=lambda p: (p["name"], p["version"] or "", p["path"]))
        edges = sorted(edge_records.values(), key=lambda e: (e["source"], e["target"], e["dependency_type"]))
        direct_count = sum(1 for package in packages if package["is_direct"])
        transitive_count = len(packages) - direct_count
        for orphan in orphaned_lockfiles:
            warnings.append(f"Orphaned lockfile {orphan.path}: {orphan.reason}")

        inventory_partial = bool(warnings) or analyzed_projects < len(projects) or len(manifest_contents) < len(discovered["manifests"])
        unresolved_declarations = any(not dep["resolved"] for project in project_records for dep in project["direct_dependencies"])
        unresolved_graph_entries = any(bool(graph.unresolved) for graph in graphs.values())
        unsupported_or_missing_graph = any(
            (project.lockfile is not None and project_graphs.get(project.root_path) is None)
            or (project.lockfile is None and bool(_project_direct_dependencies(project, None)))
            for project in projects
        )
        malformed_manifest = len(manifest_contents) < len(discovered["manifests"])
        coverage_incomplete = unresolved_declarations or unresolved_graph_entries or unsupported_or_missing_graph or malformed_manifest or bool(orphaned_lockfiles)
        vulnerability_status = "not_started"
        vulnerabilities: list[dict[str, Any]] = []
        scan_complete = False
        scan_succeeded = False
        if not packages and coverage_incomplete:
            vulnerability_status = "partial"
            warnings.append("Vulnerability analysis could not cover all dependency declarations because resolved package versions or a supported dependency graph were unavailable.")
        else:
            try:
                vulnerabilities = await scan_packages(packages)
                scan_succeeded = True
                vulnerability_status = "partial" if coverage_incomplete else "complete"
                scan_complete = not coverage_incomplete
            except (httpx.HTTPError, ValueError) as exc:
                vulnerability_status = "failed"
                warnings.append(f"OSV vulnerability lookup failed; inventory is available but vulnerability coverage is incomplete: {exc}")

        recommendations = _recommendations(vulnerabilities)
        risk_level = _risk_level(vulnerabilities, scan_complete)
        manifest_paths = {m["path"] for m in discovered["manifests"]}
        lockfile_paths = {l["path"] for l in discovered["lockfiles"]}
        return {
            "repository": {
                "name": repository.get("full_name", f"{owner}/{repository_name}"), "url": repository_url,
                "default_branch": branch, "commit_sha": commit_sha,
            },
            "summary": {
                "projects_discovered": len(projects), "projects_with_resolved_graph": analyzed_projects,
                "manifests_found": len(manifest_paths), "lockfiles_found": len(lockfile_paths),
                "total_packages": len(packages), "direct_packages": direct_count,
                "transitive_packages": transitive_count, "dependency_edges": len(edges),
                "vulnerabilities_found": len(vulnerabilities) if scan_succeeded else None,
                "risk_level": risk_level,
            },
            "projects": project_records, "packages": packages,
            "dependency_graph": {"nodes": packages, "edges": edges},
            "sbom": build_cyclonedx_sbom(
                {"name": repository.get("full_name", f"{owner}/{repository_name}"), "commit_sha": commit_sha},
                project_records, packages, edges,
            ),
            "vulnerabilities": vulnerabilities, "recommendations": recommendations,
            "analysis_metadata": {
                "status": "partial" if inventory_partial else "inventory_complete",
                "vulnerability_analysis_status": vulnerability_status,
                "supported_package_manager": "npm",
                "snapshot": "default-branch commit SHA; results are tied to the returned commit_sha",
                "warnings": warnings,
            },
        }
    finally:
        await client.close()
