"""Repository-wide npm/pnpm inventory and OSV enrichment service."""
from __future__ import annotations

import asyncio
import json
import logging
import posixpath
import time
from collections import deque
from typing import Any

import httpx

from app.analysis import semver
from app.analysis.dependencies import SOURCE_WORKSPACE, resolve_dependency_path
from app.analysis.direct import get_direct_dependencies
from app.analysis.discovery import discover_dependency_files
from app.analysis.graph import DependencyGraph
from app.analysis.lockfiles import (
    MAX_LOCKFILE_BYTES, SUPPORTED_LOCKFILES, LockfileLoad, load_lockfile, unsupported_lockfile_diagnostic,
)
from app.analysis.osv import ScanReport, scan_packages
from app.analysis.projects import NpmProject, build_npm_projects
from app.analysis.reachability import DEFAULT_MAX_FILES, apply_priority_without_reachability, run_reachability
from app.analysis.sbom import build_cyclonedx_sbom
from app.errors import AnalysisError, Diagnostic
from app.github.client import GitHubClient

logger = logging.getLogger(__name__)

SUPPORTED_NPM_LOCKFILES = {"package-lock.json", "npm-shrinkwrap.json"}
SUPPORTED_PNPM_LOCKFILES = {"pnpm-lock.yaml"}
FETCH_CONCURRENCY = 10
EXAMPLE_LIMIT = 25                  # cap on per-diagnostic detail lists so payloads stay small
# Errors that make every remaining GitHub call pointless: fail the analysis, don't return junk.
FATAL_FETCH_CODES = frozenset({"GITHUB_RATE_LIMITED", "GITHUB_AUTH_FAILED", "GITHUB_FORBIDDEN"})
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


def map_projects_to_graphs(projects: list[NpmProject], graphs: dict[str, DependencyGraph]) -> dict[str, DependencyGraph]:
    """Map projects to lockfile graphs, including pnpm workspace importers.

    pnpm workspaces are declared in pnpm-workspace.yaml rather than necessarily
    in package.json. Therefore importer paths in the lockfile are the source of
    truth for associating workspace manifests with the shared pnpm graph.
    """
    project_graphs: dict[str, DependencyGraph] = {}

    # Preserve the existing npm mapping behavior.
    for project in projects:
        if project.lockfile is None:
            continue
        graph = graphs.get(project.lockfile["path"])
        if graph is None or graph.importer_dependencies:
            continue
        project_graphs[project.root_path] = graph

    # Map each pnpm importer to the package.json in the same repository-relative
    # directory. Do not infer workspace membership from directory proximity.
    for lockfile_path, graph in graphs.items():
        if not graph.importer_dependencies:
            continue
        lockfile_root = posixpath.dirname(lockfile_path) or "."
        for project in projects:
            project_root = project.root_path or "."
            importer_path = posixpath.relpath(project_root, lockfile_root)
            if importer_path == "":
                importer_path = "."
            if importer_path in graph.importer_dependencies:
                project_graphs[project.root_path] = graph

    # Existing npm workspaces may share a root graph even when their own
    # project records do not carry a lockfile.
    for root_project in projects:
        if not root_project.is_workspace_root or root_project.lockfile is None:
            continue
        graph = graphs.get(root_project.lockfile["path"])
        if graph is None or graph.importer_dependencies:
            continue
        for member_manifest_path in root_project.workspace_members:
            member_root = member_manifest_path.rsplit("/", maxsplit=1)[0]
            project_graphs[member_root] = graph
    return project_graphs


