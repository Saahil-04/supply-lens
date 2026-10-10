"""Repository-wide npm dependency inventory for SupplyLens.

This stage builds the stable repository-analysis response. Vulnerability enrichment
will be added as a separate stage; this module does not claim a clean vulnerability scan.
"""

import json
from typing import Any

from app.analysis.dependencies import resolve_dependency_path
from app.analysis.discovery import discover_dependency_files
from app.analysis.direct import get_direct_dependencies
from app.analysis.graph import DependencyGraph, build_dependency_graph
from app.analysis.projects import NpmProject, build_npm_projects
from app.github.client import GitHubClient

SUPPORTED_NPM_LOCKFILES = {"package-lock.json", "npm-shrinkwrap.json"}


def map_projects_to_graphs(
    projects: list[NpmProject],
    graphs: dict[str, DependencyGraph],
) -> dict[str, DependencyGraph]:
    """Map standalone projects and workspace members to their lockfile graph."""
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


def _project_direct_dependencies(
    project: NpmProject,
    graph: DependencyGraph | None,
) -> list[dict[str, Any]]:
    declarations = get_direct_dependencies(project.manifest_data)
    version_specs = dict(project.manifest_data.get("dependencies", {}))
    for name, spec in project.manifest_data.get("devDependencies", {}).items():
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
            "resolved": node is not None,
        })
    return result


async def analyze_repository(repository_url: str) -> dict[str, Any]:
    """Analyze all supported npm projects in a GitHub repository snapshot."""
    client = GitHubClient()
    try:
        repository = await client.get_repository(repository_url)
        owner = repository["owner"]["login"]
        repository_name = repository["name"]
        branch = repository["default_branch"]
        commit_sha = await client.get_latest_commit_sha(owner, repository_name, branch)
        tree = await client.get_repository_tree(owner, repository_name, commit_sha)
        discovered = discover_dependency_files(tree)

        if not discovered["manifests"]:
            raise ValueError("No package.json manifests were found in this repository")

        manifest_contents: dict[str, dict[str, Any]] = {}
        warnings: list[str] = []
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
                warnings.append(
                    f"{lockfile['path']} was discovered but is not supported for resolved npm graph analysis yet."
                )
                continue
            if lockfile["path"] in graphs:
                continue
            try:
                raw = await client.get_file_content(owner, repository_name, lockfile["sha"])
                lockfile_data = json.loads(raw)
                packages = lockfile_data.get("packages")
                if not isinstance(packages, dict):
                    raise ValueError("lockfile has no valid 'packages' object (npm lockfile v2/v3 required)")
                graphs[lockfile["path"]] = build_dependency_graph(packages)
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
                warnings.append(f"Could not analyze lockfile {lockfile['path']}: {exc}")

        project_graphs = map_projects_to_graphs(projects, graphs)
        package_records: dict[tuple[str, str], dict[str, Any]] = {}
        edge_records: dict[tuple[str, str, str], dict[str, str]] = {}
        project_records: list[dict[str, Any]] = []
        direct_instance_keys: set[tuple[str, str]] = set()
        analyzed_projects = 0

        for project in projects:
            graph = project_graphs.get(project.root_path)
            direct_dependencies = _project_direct_dependencies(project, graph)
            if graph is not None:
                analyzed_projects += 1
                graph_key = next((path for path, candidate in graphs.items() if candidate is graph), project.root_path)
                for dep in direct_dependencies:
                    path = dep["package_path"]
                    if path:
                        direct_instance_keys.add((graph_key, path))
                for path, node in graph.nodes.items():
                    key = (graph_key, path)
                    package_records[key] = {
                        "id": f"{graph_key}::{path}",
                        "name": node.name,
                        "version": node.version,
                        "path": path,
                        "lockfile": graph_key,
                        "is_direct": False,
                        "is_dev": node.is_dev,
                        "resolved": node.resolved,
                        "integrity": node.integrity,
                    }
                for edge in graph.edges:
                    key = (graph_key, edge.source, edge.target, edge.dependency_type.value)
                    edge_records[key] = {
                        "source": f"{graph_key}::{edge.source}",
                        "target": f"{graph_key}::{edge.target}",
                        "dependency_type": edge.dependency_type.value,
                    }
            project_records.append({
                "path": project.root_path,
                "name": project.package_name,
                "version": project.package_version,
                "manifest_path": project.manifest.get("path"),
                "lockfile_path": project.lockfile.get("path") if project.lockfile else None,
                "has_resolved_graph": graph is not None,
                "is_workspace_root": project.is_workspace_root,
                "workspace_members": project.workspace_members,
                "direct_dependencies": direct_dependencies,
            })

        for key in direct_instance_keys:
            if key in package_records:
                package_records[key]["is_direct"] = True

        packages = sorted(package_records.values(), key=lambda p: (p["name"], p["version"], p["path"]))
        edges = list(edge_records.values())
        direct_count = sum(1 for p in packages if p["is_direct"])
        transitive_count = len(packages) - direct_count
        manifest_paths = {m["path"] for m in usable_discovery["manifests"]}
        lockfile_paths = {l["path"] for l in discovered["lockfiles"]}
        for orphan in orphaned_lockfiles:
            warnings.append(f"Orphaned lockfile {orphan.path}: {orphan.reason}")

        return {
            "repository": {
                "name": repository.get("full_name", f"{owner}/{repository_name}"),
                "url": repository_url,
                "default_branch": branch,
                "commit_sha": commit_sha,
            },
            "summary": {
                "projects_discovered": len(projects),
                "projects_with_resolved_graph": analyzed_projects,
                "manifests_found": len(manifest_paths),
                "lockfiles_found": len(lockfile_paths),
                "total_packages": len(packages),
                "direct_packages": direct_count,
                "transitive_packages": transitive_count,
                "dependency_edges": len(edges),
                "vulnerabilities_found": None,
                "risk_level": None,
            },
            "projects": project_records,
            "packages": packages,
            "dependency_graph": {"nodes": packages, "edges": edges},
            "vulnerabilities": [],
            "recommendations": [],
            "analysis_metadata": {
                "status": "partial" if warnings or analyzed_projects < len(projects) else "inventory_complete",
                "vulnerability_analysis_status": "not_started",
                "supported_package_manager": "npm",
                "warnings": warnings,
            },
        }
    finally:
        await client.close()
