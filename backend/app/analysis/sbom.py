"""Build a CycloneDX 1.6 SBOM from SupplyLens project/package records."""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote
from uuid import uuid4
from typing import Any


def _project_ref(project: dict[str, Any]) -> str:
    return "urn:supplylens:project:" + quote(project.get("path") or ".", safe="")


def _package_purl(name: str, version: str) -> str:
    if name.startswith("@") and "/" in name:
        scope, package = name[1:].split("/", 1)
        encoded_name = f"%40{quote(scope, safe='')}/{quote(package, safe='')}"
    else:
        encoded_name = quote(name, safe="")
    return f"pkg:npm/{encoded_name}@{quote(version, safe='.+-')}"


def build_cyclonedx_sbom(
    repository: dict[str, Any],
    projects: list[dict[str, Any]],
    packages: list[dict[str, Any]],
    edges: list[dict[str, str]],
) -> dict[str, Any]:
    """Return inventory-only CycloneDX; vulnerability results remain in the API's findings section."""
    commit_sha = repository.get("commit_sha", "unknown")
    repo_name = repository.get("name", "unknown-repository")
    root_ref = f"urn:supplylens:repository:{quote(str(repo_name), safe='')}@{commit_sha}"
    components: list[dict[str, Any]] = []
    dependencies: dict[str, set[str]] = {root_ref: set()}

    for project in projects:
        ref = _project_ref(project)
        component: dict[str, Any] = {
            "type": "application",
            "bom-ref": ref,
            "name": project.get("name") or project.get("path") or repo_name,
            "properties": [
                {"name": "supplylens:project:path", "value": project.get("path") or "."},
                {"name": "supplylens:project:has-resolved-graph", "value": str(bool(project.get("has_resolved_graph"))).lower()},
            ],
        }
        if project.get("version"):
            component["version"] = project["version"]
        components.append(component)
        dependencies[root_ref].add(ref)
        dependencies.setdefault(ref, set())
        graph_lockfile = project.get("graph_lockfile_path")
        for declaration in project.get("direct_dependencies", []):
            package_path = declaration.get("package_path")
            if not declaration.get("resolved") or not package_path or not graph_lockfile:
                continue
            package_ref = f"{graph_lockfile}::{package_path}"
            dependencies[ref].add(package_ref)

    for package in packages:
        ref = package["id"]
        component = {
            "type": "library",
            "bom-ref": ref,
            "name": package["name"],
            "version": package["version"],
            "purl": _package_purl(package["name"], package["version"]),
            "properties": [
                {"name": "supplylens:package:path", "value": package["path"]},
                {"name": "supplylens:package:lockfile", "value": package["lockfile"]},
                {"name": "supplylens:package:is-direct", "value": str(bool(package.get("is_direct"))).lower()},
            ],
        }
        if package.get("integrity"):
            component["properties"].append({"name": "supplylens:npm:integrity", "value": package["integrity"]})
        if package.get("resolved"):
            component["externalReferences"] = [{"type": "distribution", "url": package["resolved"]}]
        components.append(component)
        dependencies.setdefault(ref, set())

    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        if source and target:
            dependencies.setdefault(source, set()).add(target)
            dependencies.setdefault(target, set())

    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{uuid4()}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "tools": {"components": [{"type": "application", "name": "SupplyLens", "version": "0.3.0"}]},
            "component": {"type": "application", "bom-ref": root_ref, "name": str(repo_name)},
        },
        "components": components,
        "dependencies": [
            {"ref": ref, "dependsOn": sorted(targets)}
            for ref, targets in sorted(dependencies.items())
        ],
    }