def _project_direct_dependencies(
    project: NpmProject,
    graph: DependencyGraph | None,
    graph_key: str | None = None,
    workspace_versions: dict[str, str | None] | None = None,
) -> list[dict[str, Any]]:
    declarations = get_direct_dependencies(project.manifest_data)
    version_specs: dict[str, Any] = {}
    for field in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
        values = project.manifest_data.get(field, {})
        if isinstance(values, dict):
            for name, spec in values.items():
                version_specs.setdefault(name, spec)
    importer_path = project.root_path or "."
    if graph and graph.importer_dependencies and graph_key:
        importer_root = posixpath.dirname(graph_key) or "."
        importer_path = posixpath.relpath(importer_path, importer_root) or "."
    is_pnpm = bool(graph and graph.importer_dependencies)
    pnpm_direct = graph.importer_dependencies.get(importer_path, {}) if graph else {}
    pnpm_links = graph.workspace_links.get(importer_path, {}) if graph else {}
    result: list[dict[str, Any]] = []
    for name, dependency_type in declarations.items():
        dependency_path: str | None = None
        kind = "missing"
        link_target: str | None = None
        if graph:
            dependency_path = pnpm_direct.get(name)
            if dependency_path is None and not is_pnpm:
                # graph.nodes is a dict: membership tests are O(1), no per-project set copy.
                dependency_path = resolve_dependency_path(project.root_path, name, graph.nodes)  # type: ignore[arg-type]
            if dependency_path is None and name in pnpm_links:
                link_target = pnpm_links[name]
        node = graph.nodes.get(dependency_path) if graph and dependency_path else None
        resolved_version = node.version if node else None
        if node is not None:
            kind = "workspace" if node.source == SOURCE_WORKSPACE else "package"
        elif link_target is not None:
            # pnpm `workspace:*` / `link:` dependency: resolved to a sibling project, not a package.
            kind = "workspace"
            target = posixpath.normpath(posixpath.join(posixpath.dirname(graph_key or ""), link_target))
            resolved_version = (workspace_versions or {}).get("" if target == "." else target)
        resolved = bool(node and node.version) or link_target is not None
        result.append({
            "name": name,
            "declared_version": version_specs.get(name),
            "dependency_type": dependency_type,
            "resolved_version": resolved_version,
            "package_path": dependency_path,
            "resolved": resolved,
            "kind": kind if resolved else "missing",
            # Optional and peer declarations are allowed to be absent from an install.
            "required": dependency_type in ("production", "development"),
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
            "_lowest_fixes": [], "unfixed_vulnerability_ids": [],
            "is_direct": vuln.get("is_direct"), "introduced_via": vuln.get("introduced_via", []),
            "direct_projects": vuln.get("direct_projects", []),
            "priority": None,
        })
        if vuln.get("priority") is not None:
            rec["priority"] = vuln["priority"] if rec["priority"] is None else min(rec["priority"], vuln["priority"])
        if vuln.get("id") and vuln["id"] not in rec["vulnerability_ids"]:
            rec["vulnerability_ids"].append(vuln["id"])
        fixes = vuln.get("fixed_versions", [])
        for version in fixes:
            if version not in rec["fixed_versions"]:
                rec["fixed_versions"].append(version)
        if fixes:
            rec["_lowest_fixes"].append(semver.sorted_versions(list(fixes))[0])
        elif vuln.get("id") and vuln["id"] not in rec["unfixed_vulnerability_ids"]:
            rec["unfixed_vulnerability_ids"].append(vuln["id"])
    result = list(grouped.values())
    for rec in result:
        rec["fixed_versions"] = semver.sorted_versions(rec["fixed_versions"])
        lowest = rec.pop("_lowest_fixes")
        # The smallest version that fixes *every* advisory on this package, when all of them have a fix.
        rec["minimum_safe_version"] = semver.sorted_versions(lowest)[-1] if lowest and not rec["unfixed_vulnerability_ids"] else None
        if rec["minimum_safe_version"]:
            rec["recommendation"] = f"Upgrade to {rec['minimum_safe_version']} or later (the lowest version that fixes all listed advisories); review compatibility first."
        elif rec["fixed_versions"]:
            rec["recommendation"] = "Review compatibility and upgrade to one of the OSV-listed fixed versions; some advisories have no fix yet."
        else:
            rec["recommendation"] = "OSV did not provide a fixed version; review the advisory and mitigation guidance."
        if rec["is_direct"] is False and rec["introduced_via"]:
            rec["recommendation"] += f" This package is transitive (via {rec['introduced_via'][0]}); upgrade that dependency or add an override/resolution."
    return sorted(result, key=lambda r: (r["package_name"], r["installed_version"]))


def _package_record(graph_key: str, path: str, node: Any) -> dict[str, Any]:
    return {
        "id": f"{graph_key}::{path}", "name": node.name, "version": node.version,
        "path": path, "lockfile": graph_key, "is_direct": False, "direct_projects": [],
        # This reflects npm's lockfile flag; direct declaration scope is per-project below.
        "is_dev": node.dev, "is_optional": node.optional, "is_dev_optional": node.dev_optional,
        "is_link": node.is_link, "resolved": node.resolved, "integrity": node.integrity,
        "source": node.source,
    }


