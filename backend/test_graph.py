import json
from pathlib import Path
import pprint

from app.analysis.direct import get_direct_dependencies
from app.analysis.graph import build_dependency_graph
from app.analysis.projects import NpmProject
from app.analysis.relationships import (
    associate_project_dependencies,
)
from app.analysis.impact import (
    find_affected_packages,
    find_dependency_paths,
    find_project_impact,
    analyze_impact
)

from app.analysis.service import analyze_project_impact
from app.analysis.reporting import format_project_impact


LOCKFILE = Path(
    "temp-npm-test/saransh-backend-package-lock.json"
)

MANIFEST = Path(
    "temp-npm-test/saransh-backend-package.json"
)


with LOCKFILE.open("r", encoding="utf-8") as file:
    lockfile = json.load(file)

with MANIFEST.open("r", encoding="utf-8") as file:
    manifest_data = json.load(file)


# Build dependency graph
graph = build_dependency_graph(
    lockfile["packages"]
)


# Validate optional dependencies
optional_edges = [
    edge
    for edge in graph.edges
    if edge.dependency_type.value == "optional"
]

assert len(optional_edges) == 5

optional_pairs = {
    (edge.source, edge.target)
    for edge in optional_edges
}

expected_optional_pairs = {
    (
        "node_modules/chokidar",
        "node_modules/fsevents",
    ),
    (
        "node_modules/cli-table3",
        "node_modules/@colors/colors",
    ),
    (
        "node_modules/jackspeak",
        "node_modules/@pkgjs/parseargs",
    ),
    (
        "node_modules/jest-haste-map",
        "node_modules/fsevents",
    ),
    (
        "node_modules/jsonfile",
        "node_modules/graceful-fs",
    ),
}

assert optional_pairs == expected_optional_pairs

print("Optional edge validation: PASS")


# Validate peer dependencies
peer_edges = [
    edge
    for edge in graph.edges
    if edge.dependency_type.value == "peer"
]

print("Peer edges:", len(peer_edges))

missing_peer_targets = [
    edge
    for edge in peer_edges
    if edge.target not in graph.nodes
]

assert len(missing_peer_targets) == 0

print("Peer edge validation: PASS")


# Create project
project = NpmProject(
    root_path="backend",
    manifest={
        "path": "backend/package.json",
        "sha": "test",
    },
    manifest_data=manifest_data,
    lockfile={
        "path": "backend/package-lock.json",
        "sha": "test",
    },
    package_name=manifest_data.get("name"),
    package_version=manifest_data.get("version"),
    is_workspace_root=False,
    workspace_patterns=[],
    workspace_members=[],
)


# Associate direct dependencies with graph nodes
unresolved_direct = associate_project_dependencies(
    project,
    graph,
)

print(
    "\nUnresolved direct dependencies:",
    len(unresolved_direct),
)

for dependency in unresolved_direct:
    print("  ", dependency)

direct_dependencies = get_direct_dependencies(
    manifest_data
)

print("\nDirect dependency sample:")
print(list(direct_dependencies.items())[:5])

print("\nProject dependencies:")

for dependency in project.dependencies:
    node = graph.nodes[dependency.dependency_path]

    print(
        f"  {node.name}@{node.version}"
        f" [{dependency.dependency_type}]"
    )


print("\nNodes:", len(graph.nodes))
print("Edges:", len(graph.edges))
print(
    "Project dependencies:",
    len(project.dependencies),
)


print("\nSample Edges:")

for edge in graph.edges[:10]:
    print(
        f"  {edge.source}"
        f" -> {edge.target}"
        f"  [{edge.dependency_type.value}]"
    )


print(
    "\nUnresolved graph dependencies:",
    len(graph.unresolved),
)

for unresolved in graph.unresolved[:20]:
    print(
        f"  {unresolved['from']}"
        f" -> {unresolved['dependency']}"
    )
    
    
target = "node_modules/rxjs"
assert (
    "node_modules/@nestjs/common"
    in graph.reverse_edges["node_modules/rxjs"]
)

affected = find_affected_packages(
    graph,
    target,
)

print("\nImpact analysis:")
print("Target:", target)
print("Affected packages:", len(affected))

for path in sorted(affected):
    node = graph.nodes[path]

    print(
        f"  {node.name}@{node.version}"
    )
    
assert target in affected        

missing_target = find_affected_packages(
    graph,
    "node_modules/does-not-exist",
)

assert missing_target == set()

dependencyPaths = find_dependency_paths(
    graph,
    target,
)

print("Dependency Paths:" ,dependencyPaths)


result = analyze_impact(
    graph,
    project,
    target,
)


print(result)
    
# print(
#     format_project_impact(
#         result,
#         graph,
#     )
# )


result = analyze_project_impact(
    lockfile_data=lockfile,
    manifest_data=manifest_data,
    project_path="backend",
    target_path="node_modules/rxjs",
)

print("\nService result:")
print(result)