def _introduced_via(graph: DependencyGraph, target: str, direct_paths: set[str]) -> list[str]:
    """Shortest chain 'direct dependency -> ... -> vulnerable package' using reverse edges."""
    if target in direct_paths:
        return [f"{graph.nodes[target].name}@{graph.nodes[target].version}"]
    parents: dict[str, str | None] = {target: None}
    queue = deque([target])
    budget = 50000
    while queue and budget:
        budget -= 1
        current = queue.popleft()
        for parent in sorted(graph.reverse_edges.get(current, ())):
            if parent in parents:
                continue
            parents[parent] = current
            if parent in direct_paths:
                chain, cursor = [], parent
                while cursor is not None:
                    node = graph.nodes[cursor]
                    chain.append(f"{node.name}@{node.version}")
                    cursor = parents[cursor]
                return chain
            queue.append(parent)
    return []


def _fatal_fetch_error(results: dict[str, Any]) -> AnalysisError | None:
    for value in results.values():
        if isinstance(value, AnalysisError) and value.code in FATAL_FETCH_CODES:
            return value
    return None


async def _fetch_many(client: Any, owner: str, name: str, items: list[dict[str, Any]]) -> dict[str, str | Exception]:
    """Download several blobs concurrently; each result is the text or the exception it raised."""
    gate = asyncio.Semaphore(FETCH_CONCURRENCY)

    async def one(item: dict[str, Any]) -> tuple[str, str | Exception]:
        async with gate:
            try:
                return item["path"], await client.get_file_content(owner, name, item["sha"])
            except Exception as exc:                          # noqa: BLE001 - classified by the caller
                return item["path"], exc

    return dict(await asyncio.gather(*(one(item) for item in items)))


def _describe(exc: Exception) -> str:
    return exc.message if isinstance(exc, AnalysisError) else str(exc) or type(exc).__name__


async def analyze_repository(repository_url: str, include_reachability: bool = True) -> dict[str, Any]:
    """Analyze one immutable GitHub commit; return partial data with explicit coverage warnings."""
    started = time.perf_counter()
    timings: dict[str, int] = {}
    diagnostics: list[Diagnostic] = []
    client = GitHubClient()
    try:
        repository = await client.get_repository(repository_url)
        owner = repository["owner"].get("login")
        repository_name = repository.get("name")
        branch = repository.get("default_branch")
        if not all(isinstance(x, str) and x for x in (owner, repository_name, branch)):
            raise AnalysisError("GITHUB_BAD_RESPONSE", "GitHub returned incomplete repository metadata", status_code=502, retryable=True)
        commit_sha = await client.get_latest_commit_sha(owner, repository_name, branch)
        tree = await client.get_repository_tree(owner, repository_name, commit_sha)
        diagnostics.extend(getattr(client, "diagnostics", []))
        discovered = discover_dependency_files(tree)
        if not discovered["manifests"]:
            raise AnalysisError(
                "NO_MANIFESTS", "No package.json manifests were found in this repository", status_code=422,
                hint="SupplyLens analyzes JavaScript/TypeScript projects that have a package.json.",
            )

        # ---- manifests (concurrent)
        fetched = await _fetch_many(client, owner, repository_name, discovered["manifests"])
        if (fatal := _fatal_fetch_error(fetched)) is not None:
            raise fatal
        manifest_contents: dict[str, dict[str, Any]] = {}
        for manifest in discovered["manifests"]:
            value = fetched[manifest["path"]]
            try:
                if isinstance(value, Exception):
                    raise value
                parsed = json.loads(value)
                if not isinstance(parsed, dict):
                    raise ValueError("package.json must contain a JSON object")
                manifest_contents[manifest["path"]] = parsed
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError, AnalysisError, httpx.HTTPError) as exc:
                code = "MANIFEST_PARSE_ERROR" if isinstance(exc, (json.JSONDecodeError, UnicodeDecodeError)) or "JSON object" in str(exc) else "MANIFEST_FETCH_FAILED"
                diagnostics.append(Diagnostic(
                    code, "error", f"Could not parse {manifest['path']}: {_describe(exc)}", path=manifest["path"],
                    hint="Fix the JSON syntax (merge-conflict markers and trailing commas are common causes)." if code == "MANIFEST_PARSE_ERROR" else None,
                ))

        usable_discovery = {
            "manifests": [m for m in discovered["manifests"] if m["path"] in manifest_contents],
            "lockfiles": discovered["lockfiles"],
        }
        projects, orphaned_lockfiles = build_npm_projects(usable_discovery, manifest_contents)

        # ---- decide which lockfiles to load: those chosen for a project + orphans
        lockfile_roles: dict[str, str] = {}
        by_path = {item["path"]: item for item in discovered["lockfiles"]}
        for project in projects:
            if project.lockfile is not None:
                lockfile_roles.setdefault(project.lockfile["path"], "project")
        for orphan in orphaned_lockfiles:
            lockfile_roles.setdefault(orphan.path, "orphan")
        used_by_directory = {posixpath.dirname(path) for path in lockfile_roles}
        for item in discovered["lockfiles"]:
            directory = posixpath.dirname(item["path"])
            if item["path"] not in lockfile_roles and directory in used_by_directory:
                chosen = next(p for p in lockfile_roles if posixpath.dirname(p) == directory)
                diagnostics.append(Diagnostic(
                    "MULTIPLE_LOCKFILES", "info",
                    f"{item['path']} was ignored because {chosen} is used for the same directory "
                    "(a package.json 'packageManager' field or npm > pnpm > yarn precedence decides).",
                    path=item["path"],
                ))

        to_fetch: list[dict[str, Any]] = []
        loads: dict[str, LockfileLoad] = {}
        for path, role in lockfile_roles.items():
            item = by_path[path]
            name = path.rsplit("/", 1)[-1]
            if name not in SUPPORTED_LOCKFILES:
                diagnostics.append(unsupported_lockfile_diagnostic(path))
                loads[path] = LockfileLoad(path=path, format="yarn" if name == "yarn.lock" else "unknown")
            elif isinstance(item.get("size"), int) and item["size"] > MAX_LOCKFILE_BYTES:
                diagnostics.append(Diagnostic(
                    "LOCKFILE_TOO_LARGE", "error",
                    f"{path} is larger than {MAX_LOCKFILE_BYTES // (1024 * 1024)} MB and was skipped.", path=path,
                ))
                loads[path] = LockfileLoad(path=path, format="npm" if name != "pnpm-lock.yaml" else "pnpm")
            else:
                to_fetch.append(item)
        lock_contents = await _fetch_many(client, owner, repository_name, to_fetch)
        if (fatal := _fatal_fetch_error(lock_contents)) is not None:
            raise fatal
        timings["github_fetch"] = int((time.perf_counter() - started) * 1000)

        # ---- parse lockfiles (worker threads, concurrently)
        parse_started = time.perf_counter()
        parse_jobs: list[tuple[str, Any]] = []
        for item in to_fetch:
            value = lock_contents[item["path"]]
            if isinstance(value, Exception):
                diagnostics.append(Diagnostic(
                    "LOCKFILE_FETCH_FAILED", "error", f"Could not download lockfile {item['path']}: {_describe(value)}",
                    path=item["path"], hint="Retry the analysis." if getattr(value, "retryable", True) else None,
                ))
                loads[item["path"]] = LockfileLoad(path=item["path"], format="npm" if not item["path"].endswith("pnpm-lock.yaml") else "pnpm")
            else:
                parse_jobs.append((item["path"], value))
        for load in await asyncio.gather(*(load_lockfile(path, raw) for path, raw in parse_jobs)):
            loads[load.path] = load
        timings["lockfile_parse"] = int((time.perf_counter() - parse_started) * 1000)

        graphs: dict[str, DependencyGraph] = {}
        lockfile_reports: list[dict[str, Any]] = []
        orphan_graph_paths: set[str] = set()
        for path in sorted(loads):
            load = loads[path]
            diagnostics.extend(load.diagnostics)
            graph = load.graph
            if graph is not None:
                graphs[path] = graph
                if lockfile_roles.get(path) == "orphan":
                    orphan_graph_paths.add(path)
                if graph.unresolved:
                    diagnostics.append(Diagnostic(
                        "LOCKFILE_UNRESOLVED_DEPENDENCIES", "warning",
                        f"{path}: {len(graph.unresolved)} dependency or package entries could not be resolved in the lockfile graph.",
                        path=path, details={"count": len(graph.unresolved), "examples": graph.unresolved[:EXAMPLE_LIMIT]},
                        hint="The lockfile may be corrupt or out of date; regenerate it with your package manager.",
                    ))
            lockfile_reports.append({
                "path": path, "format": load.format, "lockfile_version": load.lockfile_version,
                "role": lockfile_roles.get(path, "project"),
                "status": "ok" if graph is not None else ("unsupported" if load.format in ("yarn", "unknown") else "failed"),
                "packages": len(graph.nodes) if graph else 0, "edges": len(graph.edges) if graph else 0,
                "unresolved": len(graph.unresolved) if graph else 0,
                "error_codes": sorted({d.code for d in load.diagnostics if d.severity == "error"}),
            })

        project_graphs = map_projects_to_graphs(projects, graphs)
        graph_key_by_id = {id(graph): path for path, graph in graphs.items()}
        workspace_versions = {p.root_path: p.package_version for p in projects}
        package_records: dict[tuple[str, str], dict[str, Any]] = {}
        edge_records: dict[tuple[str, str, str, str], dict[str, str]] = {}
        project_records: list[dict[str, Any]] = []
        direct_instance_keys: set[tuple[str, str]] = set()
        direct_projects_by_instance: dict[tuple[str, str], set[str]] = {}
        analyzed_projects = 0
        unsupported_or_missing_graph = False
        graphs_in_inventory: set[str] = set()
        no_lockfile: list[tuple[str, int]] = []

        def add_graph(graph_key: str, graph: DependencyGraph) -> None:
            if graph_key in graphs_in_inventory:
                return
            graphs_in_inventory.add(graph_key)
            for path, node in graph.nodes.items():
                package_records.setdefault((graph_key, path), _package_record(graph_key, path, node))
            for edge in graph.edges:
                edge_records[(graph_key, edge.source, edge.target, edge.dependency_type.value)] = {
                    "source": f"{graph_key}::{edge.source}", "target": f"{graph_key}::{edge.target}",
                    "dependency_type": edge.dependency_type.value,
                }

        for project in projects:
            graph = project_graphs.get(project.root_path)
            graph_key = graph_key_by_id.get(id(graph)) if graph is not None else None
            direct_dependencies = _project_direct_dependencies(project, graph, graph_key, workspace_versions)
            manifest_path = project.manifest.get("path")
            if graph is not None:
                analyzed_projects += 1
                add_graph(graph_key or project.root_path, graph)
                for dep in direct_dependencies:
                    if dep["package_path"]:
                        instance_key = (graph_key or project.root_path, dep["package_path"])
                        direct_instance_keys.add(instance_key)
                        direct_projects_by_instance.setdefault(instance_key, set()).add(project.root_path or ".")
                missing = [d["name"] for d in direct_dependencies if d["required"] and not d["resolved"]]
                if missing:
                    diagnostics.append(Diagnostic(
                        "DIRECT_DEPENDENCIES_UNRESOLVED", "warning",
                        f"{len(missing)} dependency(ies) declared in {manifest_path} are not in the lockfile "
                        f"({', '.join(missing[:5])}{', ...' if len(missing) > 5 else ''}); the lockfile may be out of date.",
                        path=manifest_path, details={"count": len(missing), "names": missing[:EXAMPLE_LIMIT]},
                        hint="Run your package manager's install command and commit the updated lockfile.",
                    ))
            elif direct_dependencies:
                unsupported_or_missing_graph = True
                if project.lockfile is None:
                    no_lockfile.append((manifest_path, len(direct_dependencies)))
                else:
                    diagnostics.append(Diagnostic(
                        "PROJECT_GRAPH_UNAVAILABLE", "warning",
                        f"{manifest_path}: its lockfile {project.lockfile['path']} could not be turned into a dependency graph (see the lockfile diagnostics).",
                        path=manifest_path,
                    ))
            is_workspace_root, workspace_members = project.is_workspace_root, project.workspace_members
            if graph is not None and graph_key and graph.importer_dependencies and (posixpath.dirname(graph_key) == project.root_path):
                others = sorted(i for i in graph.importer_dependencies if i != ".")
                if others:
                    is_workspace_root = True
                    workspace_members = [posixpath.join(project.root_path, i, "package.json") for i in others]
            project_records.append({
                "path": project.root_path, "name": project.package_name, "version": project.package_version,
                "manifest_path": manifest_path,
                "lockfile_path": project.lockfile.get("path") if project.lockfile else None,
                "has_resolved_graph": graph is not None,
                "graph_lockfile_path": graph_key if graph is not None else None,
                "is_workspace_root": is_workspace_root,
                "workspace_members": workspace_members, "direct_dependencies": direct_dependencies,
            })

        if no_lockfile:
            # One aggregated diagnostic: large repos (e.g. examples/ folders) can have hundreds of
            # lockfile-less projects, and one warning per project buries everything else.
            top_levels: dict[str, int] = {}
            for path, _ in no_lockfile:
                top = path.split("/", 1)[0] if "/" in path else "(repository root)"
                top_levels[top] = top_levels.get(top, 0) + 1
            total_deps = sum(count for _, count in no_lockfile)
            names = ", ".join(path for path, _ in no_lockfile[:3])
            diagnostics.append(Diagnostic(
                "PROJECT_WITHOUT_LOCKFILE", "warning",
                f"{len(no_lockfile)} project(s) declare {total_deps} dependencies but have no lockfile, so exact installed versions "
                f"(and therefore vulnerabilities) cannot be determined for them (e.g. {names}{', ...' if len(no_lockfile) > 3 else ''}).",
                details={
                    "count": len(no_lockfile), "dependencies_declared": total_deps,
                    "by_top_level_directory": dict(sorted(top_levels.items(), key=lambda kv: -kv[1])[:EXAMPLE_LIMIT]),
                    "examples": [{"path": path, "dependencies": count} for path, count in no_lockfile[:EXAMPLE_LIMIT]],
                },
                hint="Commit package-lock.json (`npm install --package-lock-only`) or pnpm-lock.yaml (`pnpm install --lockfile-only`) for these projects, or add them to the workspace so the root lockfile covers them.",
            ))

        # Orphaned lockfiles are inventoried and scanned under their own identity, but never
        # marked direct: there is no manifest from which to establish declarations.
        for graph_key in sorted(orphan_graph_paths):
            add_graph(graph_key, graphs[graph_key])

        for key in direct_instance_keys:
            if key in package_records:
                package_records[key]["is_direct"] = True
                package_records[key]["direct_projects"] = sorted(direct_projects_by_instance.get(key, set()))
        packages = sorted(package_records.values(), key=lambda p: (p["name"], p["version"] or "", p["path"]))
        edges = sorted(edge_records.values(), key=lambda e: (e["source"], e["target"], e["dependency_type"]))
        direct_count = sum(1 for package in packages if package["is_direct"])
        transitive_count = len(packages) - direct_count
        for orphan in orphaned_lockfiles:
            diagnostics.append(Diagnostic(
                "ORPHAN_LOCKFILE", "warning", f"Orphaned lockfile {orphan.path}: {orphan.reason}", path=orphan.path,
                hint="Add the package.json that belongs to this lockfile, or delete the stale lockfile.",
            ))

        non_registry = [p for p in packages if p["source"] not in ("registry", SOURCE_WORKSPACE)]
        if non_registry:
            kinds = sorted({p["source"] for p in non_registry})
            diagnostics.append(Diagnostic(
                "PACKAGES_NOT_SCANNABLE", "warning",
                f"{len(non_registry)} package(s) come from {'/'.join(kinds)} sources rather than the npm registry and cannot be matched "
                "against OSV by name and version; they are listed in the inventory but not assessed.",
                details={"count": len(non_registry), "examples": [f"{p['name']}@{p['version']}" for p in non_registry[:EXAMPLE_LIMIT]]},
            ))

        # Informational repository warnings (such as a successfully inventoried
        # orphan lockfile) do not by themselves mean inventory failed.
        orphan_inventory_incomplete = any(orphan.path not in orphan_graph_paths for orphan in orphaned_lockfiles)
        unresolved_graph_entries = any(bool(graph.unresolved) for graph in graphs.values())
        malformed_manifest = len(manifest_contents) < len(discovered["manifests"])
        inventory_partial = (
            analyzed_projects < len(projects) or malformed_manifest or orphan_inventory_incomplete or unresolved_graph_entries
        )
        unresolved_declarations = any(
            dep["required"] and not dep["resolved"] for project in project_records for dep in project["direct_dependencies"]
        )
        failed_required_lockfiles = any(
            report["status"] != "ok" and report["role"] == "project" for report in lockfile_reports
        )
        coverage_incomplete = (
            unresolved_declarations or unresolved_graph_entries or unsupported_or_missing_graph or failed_required_lockfiles
            or malformed_manifest or orphan_inventory_incomplete or bool(non_registry)
        )

        # ---- vulnerability scan
        osv_started = time.perf_counter()
        vulnerability_status = "not_started"
        vulnerabilities: list[dict[str, Any]] = []
        scan_complete = False
        scan_succeeded = False
        report = ScanReport()
        if not packages and coverage_incomplete:
            vulnerability_status = "partial"
            diagnostics.append(Diagnostic(
                "VULNERABILITY_SCAN_SKIPPED", "warning",
                "Vulnerability analysis could not cover all dependency declarations because resolved package versions or a supported dependency graph were unavailable.",
                hint="Commit a package-lock.json or pnpm-lock.yaml so exact versions can be resolved.",
            ))
        else:
            try:
                vulnerabilities = await scan_packages(packages, report=report)
                scan_succeeded = True
                vulnerability_status = "partial" if (coverage_incomplete or not report.complete) else "complete"
                scan_complete = vulnerability_status == "complete"
                diagnostics.extend(report.diagnostics)
            except Exception as exc:                          # noqa: BLE001 - reported, never hidden
                if not isinstance(exc, (httpx.HTTPError, ValueError)):
                    logger.exception("Unexpected OSV scan failure")
                vulnerability_status = "failed"
                diagnostics.extend(report.diagnostics)
                diagnostics.append(Diagnostic(
                    "OSV_UNAVAILABLE", "error",
                    f"OSV vulnerability lookup failed; inventory is available but vulnerability coverage is incomplete: {_describe(exc)}",
                    hint="Retry the analysis; the dependency inventory below is still valid.",
                ))
        timings["osv"] = int((time.perf_counter() - osv_started) * 1000)

        # ---- enrich findings: how does each vulnerable package get into the project?
        direct_paths_by_graph: dict[str, set[str]] = {}
        for graph_key, path in direct_instance_keys:
            direct_paths_by_graph.setdefault(graph_key, set()).add(path)
        for vuln in vulnerabilities:
            graph_key, path = vuln.get("lockfile"), vuln.get("package_path")
            record = package_records.get((graph_key, path)) if graph_key and path else None
            if record is None:
                continue
            vuln["is_direct"] = record["is_direct"]
            vuln["direct_projects"] = record["direct_projects"]
            vuln["is_dev"] = record["is_dev"]
            graph = graphs.get(graph_key)
            vuln["introduced_via"] = _introduced_via(graph, path, direct_paths_by_graph.get(graph_key, set())) if graph and path in graph.nodes else []

        # ---- reachability + context-aware priority (package-level; see reachability.py)
        reachability_meta: dict[str, Any] = {"enabled": False}
        if vulnerabilities and include_reachability:
            try:
                reachability_meta, reach_diagnostics = await run_reachability(
                    client, owner, repository_name, tree, project_records,
                    {root: graph_key_by_id[id(g)] for root, g in project_graphs.items() if id(g) in graph_key_by_id},
                    graphs, {p.root_path: p.manifest_data for p in projects}, vulnerabilities, DEFAULT_MAX_FILES,
                )
                diagnostics.extend(reach_diagnostics)
            except Exception as exc:                          # noqa: BLE001 - never fail the whole analysis
                logger.exception("Reachability analysis failed")
                apply_priority_without_reachability(vulnerabilities, "reachability analysis failed")
                diagnostics.append(Diagnostic(
                    "REACHABILITY_FAILED", "warning",
                    f"Reachability analysis failed ({_describe(exc)}); findings are ranked by severity only.",
                ))
        else:
            apply_priority_without_reachability(vulnerabilities, None if include_reachability else "reachability disabled for this analysis")
        timings["reachability"] = int((time.perf_counter() - osv_started) * 1000) - timings.get("osv", 0)
        reachability_counts: dict[str, int] = {}
        priority_counts = {f"P{n}": 0 for n in (1, 2, 3, 4)}
        baseline_counts = {f"P{n}": 0 for n in (1, 2, 3, 4)}
        for vuln in vulnerabilities:
            status = vuln["reachability"]["status"]
            reachability_counts[status] = reachability_counts.get(status, 0) + 1
            priority_counts[f"P{vuln['priority']}"] += 1
            baseline_counts[f"P{vuln['baseline_priority']}"] += 1

        recommendations = _recommendations(vulnerabilities)
        risk_level = _risk_level(vulnerabilities, scan_complete)
        manifest_paths = {m["path"] for m in discovered["manifests"]}
        lockfile_paths = {l["path"] for l in discovered["lockfiles"]}
        diagnostics.sort(key=lambda d: SEVERITY_ORDER.get(d.severity, 3))
        warnings = [d.message for d in diagnostics if d.severity != "info"]
        counts = {severity: sum(1 for d in diagnostics if d.severity == severity) for severity in ("error", "warning", "info")}
        timings["total"] = int((time.perf_counter() - started) * 1000)
        repo_name = repository.get("full_name", f"{owner}/{repository_name}")
        direct_declared = [dep for project in project_records for dep in project["direct_dependencies"]]
        return {
            "repository": {
                "name": repo_name, "url": repository_url,
                "default_branch": branch, "commit_sha": commit_sha,
            },
            "summary": {
                "projects_discovered": len(projects), "projects_with_resolved_graph": analyzed_projects,
                "manifests_found": len(manifest_paths), "lockfiles_found": len(lockfile_paths),
                "total_packages": len(packages), "direct_packages": direct_count,
                "transitive_packages": transitive_count, "dependency_edges": len(edges),
                # This count is finding instances (advisory x affected package instance),
                # not the number of distinct advisory IDs.
                "vulnerabilities_found": len(vulnerabilities) if scan_succeeded else None,
                "unique_advisories_found": len({v.get("id") for v in vulnerabilities if v.get("id")}) if scan_succeeded else None,
                "risk_level": risk_level,
                "reachability": reachability_counts,
                "priority_counts": priority_counts,
                # What a severity-only ranking would have put at each level, for comparison.
                "baseline_priority_counts": baseline_counts,
            },
            "projects": project_records, "packages": packages,
            "dependency_graph": {"nodes": packages, "edges": edges},
            "sbom": build_cyclonedx_sbom(
                {"name": repo_name, "commit_sha": commit_sha},
                project_records, packages, edges,
            ),
            "vulnerabilities": vulnerabilities, "recommendations": recommendations,
            "analysis_metadata": {
                "status": "partial" if inventory_partial else "inventory_complete",
                "vulnerability_analysis_status": vulnerability_status,
                "supported_package_manager": "npm, pnpm",
                "snapshot": "default-branch commit SHA; results are tied to the returned commit_sha",
                # Legacy flat list of human-readable messages (everything that is not purely informational).
                "warnings": warnings,
                # Structured diagnostics: stable `code`, `severity`, optional `path`, `hint`, `details`.
                "diagnostics": [d.as_dict() for d in diagnostics],
                "diagnostics_summary": counts,
                "lockfiles": lockfile_reports,
                "coverage": {
                    "projects_total": len(projects), "projects_with_resolved_graph": analyzed_projects,
                    "direct_dependencies_declared": len(direct_declared),
                    "direct_dependencies_resolved": sum(1 for d in direct_declared if d["resolved"]),
                    "direct_dependencies_unresolved_required": sum(1 for d in direct_declared if d["required"] and not d["resolved"]),
                    "projects_without_lockfile": len(no_lockfile),
                    "packages_total": len(packages),
                    "packages_queried_in_osv": report.packages_queried,
                    "packages_not_scannable": len(non_registry),
                    "osv_lookups_failed": report.failed_queries,
                    "advisory_details_failed": len(report.failed_advisories),
                    "withdrawn_advisories_ignored": len(report.withdrawn_advisories),
                },
                "timings_ms": timings,
                "reachability": reachability_meta,
            },
        }
    finally:
        await client.close()
